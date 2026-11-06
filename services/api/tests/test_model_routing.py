from test_api import app as app
from test_api import client as client
from test_model_center import project


def test_worker_holds_central_request_without_dispatch_or_optimizer_reservation(client, app):
    from ai_team.model_center import ModelCenter
    from ai_team.model_router import CentralProvider
    from ai_team.worker import Worker

    pid = project(client)
    run = ModelCenter(app.state.database).request(pid, "held", "Preparar plano simples", "owner")
    assert Worker(
        app.state.database, app.state.settings, CentralProvider(app.state.database)
    ).once()
    with app.state.database.session() as db:
        from ai_team.models import Run

        saved = db.get(Run, run.id)
        assert saved.status == "waiting_model" and saved.calls == 0 and saved.stage == 0


def test_model_api_has_auth_csrf_and_no_inference_in_http(client):
    assert client.get("/model-center/missing").status_code == 401
    pid = project(client)
    url = f"/model-center/{pid}"
    assert client.get(url).status_code == 200
    assert (
        client.post(url + "/check", json={}, headers={"origin": "https://evil"}).status_code == 403
    )
    assert client.post(url + "/check", json={}).json()["status"] == "queued"
    result = client.post(
        url + "/requests",
        json={
            "request_id": "api-request-1",
            "prompt": "Planejar um produto simples",
            "consent": True,
        },
    )
    assert result.status_code == 201, result.text
    assert result.json()["calls"] == 0 and result.json()["executor"] == "central"


def test_free_dispatch_reports_usage_and_rate_limit_cannot_immediately_replay(client, app):
    from ai_team.gemini import GeminiRateLimited
    from ai_team.model_center import ModelCenter, Preference
    from ai_team.model_router import CentralProvider
    from ai_team.orchestration import Draft
    from ai_team.worker import Worker
    from ai_team.workflow import WorkflowStore

    store = ModelCenter(app.state.database)
    pid = project(client)
    store.configure(pid, "CEO", Preference(enabled=True, quotas_confirmed=True), "owner")
    called = []

    class FreeClient:
        def check(self):
            return {"status": "verified", "project_key": "123456"}

        def close(self):
            pass

        def generate(self, role, instructions, context, tick, *, authorized=False):
            assert authorized is True
            tick()
            called.append(role)
            if len(called) == 2:
                raise GeminiRateLimited(90)
            return Draft(
                summary="Plano verificado",
                deliverable="Proposta textual",
                tasks=[],
                input_tokens=10,
                output_tokens=20,
            )

    worker = Worker(
        app.state.database,
        app.state.settings,
        CentralProvider(app.state.database, factory=FreeClient),
    )
    first = store.request(pid, "success", "Preparar plano simples", "owner")
    assert worker.once()
    assert WorkflowStore(app.state.database).get(first.id).stage == 1
    row = store.snapshot(pid)["history"][0]
    assert row["input_tokens"] == 10 and row["output_tokens"] == 20
    second = store.request(pid, "limited", "Preparar outro plano simples", "owner")
    assert worker.once()
    assert WorkflowStore(app.state.database).get(second.id).status == "waiting_quota"
    assert (
        client.post(f"/model-center/{pid}/resume/{second.id}", json={"consent": True}).status_code
        == 200
    )
    assert worker.once()
    assert called == ["CEO", "CEO"]
    assert WorkflowStore(app.state.database).get(second.id).calls == 1


def test_codex_manual_handoff_is_bound_to_project_stage_and_digest(client, app):
    from ai_team.model_center import ModelCenter, Preference
    from ai_team.model_router import CentralProvider
    from ai_team.worker import Worker

    store = ModelCenter(app.state.database)
    pid = project(client)
    store.configure(
        pid, "CEO", Preference(mode="manual", provider="codex", model="codex-supervised"), "owner"
    )
    run = store.request(pid, "manual", "Planejar com executor próprio supervisionado", "owner")
    assert Worker(
        app.state.database, app.state.settings, CentralProvider(app.state.database)
    ).once()
    url = f"/model-center/{pid}/handoff/{run.id}"
    reviewed = client.get(url).json()
    data = {
        "consent": True,
        "digest": "a" * 64,
        "draft": {"summary": "Resultado manual", "deliverable": "Proposta humana", "tasks": []},
    }
    assert client.post(url, json=data).status_code == 409
    other = project(client)
    assert client.get(f"/model-center/{other}/handoff/{run.id}").status_code == 404
    data["digest"] = reviewed["digest"]
    result = client.post(url, json=data)
    assert result.status_code == 200, result.text
    assert result.json()["stage"] == 1 and result.json()["calls"] == 0
    assert client.post(url, json=data).status_code == 409


def test_central_waiting_request_can_be_cancelled(client, app):
    from ai_team.model_center import ModelCenter
    from ai_team.model_router import CentralProvider
    from ai_team.worker import Worker
    from ai_team.workflow import WorkflowStore

    run = ModelCenter(app.state.database).request(
        project(client), "cancel", "Plano simples", "owner"
    )
    assert Worker(
        app.state.database, app.state.settings, CentralProvider(app.state.database)
    ).once()
    WorkflowStore(app.state.database).cancel(run.id, "owner")
    assert WorkflowStore(app.state.database).get(run.id).status == "cancelled"
