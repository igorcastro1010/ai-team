"""Contract doubles only: no paid inference and no claims about a live gateway."""

import json

import httpx
import pytest
from pydantic import ValidationError

from ai_team.config import Settings
from ai_team.hermes import HermesClient, HermesProvider


def settings(**changes):
    return Settings(hermes_url="http://hermes:8642", hermes_key="x" * 40, **changes)


@pytest.mark.parametrize("url", [
    "http://example.com", "http://169.254.169.254", "http://hermes.evil.test",
    "http://user:pass@hermes:8642", "http://hermes:8642/a", "http://hermes?token=a",
])
def test_refuses_public_or_ambiguous_destination(url):
    with pytest.raises(ValidationError):
        Settings(hermes_url=url)


def test_no_network_without_configuration():
    client = HermesClient(Settings(), transport=httpx.MockTransport(lambda r: pytest.fail()))
    assert client.inspect()["status"] == "not_configured"


def make_client(handler):
    return HermesClient(settings(), transport=httpx.MockTransport(handler))


def test_probe_authentication_capabilities_and_redaction():
    def handler(request):
        assert request.headers["Authorization"] == "Bearer " + "x" * 40
        if request.url.path == "/v1/toolsets":
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={"object": "hermes.api_server.capabilities",
                                         "features": {"runs": True}, "key": "private"})
    result = make_client(handler).inspect()
    assert result["status"] == "reachable"
    assert "private" not in json.dumps(result)
    assert "x" * 40 not in json.dumps(result)


@pytest.mark.parametrize("response", [
    httpx.Response(302, headers={"location": "https://evil.test"}),
    httpx.Response(401, json={"error": "secret value"}),
    httpx.Response(200, content=b"not json"),
    httpx.Response(200, content=b"x" * 210000),
])
def test_probe_fails_closed_without_remote_error_details(response):
    result = make_client(lambda r: response).inspect()
    assert result["status"] == "unavailable"
    assert "secret" not in json.dumps(result)


def test_refuses_inference_when_toolset_enabled():
    def handler(request):
        assert request.method == "GET"
        if request.url.path == "/v1/toolsets":
            return httpx.Response(200, json=[{"name": "terminal", "enabled": True}])
        return httpx.Response(200, json={"object": "hermes.api_server.capabilities"})
    client = make_client(handler)
    assert client.inspect()["status"] == "unsafe_configuration"
    with pytest.raises(RuntimeError):
        HermesProvider(client).generate("CEO", "plan", {}, lambda: None)


def run_client(status="completed", invalid=False):
    calls = []
    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json={"object": "hermes.api_server.capabilities"})
        if request.url.path == "/v1/toolsets":
            return httpx.Response(200, json=[])
        if request.method == "POST" and request.url.path == "/v1/runs":
            assert request.headers["Idempotency-Key"]
            assert json.loads(request.content)["session_id"].startswith("ai-team-")
            return httpx.Response(202, json={"run_id": "run_test", "status": "started"})
        if request.url.path.endswith("/stop"):
            return httpx.Response(200, json={"status": "cancelled"})
        return httpx.Response(200, json={"status": status,
            "output": "invalid" if invalid else json.dumps({
                "summary": "Plano real", "deliverable": "Resultado", "tasks": []}),
            "usage": {"input_tokens": 12, "output_tokens": 8}})
    return make_client(handler), calls


def test_run_polls_and_validates_output_and_usage():
    client, calls = run_client()
    draft = HermesProvider(client).generate("CEO", "plan", {}, lambda: None)
    assert draft.input_tokens == 12
    assert draft.output_tokens == 8
    assert draft.summary == "Plano real"
    assert calls.count(("POST", "/v1/runs")) == 1


@pytest.mark.parametrize("status", ["failed", "cancelled", "interrupted", "unknown"])
def test_non_success_status_is_never_a_completed_draft(status):
    client, _ = run_client(status)
    with pytest.raises(RuntimeError):
        HermesProvider(client).generate("CEO", "plan", {}, lambda: None)


def test_invalid_output_not_accepted():
    client, _ = run_client(invalid=True)
    with pytest.raises((RuntimeError, ValidationError)):
        HermesProvider(client).generate("CEO", "plan", {}, lambda: None)


def test_cancel_requests_remote_stop_without_retrying_admission():
    client, calls = run_client("running")
    count = 0
    def tick():
        nonlocal count
        count += 1
        if count > 1:
            raise InterruptedError()
    with pytest.raises(InterruptedError):
        HermesProvider(client, poll_interval=0).generate("CEO", "plan", {}, tick)
    assert ("POST", "/v1/runs/run_test/stop") in calls
    assert calls.count(("POST", "/v1/runs")) == 1


def test_executor_consent_is_persistent_and_legacy_runs_stay_codex(tmp_path):
    from ai_team.db import Database
    from ai_team.models import Project
    from ai_team.workflow import WorkflowStore
    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'binding.db'}"))
    database.initialize()
    with database.session() as db:
        project = Project(name="Consentimento")
        db.add(project)
        db.commit()
    store = WorkflowStore(database)
    old = store.create(project.id, "Pedido antigo Codex", "owner")
    new = store.create(project.id, "Pedido autorizado Hermes", "owner", executor="hermes")
    assert store.get(old.id).executor == "codex"
    assert store.get(new.id).executor == "hermes"
    # Reopening and initializing adds tables without replacing existing rows.
    database.engine.dispose()
    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'binding.db'}"))
    database.initialize()
    assert WorkflowStore(database).get(new.id).executor == "hermes"
    assert len(WorkflowStore(database).all()) == 2
