import pytest
from fastapi import HTTPException

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.hermes_journal import HermesJournal
from ai_team.models import Project
from ai_team.workflow import WorkflowStore


@pytest.fixture
def journal(tmp_path):
    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'journal.db'}"))
    database.initialize()
    with database.session() as db:
        project = Project(name="Journal", mode="supervised")
        db.add(project)
        db.commit()
    store = WorkflowStore(database)
    created = store.create(project.id, "Proponha um plano verificável.", "owner", executor="hermes")
    claimed = store.claim()
    assert created.id == claimed.id
    return HermesJournal(database), claimed


def test_admission_identity_is_durable_and_stage_cannot_be_readmitted(journal):
    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    assert attempt.remote_id == ""
    assert store.get(attempt.id).admission_key == "ai-team-unique"
    with pytest.raises(RuntimeError):
        store.begin(run, "ai-team-different")
    store.database.engine.dispose()
    assert store.get(attempt.id).bridge_status == "admitting"


def test_cancelled_or_wrong_lease_cannot_admit(journal):
    store, run = journal
    WorkflowStore(store.database).cancel(run.id, "owner")
    with pytest.raises(RuntimeError):
        store.begin(run, "ai-team-unique")


def test_remote_reference_usage_and_terminal_status_do_not_regress(journal):
    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    store.admitted(attempt.id, "run_native_1")
    store.observe(
        attempt.id,
        {
            "run_id": "run_native_1",
            "status": "completed",
            "usage": {
                "input_tokens": 10,
                "output_tokens": 4,
                "extra_secret": "not-stored",
            },
            "output": "private-output",
        },
    )
    store.observe(attempt.id, {"status": "running"})
    current = store.get(attempt.id)
    assert current.remote_status == "completed"
    assert (current.input_tokens, current.output_tokens) == (10, 4)
    view = store.view(current)
    assert "private-output" not in str(view)
    assert "not-stored" not in str(view)
    assert "ai-team-unique" not in str(view)


def test_missing_usage_is_unknown_and_stop_is_not_assumed_confirmed(journal):
    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    store.admitted(attempt.id, "run_native_1")
    store.mark_stop(attempt.id, "requested")
    current = store.get(attempt.id)
    assert current.input_tokens is None
    assert current.stop_status == "requested"
    store.observe(attempt.id, {"status": "cancelled"})
    assert store.get(attempt.id).stop_status == "confirmed"


def test_unknown_admission_and_stop_errors_remain_auditable(journal):
    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    store.finish(attempt.id, "uncertain")
    assert store.get(attempt.id).bridge_status == "uncertain"
    assert store.get(attempt.id).remote_id == ""
    store.mark_stop(attempt.id, "uncertain")
    assert store.get(attempt.id).stop_status == "uncertain"


@pytest.mark.parametrize("remote_id", ["../admin", "run/a", "", "x" * 161])
def test_invalid_remote_identifiers_are_never_stored(journal, remote_id):
    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    with pytest.raises(ValueError):
        store.admitted(attempt.id, remote_id)


def test_cursor_is_validated_and_existing_rows_survive_initialize(journal):
    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    store.database.initialize()
    assert store.page()["items"][0]["id"] == attempt.id
    assert store.page(before=attempt.id)["items"] == []
    with pytest.raises(HTTPException) as error:
        store.page(before="missing")
    assert error.value.status_code == 404


def test_bound_provider_records_real_remote_reference_and_reported_usage(journal):
    from test_hermes import run_client

    from ai_team.hermes import HermesProvider

    store, run = journal
    client, calls = run_client()
    provider = HermesProvider(client).for_run(store.database, run)
    result = provider.generate("CEO", "Plan", {}, lambda: None)
    view = store.page()["items"][0]
    assert view["remote_id"] == "run_test"
    assert view["bridge_status"] == "succeeded"
    assert view["remote_status"] == "completed"
    assert view["input_tokens"] == result.input_tokens == 12
    assert calls.count(("POST", "/v1/runs")) == 1


def test_lost_admission_response_keeps_identity_and_never_readmits(journal):
    import httpx
    from test_hermes import settings

    from ai_team.hermes import HermesClient, HermesProvider

    store, run = journal
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/v1/toolsets":
            return httpx.Response(
                200, json={"object": "list", "platform": "api_server", "data": []}
            )
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json={"object": "hermes.api_server.capabilities"})
        raise httpx.ReadTimeout("private error must not persist")

    client = HermesClient(settings(), transport=httpx.MockTransport(handler))
    provider = HermesProvider(client).for_run(store.database, run)
    with pytest.raises(httpx.ReadTimeout):
        provider.generate("CEO", "Plan", {}, lambda: None)
    attempt = store.page()["items"][0]
    assert attempt["bridge_status"] == "uncertain"
    assert not attempt["remote_id"]
    with pytest.raises(RuntimeError):
        provider.generate("CEO", "Plan", {}, lambda: None)
    assert calls.count(("POST", "/v1/runs")) == 1
    assert "private error" not in str(store.page())


