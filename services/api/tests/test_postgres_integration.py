"""Opt-in PostgreSQL checks: only a fresh, disposable ai_team_ci database in CI."""

import os
import secrets
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

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


def test_v09_factory_checkpoints_restart_and_scope(postgres):
    from ai_team.content_factory import FactoryStore, FactoryWorker, ProductionInput

    database, settings = postgres
    with database.session() as db:
        project = Project(name="Factory PG")
        db.add(project)
        db.commit()
        project_id = project.id
    data = ProductionInput(project_id=project_id, request_id=uuid4(),
                           prompt="Vídeo local com minha logo e aprovação humana")
    store = FactoryStore(database)
    job = store.create(data)
    assert store.create(data)["id"] == job["id"]
    for _ in range(3):
        FactoryWorker(store).once()
    restarted = Database(settings)
    try:
        result = FactoryStore(restarted).get(project_id, job["id"])
        assert result["status"] == "waiting_media"
        assert len(result["steps"]) == 3
        FactoryStore(restarted).cancel(project_id, job["id"])
        assert not FactoryWorker(FactoryStore(restarted)).once()
    finally:
        restarted.engine.dispose()


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


def test_v08_preferences_and_concurrent_request_identity_survive_postgres_restart(postgres):
    from fastapi import HTTPException

    from ai_team.model_center import ModelCenter, Preference
    from ai_team.model_center_models import ModelRequest

    database, settings = postgres
    with database.session() as session:
        first, second = Project(name="V08 central PG A"), Project(name="V08 central PG B")
        session.add_all([first, second])
        session.commit()
    center = ModelCenter(database)
    center.configure(
        first.id,
        "CEO",
        Preference(mode="manual", provider="codex", model="codex-supervised"),
        "postgres-ci-owner",
    )
    assert not center.preference(first.id, "CEO")["enabled"]
    assert center.preference(second.id, "CEO")["provider"] == "gemini"
    assert center.preference(first.id, "QA")["provider"] == "gemini"
    barrier = Barrier(2, timeout=10)

    def request(_):
        barrier.wait()
        return center.request(first.id, "pg-v08-duplicate", "Proposta textual sem inferência", "ci")

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(request, range(2)))
    assert outcomes[0].id == outcomes[1].id
    assert outcomes[0].executor == "central" and outcomes[0].calls == 0
    with pytest.raises(HTTPException) as conflict:
        center.request(first.id, "pg-v08-duplicate", "Conteúdo diferente deve ser rejeitado", "ci")
    assert conflict.value.status_code == 409
    other = center.request(second.id, "pg-v08-duplicate", "Proposta textual sem inferência", "ci")
    assert other.id != outcomes[0].id
    database.engine.dispose()
    restarted = Database(settings)
    try:
        restored = ModelCenter(restarted)
        assert restored.preference(first.id, "CEO")["provider"] == "codex"
        assert restored.preference(second.id, "CEO")["provider"] == "gemini"
        assert (
            restored.request(
                first.id, "pg-v08-duplicate", "Proposta textual sem inferência", "ci"
            ).id
            == outcomes[0].id
        )
        with restarted.session() as session:
            assert (
                session.scalar(
                    select(func.count())
                    .select_from(ModelRequest)
                    .where(
                        ModelRequest.project_id == first.id,
                        ModelRequest.request_id == "pg-v08-duplicate",
                    )
                )
                == 1
            )
    finally:
        restarted.engine.dispose()
        for run in (outcomes[0], other):
            WorkflowStore(database).cancel(run.id, "postgres-ci-owner")


def test_v08_cloud_admission_serializes_two_rpm_across_postgres_projects(postgres, monkeypatch):
    from ai_team.gemini import GeminiClient
    from ai_team.model_center import CentralDeferred, ModelCenter, Preference
    from ai_team.model_center_models import ModelCall

    # Admission is a local transaction only. Any accidental provider access must fail.
    def no_provider(*args, **kwargs):
        pytest.fail("Provider access forbidden in PostgreSQL admission checks")

    monkeypatch.setattr(GeminiClient, "check", no_provider)
    monkeypatch.setattr(GeminiClient, "generate", no_provider)
    database, _ = postgres
    with database.session() as session:
        projects = [Project(name=f"V08 shared quota PG {index}") for index in range(3)]
        session.add_all(projects)
        session.commit()
    center = ModelCenter(database)
    policy = Preference(enabled=True, quotas_confirmed=True, rpm=2)
    runs = []
    for index, project in enumerate(projects):
        center.configure(project.id, "CEO", policy, "ci")
        runs.append(center.request(project.id, f"quota-{index}", "Proposta sintética local", "ci"))
    cloud = f"synthetic-pg-{secrets.token_hex(8)}"
    barrier = Barrier(3, timeout=10)

    def admit(run):
        barrier.wait()
        try:
            return center.admit(run, "CEO", cloud, 1000)
        except CentralDeferred as deferred:
            assert deferred.status == "waiting_quota"
            return None

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            outcomes = list(pool.map(admit, runs))
        assert sum(outcome is not None for outcome in outcomes) == 2
        with database.session() as session:
            admitted = session.scalars(
                select(ModelCall).where(
                    ModelCall.cloud_project == cloud, ModelCall.admitted.is_(True)
                )
            ).all()
            assert len(admitted) == 2
            assert len({row.project_id for row in admitted}) == 2
            assert all(row.status == "started" for row in admitted)
            assert all(row.input_tokens is None and row.output_tokens is None for row in admitted)
        # Reconnection cannot release already reserved shared quota or duplicate a stage.
        database.engine.dispose()
        with pytest.raises(CentralDeferred):
            center.admit(runs[0], "CEO", cloud, 1000)
        assert sum(len(center.snapshot(project.id)["history"]) for project in projects) >= 3
    finally:
        for run in runs:
            WorkflowStore(database).cancel(run.id, "postgres-ci-owner")


