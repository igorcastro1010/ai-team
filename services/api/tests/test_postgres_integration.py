"""Opt-in PostgreSQL checks: only a fresh, disposable ai_team_ci database in CI."""

import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from ai_team.auth import COOKIE_NAME, create_owner, digest
from ai_team.config import Settings
from ai_team.db import Database
from ai_team.hermes_jobs import HermesJobs, jobs_snapshot
from ai_team.hermes_journal import HermesJournal
from ai_team.hermes_monitor import ReconciliationStore
from ai_team.main import create_app
from ai_team.models import AuthSession, Base, Event, HermesAttempt, Owner, Project, Run, RunExecutor
from ai_team.repository_policy import RepositoryPolicy
from ai_team.repository_runs import RepositoryStore
from ai_team.workflow import WorkflowStore

pytestmark = pytest.mark.skipif(
    not os.environ.get("AI_TEAM_TEST_POSTGRES_URL"),
    reason="Requires explicit ephemeral PostgreSQL CI URL",
)


def test_v07_memory_restart_scope_and_optimizer_budget(postgres):
    from ai_team.memory_store import MemoryStore
    from ai_team.token_optimizer import OptimizerStore

    database, settings = postgres
    with database.session() as db:
        first, second = Project(name="Memory PG A"), Project(name="Memory PG B")
        db.add_all([first, second])
        db.commit()
    MemoryStore(database).put(first.id, "Decisão Python", "Workers Python privados.", "ci", "test")
    restarted = Database(settings)
    try:
        assert MemoryStore(restarted).search(first.id, "decisao")[0]["version"] == 1
        assert MemoryStore(restarted).search(second.id, "Python") == []
        optimizer = OptimizerStore(restarted)
        optimizer.set_budget(first.id, "project", "", 100, "test")
        admission = optimizer.reserve(first.id, "DEV", "synthetic-task", 80)
        optimizer.reconcile(admission, 20, 10)
        optimizer.reconcile(admission, 20, 10)
        project_budget = next(
            item for item in optimizer.summary(first.id)["budgets"] if item["scope"] == "project"
        )
        assert project_budget["used"] == 30 and project_budget["reserved"] == 0
    finally:
        restarted.engine.dispose()


def test_v07_postgres_concurrent_issue_dedup(postgres):
    from ai_team.issue_store import IssueStore

    database, _ = postgres
    with database.session() as db:
        project = Project(name="PG Issue dedup")
        db.add(project)
        db.commit()
    data = {
        "project_id": project.id,
        "request_id": "pg-duplicate",
        "title": "Revisar contrato local",
        "body": "Não publicar",
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: IssueStore(database).create(data, "test"), range(2)))
    assert results[0]["id"] == results[1]["id"]
    assert results[0]["action"]["status"] == "pending"


OWNER_PASSWORD = "ci-only-synthetic-password-2026"


def checked_url():
    if os.environ.get("CI") != "true" or os.environ.get("AI_TEAM_POSTGRES_CI") != "fresh-ephemeral":
        pytest.fail("PostgreSQL tests require both explicit CI safety markers", pytrace=False)
    try:
        url = make_url(os.environ["AI_TEAM_TEST_POSTGRES_URL"])
        valid = (
            url.drivername == "postgresql+psycopg"
            and url.database == "ai_team_ci"
            and url.host in {"127.0.0.1", "localhost", "::1"}
            and bool(url.username)
            and not url.query
        )
    except (KeyError, ValueError, ArgumentError):
        valid = False
    if not valid:
        pytest.fail("Refusing PostgreSQL target outside the disposable CI contract", pytrace=False)
    return url


