from test_api import app as app
from test_api import client as client
from test_api import login


def test_hermes_is_owner_only_and_csrf_protected(client):
    assert client.get("/hermes").status_code == 401
    assert client.post("/hermes/inspect").status_code == 401
    login(client)
    assert (
        client.post("/hermes/inspect", headers={"origin": "https://evil.test"}).status_code == 403
    )


def test_inspection_persists_sanitized_observation_without_inference(client, monkeypatch):
    import ai_team.hermes_routes as routes

    calls = []

    class Reader:
        def __init__(self, settings):
            pass

        def inspect(self):
            calls.append(True)
            return {
                "status": "reachable",
                "checked_at": 123,
                "text_only": True,
                "inference_verified": False,
                "secret": "private-key",
            }

    monkeypatch.setattr(routes, "HermesClient", Reader)
    login(client)
    assert client.get("/hermes").json()["connection"] is None
    result = client.post("/hermes/inspect")
    assert result.status_code == 200
    assert "private-key" not in result.text
    assert client.get("/hermes").json()["connection"]["status"] == "reachable"
    assert client.get("/workspace").json()["hermes"]["connection"]["checked_at"] == 123
    assert len(calls) == 1


def test_hermes_consent_recorded_without_changing_codex_default(client):
    login(client)
    project = client.post("/projects", json={"name": "Execução"}).json()
    body = {"project_id": project["id"], "prompt": "Proponha um plano.", "consent": True}
    assert client.post("/runs", json=body).json()["executor"] == "codex"
    assert client.post("/runs", json={**body, "executor": "hermes"}).json()["executor"] == "hermes"
    assert client.post("/runs", json={**body, "executor": "shell"}).status_code == 422
