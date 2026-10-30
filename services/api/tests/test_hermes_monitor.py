import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.hermes_journal import HermesJournal
from ai_team.hermes_monitor import HermesMonitor, ReconciliationStore
from ai_team.models import Project
from ai_team.workflow import WorkflowStore


@pytest.fixture
def pending(tmp_path):
    settings = Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'monitor.db'}")
    database = Database(settings)
    database.initialize()
    with database.session() as db:
        project = Project(name="Monitor", mode="supervised")
        db.add(project)
        db.commit()
    workflow = WorkflowStore(database)
    workflow.create(project.id, "Planeje a revisão.", "owner", executor="hermes")
    run = workflow.claim()
    journal = HermesJournal(database)
    attempt = journal.begin(run, "ai-team-monitor-test")
    journal.admitted(attempt.id, "native_monitor")
    return database, settings, run, attempt


class Reader:
    configured = True

    def __init__(self, *, failure=False):
        self.calls = []
        self.failure = failure

    def request(self, method, path):
        self.calls.append((method, path))
        assert method == "GET"  # Monitor cannot admit, stop, resume or run a model.
        if self.failure:
            raise RuntimeError("private-provider-token")
        return {"status": "completed", "usage": {"input_tokens": 10, "output_tokens": 4}}


def test_live_worker_is_never_polled_by_reconciler(pending):
    database, settings, _, _ = pending
    reader = Reader()
    assert not HermesMonitor(database, settings, reader).once(now=int(time.time()))
    assert reader.calls == []


def test_cancelled_run_is_observed_without_readmission_or_stop(pending):
    database, settings, run, attempt = pending
    WorkflowStore(database).cancel(run.id, "owner")
    reader = Reader()
    monitor = HermesMonitor(database, settings, reader)
    assert monitor.once(now=1000)
    assert reader.calls == [("GET", "/v1/runs/native_monitor")]
    assert HermesJournal(database).get(attempt.id).remote_status == "completed"
    assert WorkflowStore(database).get(run.id).status == "cancelled"
    assert not monitor.once(now=2000)


def test_expired_local_lease_can_be_reconciled(pending):
    database, settings, run, _ = pending
    reader = Reader()
    assert HermesMonitor(database, settings, reader).once(now=run.lease_expires_at + 1)
    assert len(reader.calls) == 1


def test_failed_observation_backoff_and_redaction(pending):
    database, settings, run, attempt = pending
    WorkflowStore(database).cancel(run.id, "owner")
    reader = Reader(failure=True)
    monitor = HermesMonitor(database, settings, reader)
    assert monitor.once(now=1000)
    assert not monitor.once(now=1001)
    assert monitor.once(now=1060)
    assert len(reader.calls) == 2
    store = ReconciliationStore(database)
    state = store.state(attempt.id)
    assert state["failures"] == 2
    assert state["next_poll_at"] == 1180
    assert "private-provider-token" not in str(state)
    assert HermesJournal(database).get(attempt.id).remote_status == "started"
    database.engine.dispose()
    assert store.state(attempt.id)["next_poll_at"] == 1180


def test_disjoint_leases_across_monitor_processes(pending):
    database, _, run, _ = pending
    WorkflowStore(database).cancel(run.id, "owner")

    def claim(_):
        return ReconciliationStore(database).claim(now=1000)

    with ThreadPoolExecutor(max_workers=2) as pool:
        leases = list(pool.map(claim, range(2)))
    assert sum(lease is not None for lease in leases) == 1
    # A crashed monitor's lease can be taken over after its bounded expiry.
    assert ReconciliationStore(database).claim(now=1091) is not None


def test_missing_configuration_does_not_query_or_mark_worker_online(pending):
    database, settings, run, _ = pending
    WorkflowStore(database).cancel(run.id, "owner")
    reader = Reader()
    reader.configured = False
    assert not HermesMonitor(database, settings, reader).once(now=1000)
    assert not reader.calls
    assert not WorkflowStore(database).usage()["worker_online"]
    assert (
        ReconciliationStore(database).snapshot(now=1000)["connection"]["status"] == "not_configured"
    )


def test_a_stale_monitor_cannot_release_a_new_lease(pending):
    database, _, run, attempt = pending
    WorkflowStore(database).cancel(run.id, "owner")
    store = ReconciliationStore(database)
    old = store.claim(now=1000)
    fresh = store.claim(now=1091)
    assert fresh.token != old.token
    store.finish(old, now=1092, success=False)
    assert store.state(attempt.id)["last_polled_at"] is None
    assert store.claim(now=1093) is None
    store.finish(fresh, now=1094, success=True)
    assert store.state(attempt.id)["last_polled_at"] == 1094


def test_terminal_or_unidentified_attempt_never_generates_a_request(pending):
    database, settings, run, attempt = pending
    WorkflowStore(database).cancel(run.id, "owner")
    journal = HermesJournal(database)
    journal.observe(attempt.id, {"status": "failed"})
    reader = Reader()
    assert not HermesMonitor(database, settings, reader).once(now=1000)
    assert not reader.calls


def test_monitor_process_exits_without_inference_when_not_configured(tmp_path):
    import os
    import subprocess
    import sys

    from ai_team.models import ProviderObservation

    path = tmp_path / "process.db"
    database_url = f"sqlite:///{path}"
    result = subprocess.run(
        [sys.executable, "-m", "ai_team.hermes_monitor", "--once"],
        env=os.environ
        | {
            "AI_TEAM_ENVIRONMENT": "test",
            "AI_TEAM_DATABASE_URL": database_url,
            "AI_TEAM_HERMES_URL": "",
            "AI_TEAM_HERMES_KEY": "",
        },
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0
    database = Database(Settings(environment="test", database_url=database_url))
    with database.session() as db:
        assert db.get(ProviderObservation, "hermes-monitor").details["status"] == "not_configured"
    assert not WorkflowStore(database).usage()["worker_online"]
