import httpx
from test_api import app as app
from test_api import client as client
from test_api import login

from ai_team.hermes_journal import HermesJournal
from ai_team.workflow import WorkflowStore


def prepare(client, app, *, remote_id="native_1"):
    login(client)
    project = client.post("/projects", json={"name": "Controle Hermes"}).json()
    created = client.post(
        "/runs",
        json={
            "project_id": project["id"],
            "prompt": "Planeje um teste.",
            "consent": True,
            "executor": "hermes",
        },
    ).json()
    run = WorkflowStore(app.state.database).claim()
    assert run.id == created["id"]
    journal = HermesJournal(app.state.database)
    attempt = journal.begin(run, "ai-team-synthetic")
    if remote_id:
        journal.admitted(attempt.id, remote_id)
    return attempt, run, journal


def test_owner_authentication_origin_and_confirmation(client):
    assert client.get("/hermes/executions").status_code == 401
    assert client.post("/hermes/executions/test/refresh").status_code == 401
    assert client.post("/hermes/executions/test/stop", json={"confirm": True}).status_code == 401
    login(client)
    assert (
        client.post(
            "/hermes/executions/test/stop",
            json={"confirm": True},
            headers={"origin": "https://evil.test"},
        ).status_code
        == 403
    )
    assert client.post("/hermes/executions/test/stop", json={"confirm": False}).status_code == 422
    assert (
        client.post(
            "/hermes/executions/test/stop", json={"confirm": True, "remote_id": "anything"}
        ).status_code
        == 422
    )


def test_refresh_uses_only_persisted_id_and_sanitizes_remote_response(client, app, monkeypatch):
    import ai_team.hermes_routes as routes

    attempt, _, _ = prepare(client, app)
    calls = []

    class Reader:
        def __init__(self, settings, *, database):
            assert database is client.app.state.database
            pass

        def request(self, method, path, **kwargs):
            calls.append((method, path))
            return {
                "run_id": "native_1",
                "status": "completed",
                "output": "private-output",
                "usage": {"input_tokens": 20, "output_tokens": 8},
                "secret": "private-key",
            }

    monkeypatch.setattr(routes, "HermesClient", Reader)
    response = client.post(f"/hermes/executions/{attempt.id}/refresh")
    assert response.status_code == 200
    assert response.json()["remote_status"] == "completed"
    assert response.json()["input_tokens"] == 20
    assert "private" not in response.text
    assert calls == [("GET", "/v1/runs/native_1")]
    assert "ai-team-synthetic" not in client.get("/hermes/executions").text
    assert client.get("/workspace").json()["hermes"]["executions"]["items"][0]["id"] == attempt.id


def test_stop_requires_local_cancellation_and_observes_native_terminal_state(
    client, app, monkeypatch
):
    import ai_team.hermes_routes as routes

    attempt, run, _ = prepare(client, app)
    calls = []

    class Controller:
        def __init__(self, settings, *, database):
            assert database is client.app.state.database
            pass

        def request(self, method, path, **kwargs):
            calls.append((method, path))
            return {"status": "cancelled"} if method == "GET" else {"status": "running"}

    monkeypatch.setattr(routes, "HermesClient", Controller)
    endpoint = f"/hermes/executions/{attempt.id}/stop"
    assert client.post(endpoint, json={"confirm": True}).status_code == 409
    assert not calls
    client.post(f"/runs/{run.id}/cancel")
    result = client.post(endpoint, json={"confirm": True})
    assert result.status_code == 200
    assert result.json()["stop_status"] == "confirmed"
    assert calls == [("POST", "/v1/runs/native_1/stop"), ("GET", "/v1/runs/native_1")]
    assert client.get(f"/runs/{run.id}").json()["status"] == "cancelled"


def test_failed_stop_is_uncertain_and_error_detail_is_private(client, app, monkeypatch):
    import ai_team.hermes_routes as routes

    attempt, run, journal = prepare(client, app)
    client.post(f"/runs/{run.id}/cancel")

    class Broken:
        def __init__(self, settings, *, database):
            assert database is client.app.state.database
            pass

        def request(self, *args, **kwargs):
            raise httpx.ConnectError("secret-provider-error")

    monkeypatch.setattr(routes, "HermesClient", Broken)
    response = client.post(f"/hermes/executions/{attempt.id}/stop", json={"confirm": True})
    assert response.status_code == 502
    assert "secret-provider-error" not in response.text
    assert journal.get(attempt.id).stop_status == "uncertain"


def test_unknown_admission_cannot_be_readmitted_or_control_arbitrary_remote(client, app):
    attempt, _, _ = prepare(client, app, remote_id="")
    assert client.post(f"/hermes/executions/{attempt.id}/refresh").status_code == 409
    assert client.get("/hermes/executions?before=missing").status_code == 404
    assert client.post("/hermes/executions/missing/refresh").status_code == 404
