import io
import json
import zipfile

import pytest
from test_workflow import environment as environment

from ai_team.orchestration import Draft
from ai_team.worker import Worker
from ai_team.workflow import WorkflowStore


class CodeProvider:
    def ready(self):
        return True

    def generate(self, role, instructions, context, on_tick):
        files = {
            "DEV": [{"path": "main.py", "content": "def add(a, b): return a+b\n"}],
            "QA": [
                {
                    "path": "test_main.py",
                    "content": "import unittest\nfrom main import add\n"
                    "class TestAdd(unittest.TestCase):\n"
                    " def test_add(self): self.assertEqual(add(2,3),5)\n",
                }
            ],
        }
        return Draft(
            summary=f"Etapa {role}",
            tasks=[],
            input_tokens=5,
            output_tokens=5,
            deliverable=json.dumps({"files": files[role]})
            if role in files
            else "Plano ou relatório",
        )


class Sandbox:
    def __init__(self):
        self.calls = 0

    def run(self, bundle, on_tick, *, name=None):
        on_tick()
        self.calls += 1
        return {
            "status": "passed",
            "exit_code": 0,
            "output": "OK",
            "artifact_digest": bundle.digest,
        }

    def cleanup(self, name):
        self.cleaned = name


def prepared(client, db, settings):
    project = client.post("/projects", json={"name": "Python isolado", "mode": "automatic"}).json()
    run = client.post(
        "/runs",
        json={
            "project_id": project["id"],
            "prompt": "Crie uma soma com testes",
            "scope": "python_code",
            "executor": "hermes",
            "consent": True,
        },
    ).json()
    sandbox = Sandbox()
    worker = Worker(db, settings, CodeProvider(), sandbox=sandbox)
    for _ in range(4):
        worker.once()
    return client.get(f"/runs/{run['id']}").json(), worker, sandbox


def test_code_stops_for_hash_approval_even_in_automatic_mode(environment):
    client, db, settings = environment
    run, worker, sandbox = prepared(client, db, settings)
    assert run["scope"] == "python_code"
    assert run["stage"] == 4 and run["status"] == "awaiting_approval"
    assert len(run["artifact_digest"]) == 64
    worker.once()
    assert sandbox.calls == 0
    url = f"/runs/{run['id']}/decision"
    assert client.post(url, json={"stage": 4, "approve": True}).status_code == 409
    assert (
        client.post(
            url, json={"stage": 4, "approve": True, "artifact_digest": "a" * 64}
        ).status_code
        == 409
    )
    approved = {"stage": 4, "approve": True, "artifact_digest": run["artifact_digest"]}
    assert client.post(url, json=approved).status_code == 200
    assert client.post(url, json=approved).status_code == 409
    worker.once()
    finished = client.get(f"/runs/{run['id']}").json()
    assert finished["status"] == "completed" and sandbox.calls == 1
    assert finished["steps"][3]["test_result"]["status"] == "passed"
    assert finished["calls"] == 5
    response = client.get(f"/runs/{run['id']}/artifacts")
    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert set(archive.namelist()) == {"main.py", "test_main.py"}


def test_cancelled_code_never_executes_and_download_requires_owner(environment):
    client, db, settings = environment
    run, worker, sandbox = prepared(client, db, settings)
    assert client.post(f"/runs/{run['id']}/cancel").status_code == 200
    worker.once()
    assert sandbox.calls == 0
    client.cookies.clear()
    assert client.get(f"/runs/{run['id']}/artifacts").status_code == 401


def test_store_rejects_unknown_scope(environment):
    client, db, settings = environment
    project = client.post("/projects", json={"name": "Escopo"}).json()
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        WorkflowStore(db).create(project["id"], "teste", "tester", scope="host_shell")


def test_modified_artifacts_after_approval_fail_before_sandbox(environment):
    from ai_team.models import Run

    client, db, settings = environment
    run, worker, sandbox = prepared(client, db, settings)
    client.post(
        f"/runs/{run['id']}/decision",
        json={
            "stage": 4,
            "approve": True,
            "artifact_digest": run["artifact_digest"],
        },
    )
    with db.session() as session:
        stored = session.get(Run, run["id"])
        steps = [dict(step) for step in stored.steps]
        data = json.loads(steps[1]["deliverable"])
        data["files"][0]["content"] += "\n# Changed after review\n"
        steps[1]["deliverable"] = json.dumps(data)
        stored.steps = steps
        session.commit()
    worker.once()
    assert sandbox.calls == 0
    assert WorkflowStore(db).get(run["id"]).status == "failed"


def test_failed_tests_are_persisted_as_failed_and_csrf_blocks_approval(environment):
    client, db, settings = environment
    run, worker, sandbox = prepared(client, db, settings)
    data = {"stage": 4, "approve": True, "artifact_digest": run["artifact_digest"]}
    url = f"/runs/{run['id']}/decision"
    assert client.post(url, json=data, headers={"origin": "https://evil.test"}).status_code == 403
    client.post(url, json=data)

    def fail(bundle, tick, *, name=None):
        return {
            "status": "failed",
            "exit_code": 1,
            "output": "AssertionError",
            "artifact_digest": bundle.digest,
        }

    sandbox.run = fail
    worker.once()
    result = WorkflowStore(db).get(run["id"])
    assert result.status == "completed"
    assert result.steps[3]["test_result"]["status"] == "failed"


def test_expired_worker_reconciles_exact_persisted_container_without_readmission(environment):
    from ai_team.models import Run

    client, db, settings = environment
    run, worker, sandbox = prepared(client, db, settings)
    store = WorkflowStore(db)
    store.decide(run["id"], 4, True, "tester", artifact_digest=run["artifact_digest"])
    claimed = store.claim()
    name = "ai-team-test-" + "a" * 32
    store.record_sandbox(claimed, container_name=name)
    with db.session() as session:
        session.get(Run, run["id"]).lease_expires_at = 0
        session.commit()
    worker.once()
    assert sandbox.cleaned == name
    recovered = store.get(run["id"])
    assert recovered.status == "failed" and sandbox.calls == 0
    assert recovered.steps[3]["cleanup_confirmed"] is True


def test_offline_docker_blocks_code_but_preserves_text_worker(environment):
    from ai_team.models import Run

    client, db, settings = environment
    run, worker, sandbox = prepared(client, db, settings)
    store = WorkflowStore(db)
    store.decide(run["id"], 4, True, "tester", artifact_digest=run["artifact_digest"])
    claimed = store.claim()
    store.record_sandbox(claimed, container_name="ai-team-test-" + "b" * 32)
    with db.session() as session:
        session.get(Run, run["id"]).lease_expires_at = 0
        session.commit()

    def offline(name):
        raise RuntimeError("Docker offline")

    sandbox.cleanup = offline
    text = store.create(run["project_id"], "Plano textual", "tester")
    code = store.create(run["project_id"], "Novo código", "tester", scope="python_code")
    worker.once()
    assert store.get(text.id).stage == 1
    assert store.get(code.id).stage == 0
    assert store.get(run["id"]).steps[3]["cleanup_state"] == "uncertain"
