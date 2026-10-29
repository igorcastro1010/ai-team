import pytest
from test_api import app as app
from test_api import client as client
from test_api import login


def test_vercel_routes_require_login_and_origin(client):
    assert client.get("/vercel").status_code == 401
    assert client.post("/vercel/inspect").status_code == 401
    assert (
        client.post("/vercel/inspect", headers={"origin": "https://evil.example"}).status_code
        == 403
    )


def test_inspection_is_persisted_without_secrets_and_get_never_calls_provider(
    client, app, monkeypatch
):
    import ai_team.vercel_routes as routes

    calls = []

    class Vault:
        def load(self):
            return {"token": "synthetic-private-token", "team_id": None}

    class Reader:
        def __init__(self, *args, **kwargs):
            calls.append(True)

        def probe(self):
            return {
                "verified_at": 123,
                "project": {"id": "prj_test", "name": "ai-team", "env": "secret"},
                "deployments": [
                    {
                        "id": "dpl_test",
                        "state": "READY",
                        "created_at": 123000,
                        "token": "synthetic-private-token",
                    }
                ],
                "raw_token": "synthetic-private-token",
            }

        def close(self):
            pass

    monkeypatch.setattr(routes, "VercelVault", Vault)
    monkeypatch.setattr(routes, "VercelClient", Reader)
    login(client)
    result = client.post("/vercel/inspect")
    assert result.status_code == 200
    assert "synthetic-private-token" not in result.text and "env" not in result.text
    assert client.get("/vercel").json()["connection"]["project"]["id"] == "prj_test"
    snapshot = client.get("/workspace")
    assert snapshot.json()["vercel"]["connection"]["deployments"][0]["state"] == "READY"
    assert len(calls) == 1


@pytest.mark.parametrize("configured", [False, True])
def test_missing_or_failed_credentials_never_leak_into_responses(client, monkeypatch, configured):
    import ai_team.vercel_routes as routes

    class Vault:
        def load(self):
            return {"token": "synthetic-private-token"} if configured else None

    class BrokenReader:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("Error containing synthetic-private-token")

    monkeypatch.setattr(routes, "VercelVault", Vault)
    monkeypatch.setattr(routes, "VercelClient", BrokenReader)
    login(client)
    response = client.post("/vercel/inspect")
    assert response.status_code in {409, 502}
    assert "synthetic-private-token" not in response.text
    assert client.get("/vercel").json()["connection"] is None
