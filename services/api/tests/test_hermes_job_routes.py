import httpx
import pytest
from fastapi.testclient import TestClient
from test_api import app as base_app  # noqa: F401 - imported pytest fixture
from test_api import login

from ai_team.hermes import HermesClient
from ai_team.hermes_job_routes import router


@pytest.fixture
def app(request):
    application = request.getfixturevalue("base_app")
    application.include_router(router)
    return application


@pytest.fixture
def client(app):
    with TestClient(app, headers={"origin": "http://localhost:3000"}) as browser:
        yield browser


def test_owner_origin_confirmation_and_allowlisted_routes(client):
    assert client.get("/hermes/jobs").status_code == 401
    assert client.post("/hermes/jobs/inspect").status_code == 401
    assert client.post("/hermes/jobs/abcdef123456/pause", json={"confirm": True}).status_code == 401
    login(client)
    endpoint = "/hermes/jobs/abcdef123456/pause"
    assert client.post(endpoint, json={"confirm": False}).status_code == 422
    assert client.post(endpoint, json={"confirm": True, "id": "anything"}).status_code == 422
    assert (
        client.post(
            endpoint, json={"confirm": True}, headers={"origin": "https://evil.test"}
        ).status_code
        == 403
    )
    assert client.post(endpoint, json={"confirm": True}).status_code == 409
    for suffix in ("resume", "run", "delete"):
        assert client.post(f"/hermes/jobs/abcdef123456/{suffix}").status_code == 404
    assert client.post("/hermes/jobs").status_code == 405


def test_cached_get_does_not_contact_gateway_and_live_inspect_is_sanitized(client, monkeypatch):
    import ai_team.hermes_job_routes as routes

    calls = []

    def factory(settings):
        settings = settings.model_copy(update={"hermes_url": "http://hermes:8642"})
        from pydantic import SecretStr

        settings.hermes_key = SecretStr("x" * 40)

        def handler(request):
            calls.append((request.method, request.url.path))
            return httpx.Response(200, json={"jobs": []})

        return HermesClient(settings, transport=httpx.MockTransport(handler))

    monkeypatch.setattr(routes, "HermesClient", factory)
    login(client)
    assert client.get("/hermes/jobs").json()["checked_at"] is None
    assert calls == []
    result = client.post("/hermes/jobs/inspect")
    assert result.status_code == 200 and result.json()["status"] == "reachable"
    assert client.get("/hermes/jobs").json() == result.json()
    assert calls == [("GET", "/api/jobs")]