def test_v08_video_digest_approval_and_single_claim_persist_on_postgres(postgres):
    import uuid

    from fastapi import HTTPException

    from ai_team.video_routes import VideoInput
    from ai_team.video_store import VideoStore

    database, settings = postgres
    with database.session() as session:
        first, second = Project(name="V08 video PG A"), Project(name="V08 video PG B")
        session.add_all([first, second])
        session.commit()
    store = VideoStore(database)
    data = VideoInput(
        project_id=first.id,
        request_id=str(uuid.uuid4()),
        title="Roteiro PG sintético",
        format="vertical",
        scenes=[{"text": "Sem renderização neste teste", "duration": 2}],
        consent=True,
    )
    created = store.create(data)
    assert created["status"] == "pending_approval" and len(created["digest"]) == 64
    assert store.create(data)["id"] == created["id"]
    with pytest.raises(HTTPException) as conflict:
        store.create(data.model_copy(update={"title": "Outro roteiro"}))
    assert conflict.value.status_code == 409
    with pytest.raises(HTTPException) as stale:
        store.decide(created["id"], "0" * 64, True)
    assert stale.value.status_code == 409
    assert store.get(created["id"])["status"] == "pending_approval"
    assert store.snapshot(second.id)["items"] == []
    assert store.claim() is None
    assert store.decide(created["id"], created["digest"], True)["status"] == "queued"
    database.engine.dispose()
    restarted = Database(settings)
    try:
        restored = VideoStore(restarted)
        assert restored.get(created["id"])["digest"] == created["digest"]
        assert restored.snapshot(first.id)["items"][0]["status"] == "queued"
        barrier = Barrier(2, timeout=10)

        def claim(_):
            barrier.wait()
            return restored.claim()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(claim, range(2)))
        claims = [item for item in outcomes if item is not None]
        assert len(claims) == 1 and claims[0]["id"] == created["id"]
        token = claims[0]["lease_token"]
        assert restored.active(created["id"], token)
        restored.cancel(created["id"])
        assert not restored.active(created["id"], token)
        assert not restored.finish(created["id"], token, "completed")
        assert restored.get(created["id"])["status"] == "cancelled"
    finally:
        restarted.engine.dispose()


def test_v08_private_tables_and_model_probe_survive_reinitialization(postgres):
    from ai_team.model_center_models import (
        ModelCall,
        ModelPreference,
        ModelProbe,
        ModelProviderState,
        ModelRequest,
    )
    from ai_team.video_models import VideoJob

    database, _ = postgres
    expected = {
        model.__tablename__
        for model in (
            ModelCall,
            ModelPreference,
            ModelProbe,
            ModelProviderState,
            ModelRequest,
            VideoJob,
        )
    }
    assert expected <= set(Base.metadata.tables)
    with database.session() as session:
        project = Project(name="V08 private probe PG")
        session.add(project)
        session.flush()
        probe = ModelProbe(project_id=project.id, status="queued")
        session.add(probe)
        session.commit()
    database.engine.dispose()
    database.initialize()
    with database.session() as session:
        assert session.get(ModelProbe, probe.id).project_id == project.id
        assert session.get(ModelProbe, probe.id).status == "queued"
    with database.engine.connect() as connection:
        private_tables = set(
            connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'ai_team'"))
        )
        public_tables = set(
            connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        )
        assert expected <= private_tables
        assert not expected.intersection(public_tables)


def test_v081_studio_draft_concurrency_and_templates_survive_restart(postgres):
    from fastapi import HTTPException

    from ai_team.video_studio_routes import StudioStore

    database, settings = postgres
    with database.session() as db:
        project = Project(name="V081 studio private PG")
        other = Project(name="V081 isolated PG")
        db.add_all([project, other])
        db.commit()
    store = StudioStore(database)
    document = {
        "title": "Rascunho PG",
        "format": "square",
        "scenes": [{"text": "Cena persistente", "duration": 2}],
    }
    barrier = Barrier(2, timeout=10)

    def save(_):
        barrier.wait()
        try:
            return store.save_draft(project.id, 0, document)["revision"]
        except HTTPException as error:
            assert error.status_code == 409
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(save, range(2))).count(1) == 1
    template = store.save_template(project.id, "Meu template PG", document)
    database.engine.dispose()
    restarted = Database(settings)
    try:
        restored = StudioStore(restarted)
        assert restored.draft(project.id)["revision"] == 1
        assert restored.draft(project.id)["document"]["format"] == "square"
        assert restored.draft(other.id)["document"] is None
        assert template in restored.templates(project.id)["items"]
        assert template not in restored.templates(other.id)["items"]
    finally:
        restarted.engine.dispose()