def test_two_workers_cannot_reserve_same_stage_twice(journal):
    from concurrent.futures import ThreadPoolExecutor

    store, run = journal

    def admit(index):
        try:
            store.begin(run, f"ai-team-{index}")
            return True
        except RuntimeError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(admit, range(2))) == 1
    assert len(store.page()["items"]) == 1


def test_late_completed_response_does_not_confirm_cancellation(journal):
    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    store.admitted(attempt.id, "run_native_1")
    store.mark_stop(attempt.id, "requested")
    store.observe(attempt.id, {"status": "completed"})
    assert store.get(attempt.id).stop_status == "already_finished"
    store.observe(attempt.id, {"status": "cancelled"})
    assert store.get(attempt.id).remote_status == "completed"
    assert store.get(attempt.id).stop_status == "already_finished"


def test_provider_records_uncertain_stop_after_cancellation(journal):
    import httpx
    from test_hermes import settings

    from ai_team.hermes import HermesClient, HermesProvider

    store, run = journal

    def handler(request):
        if request.url.path == "/v1/toolsets":
            return httpx.Response(
                200, json={"object": "list", "platform": "api_server", "data": []}
            )
        if request.url.path == "/v1/capabilities":
            return httpx.Response(200, json={"object": "hermes.api_server.capabilities"})
        if request.url.path == "/v1/runs":
            return httpx.Response(202, json={"run_id": "native_1"})
        if request.url.path.endswith("/stop"):
            raise httpx.ConnectError("private stop error")
        raise AssertionError("No poll after cancellation")

    client = HermesClient(settings(), transport=httpx.MockTransport(handler))
    calls = 0

    def tick():
        nonlocal calls
        calls += 1
        if calls >= 3:
            raise InterruptedError()

    with pytest.raises(InterruptedError):
        HermesProvider(client).for_run(store.database, run).generate("CEO", "Plan", {}, tick)
    row = store.page()["items"][0]
    assert row["remote_id"] == "native_1"
    assert row["bridge_status"] == "interrupted"
    assert row["stop_status"] == "uncertain"


def test_history_cursor_covers_all_rows_with_equal_timestamps(journal):
    from ai_team.models import HermesAttempt, Run

    store, original = journal
    with store.database.session() as db:
        for index in range(55):
            run = Run(project_id=original.project_id, prompt="Synthetic history", mode="manual")
            db.add(run)
            db.flush()
            db.add(
                HermesAttempt(
                    run_id=run.id, stage=0, admission_key=f"ai-team-page-{index}", created_at=100
                )
            )
        db.commit()
    first = store.page()
    assert len(first["items"]) == 50
    second = store.page(before=first["next_cursor"])
    assert len(second["items"]) == 5
    assert second["next_cursor"] is None
    assert len({row["id"] for row in first["items"] + second["items"]}) == 55


def test_reconciliation_fills_usage_after_terminal_observation(journal):
    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    store.admitted(attempt.id, "native_1")
    store.observe(attempt.id, {"status": "completed"})
    assert store.get(attempt.id).input_tokens is None
    store.observe(
        attempt.id,
        {
            "status": "completed",
            "usage": {
                "input_tokens": 30,
                "output_tokens": 10,
            },
        },
    )
    assert store.get(attempt.id).input_tokens == 30
    assert store.get(attempt.id).output_tokens == 10


def test_late_active_observation_cannot_regress_status_or_token_totals(journal):
    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    store.admitted(attempt.id, "native_1")
    store.observe(
        attempt.id,
        {
            "status": "running",
            "usage": {
                "input_tokens": 20,
                "output_tokens": 5,
            },
        },
    )
    store.observe(
        attempt.id,
        {
            "status": "queued",
            "usage": {
                "input_tokens": 1,
                "output_tokens": 0,
            },
        },
    )
    assert store.get(attempt.id).remote_status == "running"
    assert store.get(attempt.id).input_tokens == 20
    store.observe(
        attempt.id,
        {
            "status": "completed",
            "usage": {
                "input_tokens": 30,
                "output_tokens": 10,
            },
        },
    )
    store.observe(
        attempt.id,
        {
            "status": "completed",
            "usage": {
                "input_tokens": 2,
                "output_tokens": 1,
            },
        },
    )
    assert store.get(attempt.id).remote_status == "completed"
    assert store.get(attempt.id).input_tokens == 30
    assert store.get(attempt.id).output_tokens == 10


def test_concurrent_reconciliation_keeps_largest_reported_usage(journal):
    from concurrent.futures import ThreadPoolExecutor

    store, run = journal
    attempt = store.begin(run, "ai-team-unique")
    store.admitted(attempt.id, "native_1")

    def observe(tokens):
        store.observe(
            attempt.id,
            {
                "status": "completed",
                "usage": {
                    "input_tokens": tokens,
                    "output_tokens": tokens // 2,
                },
            },
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(observe, [50, 10, 30]))
    row = store.get(attempt.id)
    assert row.input_tokens == 50
    assert row.output_tokens == 25
