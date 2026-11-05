import json

import pytest
from fastapi import HTTPException

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Project, Run
from ai_team.orchestration import Draft
from ai_team.repository_policy import RepositoryPolicy
from ai_team.repository_runs import RepositoryStore, execute_repository
from ai_team.workflow import WorkflowStore


@pytest.fixture
def setup(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'runs.db'}", environment="test")
    database = Database(settings)
    database.initialize()
    with database.session() as db:
        project = Project(name="Real execution", mode="automatic")
        db.add(project)
        db.commit()
    store = RepositoryStore(database, root=tmp_path / "workspaces")
    policy = RepositoryPolicy(
        base_sha="a" * 40,
        directory="tools",
        read_paths=["budget.py"],
        write_paths=["budget.py", "test_budget.py", "guide.md"],
    )
    run = store.create(project.id, "Improve budget validation", policy, "owner", "codex")
    return store, WorkflowStore(database), run


class Provider:
    def generate(self, role, instructions, context, tick):
        tick()
        content = {
            "DEV": {"path": "budget.py", "content": "value = 2\n"},
            "DESIGNER": {"path": "guide.md", "content": "# Budget\n"},
            "QA": {"path": "test_budget.py", "content": "import unittest\n"},
        }
        return Draft(
            summary=role,
            deliverable=json.dumps({"files": [content[role]]})
            if role in content
            else "Reviewed context",
            tasks=[],
            input_tokens=4,
            output_tokens=3,
        )


class Sandbox:
    @staticmethod
    def new_name():
        return "ai-team-test-" + "a" * 32

    def run(self, bundle, tick, *, name):
        tick()
        return {"status": "passed", "artifact_digest": bundle.digest, "output": "1 test OK"}


def advance(store, queue):
    run = queue.claim()
    execute_repository(
        store,
        run,
        Provider(),
        lambda: None,
        Sandbox(),
        snapshot_reader=lambda policy: {"budget.py": "value = 1\n"},
    )


def test_real_state_machine_requires_digest_before_testing_and_delivery(setup):
    store, queue, run = setup
    for _ in range(5):
        advance(store, queue)
    view = store.view(run.id)
    assert view["run"]["stage"] == 5 and view["run"]["status"] == "awaiting_approval"
    assert view["state"]["diff"].find("+value = 2") >= 0
    with pytest.raises(HTTPException):
        store.decide(run.id, "0" * 64, True, "owner")
    store.decide(run.id, view["digest"], True, "owner")
    advance(store, queue)  # Docker result persisted separately from inference.
    advance(store, queue)  # CEO consolidates actual test result.
    view = store.view(run.id)
    assert view["state"]["test_result"]["status"] == "passed"
    assert view["run"]["status"] == "awaiting_approval"
    assert view["run"]["calls"] == 6
    assert view["state"]["proposal"]["base_sha"] == "a" * 40
    store.decide(run.id, view["digest"], True, "owner")
    assert store.view(run.id)["run"]["status"] == "completed"
    with pytest.raises(HTTPException):
        store.decide(run.id, view["digest"], True, "owner")


def test_cancelled_lease_cannot_persist_generated_files(setup):
    store, queue, run = setup
    claimed = queue.claim()
    queue.cancel(run.id, "owner")
    with pytest.raises(InterruptedError):
        store.save(claimed, {}, status="queued")
    assert store.view(run.id)["run"]["calls"] == 0


def test_nearly_exhausted_budget_does_not_start_another_paid_call(setup):
    store, queue, run = setup
    with store.database.session() as db:
        current = db.get(Run, run.id)
        current.input_tokens = 49000
        db.commit()
    claimed = queue.claim()
    with pytest.raises(RuntimeError):
        store.reserve(claimed)
    assert store.view(run.id)["run"]["calls"] == 0


def test_legacy_decision_cannot_bypass_repository_digest(setup):
    store, queue, run = setup
    for _ in range(5):
        advance(store, queue)
    with pytest.raises(HTTPException):
        queue.decide(run.id, 5, True, "owner")
    assert store.view(run.id)["run"]["status"] == "awaiting_approval"


def test_recovery_confirms_cleanup_without_repeating_uncertain_test(setup):
    store, queue, run = setup
    for _ in range(5):
        advance(store, queue)
    view = store.view(run.id)
    store.decide(run.id, view["digest"], True, "owner")
    claimed = queue.claim()
    state = dict(store.view(run.id)["state"])
    state.update(execution_started=True, container_name=Sandbox.new_name(), cleanup_confirmed=False)
    store.save(claimed, state, status="failed")
    cleaned = []

    class Cleaner:
        def cleanup(self, name):
            cleaned.append(name)

    assert store.recover(Cleaner())
    assert cleaned == [Sandbox.new_name()]
    assert store.view(run.id)["state"]["cleanup_confirmed"]
    assert store.view(run.id)["run"]["status"] == "failed"


def test_expired_running_sandbox_is_checked_before_another_admission(setup):
    store, queue, run = setup
    for _ in range(5):
        advance(store, queue)
    store.decide(run.id, store.view(run.id)["digest"], True, "owner")
    claimed = queue.claim()
    state = dict(store.view(run.id)["state"])
    state.update(execution_started=True, container_name=Sandbox.new_name(), cleanup_confirmed=False)
    store.save(claimed, state)
    with store.database.session() as db:
        db.get(Run, run.id).lease_expires_at = 1
        db.commit()

    class Unavailable:
        def cleanup(self, name):
            raise RuntimeError("Docker unavailable")

    assert not store.recover(Unavailable())
    assert not store.view(run.id)["state"]["cleanup_confirmed"]


def test_publication_requires_distinct_exact_approval_and_cannot_replay(setup):
    store, queue, run = setup
    for _ in range(5):
        advance(store, queue)
    with pytest.raises(HTTPException):
        store.request_publication(run.id, store.view(run.id)["digest"], "owner")
    store.decide(run.id, store.view(run.id)["digest"], True, "owner")
    advance(store, queue)
    advance(store, queue)
    store.decide(run.id, store.view(run.id)["digest"], True, "owner")
    view = store.view(run.id)
    with pytest.raises(HTTPException):
        store.request_publication(run.id, "0" * 64, "owner")
    store.request_publication(run.id, view["digest"], "owner")
    assert store.view(run.id)["state"]["delivery"]["status"] == "authorized"
    with pytest.raises(HTTPException):
        store.request_publication(run.id, view["digest"], "owner")


def test_approved_github_delivery_does_not_require_an_available_model(setup, monkeypatch):
    from test_repository_delivery import Client

    from ai_team.worker import Worker

    store, queue, run = setup
    for _ in range(5):
        advance(store, queue)
    store.decide(run.id, store.view(run.id)["digest"], True, "owner")
    advance(store, queue)
    advance(store, queue)
    store.decide(run.id, store.view(run.id)["digest"], True, "owner")
    store.request_publication(run.id, store.view(run.id)["digest"], "owner")
    client = Client()
    client.close = lambda: None
    monkeypatch.setattr("ai_team.github_client.GitHubClient", lambda: client)

    class UnavailableModel:
        def ready(self):
            return False

        def generate(self, *args):
            raise AssertionError("Publicação não deve chamar o modelo")

    settings = Settings(environment="test")
    assert Worker(store.database, settings, UnavailableModel()).once()
    view = store.view(run.id)
    assert view["run"]["status"] == "completed"
    assert view["state"]["delivery"]["status"] == "published"
    assert view["run"]["calls"] == 6
