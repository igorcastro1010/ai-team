import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ai_team.auth import create_owner
from ai_team.config import Settings
from ai_team.db import Database
from ai_team.main import create_app
from ai_team.models import Run, Task
from ai_team.orchestration import Draft, build_graph
from ai_team.worker import Worker
from ai_team.workflow import WorkflowStore


class TestProvider:
    __test__ = False
    calls = None

    def __init__(self, ready=True):
        self.calls = []
        self.available = ready

    def ready(self):
        return self.available

    def generate(self, role, instructions, context, on_tick):
        self.calls.append(role)
        return Draft(
            summary=f"Parecer {role}",
            deliverable="Proposta textual, sem execução externa.",
            tasks=[{"title": "Revisar contrato", "description": "Proposta", "agent": "DEV"}]
            if len(self.calls) == 1
            else [],
            input_tokens=10,
            output_tokens=5,
        )


@pytest.fixture
def environment(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'workflow.db'}", environment="test")
    db = Database(settings)
    db.initialize()
    with db.session() as session:
        create_owner(session, "tester", "teste-workflow-4859")
    app = create_app(settings, db)
    with TestClient(app, headers={"origin": settings.public_origin}) as client:
        client.post("/auth/login", json={"username": "tester", "password": "teste-workflow-4859"})
        yield client, db, settings


