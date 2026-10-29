from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Project, Run


@pytest.fixture
def database(tmp_path):
    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'schedules.db'}"))
    database.initialize()
    with database.session() as db:
        db.add(Project(id="project", name="Agendas", mode="manual"))
        db.commit()
    return database


def payload(**changes):
    return {
        "project_id": "project",
        "prompt": "Planeje uma revisão de acessibilidade.",
        "mode": "automatic",
        "interval_seconds": 3600,
        "starts_at": 1100,
        "max_runs": 2,
        "consent": True,
        **changes,
    }


def test_schedule_validates_limits_and_consent_before_persisting(database):
    from ai_team.schedules import ScheduleStore

    store = ScheduleStore(database)
    for changes in [
        dict(consent=False),
        dict(max_runs=6),
        dict(interval_seconds=30),
        dict(starts_at=999),
        dict(starts_at=1000 + 8 * 86400),
        dict(mode="shell"),
        dict(scope="github_write"),
    ]:
        with pytest.raises((ValueError, HTTPException)):
            store.create(payload(**changes), "owner", now=1000)
    assert store.all() == []
    with pytest.raises(HTTPException) as error:
        store.create(payload(project_id="missing"), "owner", now=1000)
    assert error.value.status_code == 404


def test_two_schedulers_queue_exactly_once_and_never_overlap(database):
    from ai_team.schedules import ScheduleStore

    store = ScheduleStore(database)
    schedule = store.create(payload(), "owner", now=1000)
    assert store.tick(now=1099) == 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: store.tick(now=1100), range(2)))
    assert sum(results) == 1
    with database.session() as db:
        run = db.scalar(select(Run))
        assert run.mode == "automatic" and run.scope == "draft_only"
        assert run.calls == 0 and run.status == "queued"
        run.status = "awaiting_approval"
        db.commit()
    assert store.tick(now=10000) == 0
    with database.session() as db:
        run = db.scalar(select(Run))
        run.status = "completed"
        db.commit()
    assert store.tick(now=10000) == 1
    assert store.tick(now=20000) == 0
    final = store.get(schedule.id)
    assert final.emitted == 2 and final.status == "completed"
    with database.session() as db:
        assert db.scalar(select(func.count()).select_from(Run)) == 2


def test_restart_skips_missed_intervals_and_cancel_preserves_authorized_run(database):
    from ai_team.schedules import ScheduleStore

    store = ScheduleStore(database)
    schedule = store.create(payload(max_runs=5), "owner", now=1000)
    assert ScheduleStore(database).tick(now=10000) == 1
    assert store.get(schedule.id).next_run_at == 13600
    store.cancel(schedule.id, "owner")
    assert store.tick(now=20000) == 0
    with database.session() as db:
        assert db.scalar(select(Run)).status == "queued"
    with pytest.raises(HTTPException) as error:
        store.cancel(schedule.id, "owner")
    assert error.value.status_code == 409


def test_expired_schedule_cannot_queue_and_partial_transaction_rolls_back(database, monkeypatch):
    from ai_team.schedules import ScheduleStore

    store = ScheduleStore(database)
    schedule = store.create(payload(), "owner", now=1000)
    assert store.tick(now=1000 + 31 * 86400) == 0
    assert store.get(schedule.id).status == "expired"
    schedule = store.create(payload(), "owner", now=1000)
    from sqlalchemy.orm import Session

    original = Session.add

    def fail_on_run(self, item, *args, **kwargs):
        if isinstance(item, Run):
            raise RuntimeError("synthetic storage failure")
        return original(self, item, *args, **kwargs)

    monkeypatch.setattr(Session, "add", fail_on_run)
    with pytest.raises(RuntimeError):
        store.tick(now=1100)
    assert store.get(schedule.id).emitted == 0
    assert store.get(schedule.id).next_run_at == 1100


def test_busy_schedules_do_not_starve_new_due_requests(database):
    from ai_team.schedules import ScheduleStore

    store = ScheduleStore(database)
    for _ in range(20):
        store.create(payload(mode="manual"), "owner", now=1000)
    assert store.tick(now=1100) == 20
    with database.session() as db:
        for run in db.scalars(select(Run)):
            run.status = "awaiting_approval"
        db.commit()
    new = store.create(payload(starts_at=5000), "owner", now=4900)
    assert store.tick(now=5000) == 1
    assert store.get(new.id).emitted == 1


def test_cancel_racing_scheduler_prevents_any_later_dispatch(database):
    from ai_team.schedules import ScheduleStore

    store = ScheduleStore(database)
    for index in range(5):
        now = 1000 + index * 100
        schedule = store.create(payload(starts_at=now + 10), "owner", now=now)
        with ThreadPoolExecutor(max_workers=2) as pool:
            dispatch = pool.submit(store.tick, now=now + 10)
            cancellation = pool.submit(store.cancel, schedule.id, "owner")
            dispatch.result()
            cancellation.result()
        final = store.get(schedule.id)
        assert final.status == "cancelled" and final.emitted in (0, 1)
        before = final.emitted
        store.tick(now=now + 10000)
        assert store.get(schedule.id).emitted == before


def test_generated_run_uses_existing_worker_and_retains_authorized_mode(database):
    from test_workflow import TestProvider

    from ai_team.models import ScheduleOccurrence
    from ai_team.schedules import ScheduleStore
    from ai_team.worker import Worker
    from ai_team.workflow import WorkflowStore

    store = ScheduleStore(database)
    store.create(payload(), "owner", now=1000)
    store.tick(now=1100)
    worker = Worker(database, Settings(environment="test"), TestProvider())
    for _ in range(5):
        assert worker.once()
    run = WorkflowStore(database).all()[0]
    assert run.status == "completed" and run.calls == 5 and len(run.steps) == 5
    with database.session() as db:
        assert db.scalar(select(ScheduleOccurrence)).run_id == run.id
    assert store.tick(now=10000) == 1
