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