def request_run(client, mode="supervised"):
    project = client.post("/projects", json={"name": "Projeto", "mode": mode}).json()
    response = client.post(
        "/runs",
        json={
            "project_id": project["id"],
            "prompt": "Proponha uma interface acessível.",
            "consent": True,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_worker_reports_hermes_quota_without_retry_or_raw_error(environment):
    from ai_team.hermes import HermesRateLimitError

    client, database, settings = environment
    run = request_run(client)

    class LimitedProvider(TestProvider):
        def generate(self, *args):
            raise HermesRateLimitError("private-provider-detail")

    worker = Worker(database, settings, LimitedProvider())
    assert worker.once()
    current = WorkflowStore(database).get(run["id"])
    assert current.status == "failed"
    assert "Cota do provedor Hermes" in current.error
    assert "private-provider-detail" not in current.error
    assert not worker.once()


def test_request_is_persistent_and_does_not_call_model_in_http(environment):
    client, db, settings = environment
    run = request_run(client)
    assert run["status"] == "queued" and run["calls"] == 0
    restarted = WorkflowStore(Database(settings))
    assert restarted.get(run["id"]).prompt == "Proponha uma interface acessível."
    assert client.get("/runs").json()[0]["id"] == run["id"]
    assert (
        client.post(
            "/runs", json={"project_id": run["project_id"], "prompt": "teste", "consent": False}
        ).status_code
        == 422
    )


def test_graph_runs_only_selected_role_and_never_executes_external_tools():
    provider = TestProvider()
    graph = build_graph(provider, lambda: None)
    state = graph.invoke({"stage": 2, "prompt": "teste", "steps": []})
    assert provider.calls == ["DESIGNER"]
    assert state["draft"]["deliverable"].startswith("Proposta")


def test_supervised_plan_requires_one_shot_approval_before_specialists(environment):
    client, db, settings = environment
    run = request_run(client)
    provider = TestProvider()
    worker = Worker(db, settings, provider)
    assert worker.once()
    current = client.get(f"/runs/{run['id']}").json()
    assert current["status"] == "awaiting_approval" and current["stage"] == 1
    assert not worker.once()
    payload = {"stage": 1, "approve": True}
    assert client.post(f"/runs/{run['id']}/decision", json=payload).status_code == 200
    assert client.post(f"/runs/{run['id']}/decision", json=payload).status_code == 409
    for _ in range(4):
        assert worker.once()
    current = client.get(f"/runs/{run['id']}").json()
    assert current["status"] == "completed" and len(current["steps"]) == 5
    assert provider.calls == ["CEO", "DEV", "DESIGNER", "QA", "CEO"]
    assert current["input_tokens"] == 50 and current["output_tokens"] == 25
    with db.session() as session:
        tasks = list(session.scalars(select(Task)))
        assert len(tasks) == 1 and tasks[0].status == "backlog"


def test_manual_requires_approval_for_every_remaining_stage(environment):
    client, db, settings = environment
    run = request_run(client, "manual")
    worker = Worker(db, settings, TestProvider())
    for stage in range(5):
        assert worker.once()
        current = client.get(f"/runs/{run['id']}").json()
        if stage < 4:
            assert current["status"] == "awaiting_approval"
            assert (
                client.post(
                    f"/runs/{run['id']}/decision", json={"stage": stage + 1, "approve": True}
                ).status_code
                == 200
            )
    assert client.get(f"/runs/{run['id']}").json()["status"] == "completed"


def test_automatic_is_limited_to_consented_text_drafting(environment):
    client, db, settings = environment
    run = request_run(client, "automatic")
    worker = Worker(db, settings, TestProvider())
    for _ in range(5):
        assert worker.once()
    assert not worker.once()
    current = client.get(f"/runs/{run['id']}").json()
    assert current["calls"] == 5 and current["scope"] == "draft_only"
    assert (
        client.post(f"/runs/{run['id']}/decision", json={"stage": 4, "approve": True}).status_code
        == 409
    )


def test_concurrent_workers_cannot_claim_same_stage(environment):
    client, db, settings = environment
    run = request_run(client)
    store = WorkflowStore(db)
    with ThreadPoolExecutor(max_workers=6) as executor:
        claims = list(executor.map(lambda _: store.claim(), range(6)))
    assert sum(claim is not None for claim in claims) == 1
    assert store.get(run["id"]).status == "running"


def test_missing_login_blocks_without_spending_a_call(environment):
    client, db, settings = environment
    run = request_run(client)
    worker = Worker(db, settings, TestProvider(ready=False))
    assert worker.once()
    current = client.get(f"/runs/{run['id']}").json()
    assert current["status"] == "blocked" and current["calls"] == 0


def test_cancel_and_reject_are_audited_and_prevent_further_execution(environment):
    client, db, settings = environment
    run = request_run(client)
    assert client.post(f"/runs/{run['id']}/cancel").status_code == 200
    assert not Worker(db, settings, TestProvider()).once()
    assert client.get(f"/runs/{run['id']}").json()["status"] == "cancelled"
    assert any(event["kind"] == "run.cancelled" for event in client.get("/events").json())


def test_stale_lease_fails_instead_of_repeating_paid_call(environment):
    client, db, settings = environment
    run = request_run(client)
    store = WorkflowStore(db)
    assert store.claim()
    with db.session() as session:
        record = session.get(Run, run["id"])
        record.lease_expires_at = int(time.time()) - 1
        session.commit()
    assert store.claim() is None
    assert store.get(run["id"]).status == "failed"


def test_provider_failure_does_not_leak_errors_or_retry(environment):
    class FailingProvider(TestProvider):
        def generate(self, *args, **kwargs):
            raise RuntimeError("OPENAI_API_KEY=do-not-log")

    client, db, settings = environment
    run = request_run(client)
    worker = Worker(db, settings, FailingProvider())
    assert worker.once()
    current = client.get(f"/runs/{run['id']}").json()
    assert current["status"] == "failed" and current["calls"] == 1
    assert "do-not-log" not in str(current)
    assert not worker.once()


def test_older_pending_approval_is_not_hidden_by_recent_completed_runs(environment):
    client, db, settings = environment
    run = request_run(client)
    with db.session() as session:
        record = session.get(Run, run["id"])
        record.status, record.stage, record.created_at = "awaiting_approval", 1, 1
        for index in range(201):
            session.add(
                Run(
                    project_id=run["project_id"],
                    prompt="Histórico",
                    mode="manual",
                    status="completed",
                    stage=5,
                    created_at=100 + index,
                )
            )
        session.commit()
    assert client.get("/workspace").json()["approvals"][0]["id"] == run["id"]