@pytest.fixture(scope="module")
def postgres():
    url = checked_url()
    bootstrap = create_engine(url, connect_args={"connect_timeout": 5})
    app_password = secrets.token_urlsafe(32)
    try:
        with bootstrap.begin() as connection:
            # Check actual server identity and pre-existing data BEFORE any DDL.
            assert connection.scalar(text("SELECT current_database()")) == "ai_team_ci"
            occupied = connection.scalar(
                text("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_namespace WHERE nspname = 'ai_team'
                ) OR EXISTS (
                    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname NOT LIKE 'pg_%' AND n.nspname <> 'information_schema'
                    AND c.relkind IN ('r', 'p', 'f', 'm', 'v')
                ) OR EXISTS (
                    SELECT 1 FROM pg_roles WHERE rolname = 'ai_team_ci_app'
                )
            """)
            )
            if occupied:
                pytest.fail(
                    "Refusing a database/cluster with existing application state", pytrace=False
                )
            # CI admin only bootstraps a constrained login. Application queries never use superuser.
            connection.connection.driver_connection.execute(
                sql.SQL(
                    "CREATE ROLE ai_team_ci_app LOGIN PASSWORD {} "
                    "NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION"
                ).format(sql.Literal(app_password))
            )
            connection.execute(
                text("GRANT CONNECT, CREATE ON DATABASE ai_team_ci TO ai_team_ci_app")
            )
    finally:
        bootstrap.dispose()

    app_url = url.set(username="ai_team_ci_app", password=app_password).update_query_dict(
        {
            "connect_timeout": "5",
            "options": "-c statement_timeout=10000 -c lock_timeout=5000",
        }
    )
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=app_url.render_as_string(hide_password=False),
        public_origin="http://localhost:3000",
        hermes_url="",
        hermes_key="",
    )
    database = Database(settings)
    try:
        database.initialize()
        with database.session() as session:
            create_owner(session, "postgres-ci-owner", OWNER_PASSWORD)
        yield database, settings
    finally:
        # No DROP, TRUNCATE or data deletion. GitHub removes the disposable service.
        database.engine.dispose()


def running_run(database):
    with database.session() as session:
        project = Project(name="Synthetic PostgreSQL journal probe", mode="supervised")
        session.add(project)
        session.commit()
    store = WorkflowStore(database)
    run = store.create(
        project.id, "Synthetic CI draft only", "postgres-ci-owner", executor="hermes"
    )
    with database.session() as session:
        session.execute(
            update(Run)
            .where(Run.id == run.id)
            .values(
                status="running",
                lease_token=secrets.token_hex(16),
                lease_expires_at=int(time.time()) + 120,
            )
        )
        session.commit()
    return store.get(run.id)


def test_repository_checkpoint_and_digest_decision_use_real_postgres(postgres, tmp_path):
    database, _ = postgres
    with database.session() as session:
        project = Project(name="Repository CI checkpoint", mode="supervised")
        session.add(project)
        session.commit()
    store = RepositoryStore(database, root=tmp_path)
    policy = RepositoryPolicy(
        base_sha="a" * 40,
        directory="tools",
        read_paths=["budget.py"],
        write_paths=["budget.py", "test_budget.py", "guide.md"],
    )
    run = store.create(
        project.id, "CI database contract only", policy, "postgres-ci-owner", "codex"
    )
    with database.session() as session:
        session.execute(
            update(Run)
            .where(Run.id == run.id)
            .values(
                status="running",
                lease_token=secrets.token_hex(16),
                lease_expires_at=int(time.time()) + 120,
            )
        )
        session.commit()
    claimed = WorkflowStore(database).get(run.id)
    store.save(claimed, store.view(run.id)["state"], status="awaiting_approval", stage=1)
    view = store.view(run.id)
    approved = store.decide(run.id, view["digest"], True, "postgres-ci-owner")
    assert approved["run"]["status"] == "queued"
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        store.decide(run.id, view["digest"], True, "postgres-ci-owner")
    # Prevent this synthetic queued probe from interfering with subsequent queue tests.
    WorkflowStore(database).cancel(run.id, "postgres-ci-owner")


def test_private_schema_and_initialize_preserve_owner_and_rows(postgres):
    database, _ = postgres
    with database.session() as session:
        owner_hash = session.get(Owner, 1).password_hash
        sentinel = Project(name="Must survive repeated initialization")
        session.add(sentinel)
        session.commit()
    database.initialize()
    database.initialize()
    with database.session() as session:
        assert session.get(Project, sentinel.id).name == sentinel.name
        assert session.get(Owner, 1).password_hash == owner_hash
    with database.engine.connect() as connection:
        tables = set(
            connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'ai_team'"))
        )
        assert tables == set(Base.metadata.tables)
        assert (
            connection.scalar(
                text("""
            SELECT NOT EXISTS (
                SELECT 1 FROM pg_namespace n,
                LATERAL aclexplode(COALESCE(n.nspacl, acldefault('n', n.nspowner))) a
                WHERE n.nspname = 'ai_team' AND a.grantee = 0
                AND a.privilege_type IN ('USAGE', 'CREATE')
            )
        """)
            )
            is True
        )
        assert (
            connection.scalar(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user"))
            is False
        )


def test_authenticated_api_persists_executor_and_requires_consent_and_origin(postgres):
    database, settings = postgres
    with TestClient(create_app(settings, database)) as client:
        assert client.get("/projects").status_code == 401
        assert (
            client.post(
                "/auth/login",
                json={
                    "username": "postgres-ci-owner",
                    "password": OWNER_PASSWORD,
                },
            ).status_code
            == 403
        )
        headers = {"origin": settings.public_origin}
        assert (
            client.post(
                "/auth/login",
                headers=headers,
                json={
                    "username": "postgres-ci-owner",
                    "password": "wrong-synthetic-password",
                },
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/auth/login",
                headers=headers,
                json={
                    "username": "postgres-ci-owner",
                    "password": OWNER_PASSWORD,
                },
            ).status_code
            == 200
        )
        assert client.get("/auth/me").json() == {"username": "postgres-ci-owner"}
        with database.session() as session:
            token = client.cookies.get(COOKIE_NAME)
            assert session.get(AuthSession, digest(token)).owner_id == 1
        assert client.post("/projects", json={"name": "CSRF denied"}).status_code == 403
        response = client.post("/projects", headers=headers, json={"name": "PostgreSQL API CI"})
        assert response.status_code == 201
        project_id = response.json()["id"]
        payload = {
            "project_id": project_id,
            "prompt": "Synthetic text proposal",
            "executor": "hermes",
        }
        assert client.post("/runs", headers=headers, json=payload).status_code == 422
        assert (
            client.post("/runs", headers=headers, json=payload | {"consent": False}).status_code
            == 422
        )
        response = client.post("/runs", headers=headers, json=payload | {"consent": True})
        assert response.status_code == 201
        row = response.json()
        assert (row["executor"], row["scope"], row["status"], row["calls"]) == (
            "hermes",
            "draft_only",
            "queued",
            0,
        )
        assert client.get(f"/runs/{row['id']}").json()["executor"] == "hermes"
    database.engine.dispose()
    with database.session() as session:
        assert session.get(RunExecutor, row["id"]).executor == "hermes"
        legacy = Run(project_id=project_id, prompt="Synthetic legacy record", mode="manual")
        session.add(legacy)
        session.commit()
    assert WorkflowStore(database).get(legacy.id).executor == "codex"


def test_concurrent_same_stage_admission_has_one_durable_winner(postgres):
    database, _ = postgres
    run = running_run(database)
    journal = HermesJournal(database)
    barrier = Barrier(2, timeout=10)

    def admit(index):
        barrier.wait()
        try:
            return journal.begin(run, f"ai-team-pg-{run.id}-{index}").id
        except RuntimeError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(admit, range(2)))
    winner = [result for result in results if result is not None]
    assert len(winner) == 1
    database.engine.dispose()
    with database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(HermesAttempt)
                .where(
                    HermesAttempt.run_id == run.id,
                    HermesAttempt.stage == run.stage,
                )
            )
            == 1
        )
        assert session.get(HermesAttempt, winner[0]).bridge_status == "admitting"


def test_concurrent_terminal_observations_keep_atomic_largest_usage(postgres):
    database, _ = postgres
    run = running_run(database)
    journal = HermesJournal(database)
    attempt = journal.begin(run, f"ai-team-pg-{run.id}")
    journal.admitted(attempt.id, "synthetic_pg_remote_reference")
    journal.mark_stop(attempt.id, "requested")
    barrier = Barrier(3, timeout=10)

    def observe(tokens):
        barrier.wait()
        journal.observe(
            attempt.id,
            {
                "status": "completed",
                "usage": {"input_tokens": tokens, "output_tokens": tokens // 2},
            },
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(observe, [80, 4, 40]))
    for status in ("running", "cancelled"):
        journal.observe(
            attempt.id,
            {
                "status": status,
                "usage": {"input_tokens": 999, "output_tokens": 999},
            },
        )
    journal.observe(
        attempt.id,
        {
            "status": "completed",
            "usage": {"input_tokens": 1, "output_tokens": 1},
        },
    )
    database.engine.dispose()
    current = journal.get(attempt.id)
    assert (current.remote_status, current.input_tokens, current.output_tokens) == (
        "completed",
        80,
        40,
    )
    assert current.stop_status == "already_finished"


def test_cancelled_run_cannot_admit_or_create_journal_entry(postgres):
    database, _ = postgres
    run = running_run(database)
    WorkflowStore(database).cancel(run.id, "postgres-ci-owner")
    with pytest.raises(RuntimeError):
        HermesJournal(database).begin(run, f"ai-team-pg-{run.id}")
    with database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(HermesAttempt)
                .where(
                    HermesAttempt.run_id == run.id,
                )
            )
            == 0
        )


def test_monitor_lease_single_winner_and_stale_owner_cannot_finish(postgres):
    database, _ = postgres
    run = running_run(database)
    journal = HermesJournal(database)
    attempt = journal.begin(run, f"ai-team-pg-{run.id}")
    journal.admitted(attempt.id, "synthetic_pg_monitor")
    WorkflowStore(database).cancel(run.id, "postgres-ci-owner")
    barrier = Barrier(2, timeout=10)
    now = int(time.time())

    def claim(_):
        barrier.wait()
        return ReconciliationStore(database).claim(now=now)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    winners = [result for result in results if result is not None]
    assert len(winners) == 1 and winners[0].attempt_id == attempt.id
    original = winners[0]
    store = ReconciliationStore(database)
    replacement = store.claim(now=now + 91)
    assert replacement and replacement.token != original.token
    store.finish(original, now=now + 92, success=False)
    assert store.claim(now=now + 93) is None
    store.finish(replacement, now=now + 94, success=False)
    database.engine.dispose()
    assert store.state(attempt.id)["failures"] == 1
    assert store.state(attempt.id)["next_poll_at"] == now + 154


def test_repository_usage_duplicate_reports_are_atomic_on_postgres(postgres):
    database, _ = postgres
    run = running_run(database)
    with database.session() as session:
        session.execute(update(Run).where(Run.id == run.id).values(scope="repository_code"))
        session.commit()
    WorkflowStore(database).cancel(run.id, "postgres-ci-owner")
    barrier = Barrier(2, timeout=10)
    store = RepositoryStore(database)

    def report(_):
        barrier.wait()
        store.record_usage(run, 123, 45)

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(report, range(2)))
    current = WorkflowStore(database).get(run.id)
    assert (current.input_tokens, current.output_tokens) == (123, 45)
    assert current.status == "cancelled" and current.lease_token == ""
    with database.session() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Event)
                .where(
                    Event.resource_id == run.id,
                    Event.kind == "repository.usage",
                )
            )
            == 1
        )


def test_jobs_inventory_and_pause_evidence_survive_postgres_reconnect(postgres):
    database, _ = postgres
    native = {
        "id": "abcdef123456",
        "name": "Synthetic PG job",
        "enabled": True,
        "state": "scheduled",
        "schedule": {"kind": "interval"},
    }
    calls = []

    class Reader:
        configured = True

        def request(self, method, path, **kwargs):
            calls.append((method, path))
            if method == "POST":
                assert path == "/api/jobs/abcdef123456/pause"
                native.update(enabled=False, state="paused")
            return {"jobs": [dict(native)]} if "?" in path else {"job": dict(native)}

    operations = HermesJobs(database, Reader())
    assert operations.inspect("postgres-ci-owner")["items"][0]["enabled"]
    assert operations.pause(native["id"], "postgres-ci-owner")["status"] == "confirmed"
    database.engine.dispose()
    snapshot = jobs_snapshot(database)
    assert snapshot["last_pause"]["status"] == "confirmed"
    assert snapshot["items"][0]["state"] == "paused"
    # An externally resumed schedule is visible after a newer inventory read.
    native.update(enabled=True, state="scheduled")
    assert operations.inspect("postgres-ci-owner")["items"][0]["enabled"]
    assert [entry for entry in calls if entry[0] == "POST"] == [
        ("POST", "/api/jobs/abcdef123456/pause")
    ]


def test_hermes_cooldown_survives_postgres_reconnect_and_blocks_http(postgres):
    import httpx

    from ai_team.hermes import HermesClient, HermesRateLimitError

    database, _ = postgres
    journal = HermesJournal(database)
    journal.record_cooldown(120)
    database.engine.dispose()
    assert HermesJournal(database).cooldown_remaining() >= 115
    settings = Settings(hermes_url="http://hermes:8642", hermes_key="x" * 40)
    client = HermesClient(
        settings,
        database=database,
        transport=httpx.MockTransport(lambda _: pytest.fail("HTTP admission")),
    )
    with pytest.raises(HermesRateLimitError):
        client.request("POST", "/v1/runs")
