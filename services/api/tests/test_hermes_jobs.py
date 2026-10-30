import httpx
import pytest
from fastapi import HTTPException

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.hermes import HermesClient
from ai_team.hermes_jobs import HermesJobs, jobs_snapshot
from ai_team.models import ProviderObservation

JOB_ID = "abcdef123456"


def native_job(**values):
    return {
        "id": JOB_ID,
        "name": "Canário",
        "enabled": True,
        "state": "scheduled",
        "schedule": {"kind": "interval", "minutes": 525600},
        "repeat": {"times": 1, "completed": 0},
        "next_run_at": "2027-10-30T12:00:00+00:00",
        "last_run_at": None,
        "prompt": "private-prompt",
        "deliver": "private-target",
        "skills": ["private-skill"],
        "origin": {"secret": "private-origin"},
    } | values


@pytest.fixture
def database(tmp_path):
    db = Database(Settings(database_url=f"sqlite:///{tmp_path / 'jobs.db'}"))
    db.initialize()
    yield db
    db.engine.dispose()


def service(database, handler):
    settings = Settings(hermes_url="http://hermes:8642", hermes_key="x" * 40)
    return HermesJobs(database, HermesClient(settings, transport=httpx.MockTransport(handler)))


def test_inventory_is_bounded_allowlisted_and_persisted_without_private_content(database):
    calls = []

    def handler(request):
        calls.append((request.method, str(request.url)))
        return httpx.Response(
            200, json={"jobs": [native_job(id=f"{index:012x}") for index in range(105)]}
        )

    result = service(database, handler).inspect("owner")
    assert result["status"] == "reachable"
    assert len(result["items"]) == 100 and result["truncated"] is True
    assert calls == [("GET", "http://hermes:8642/api/jobs?include_disabled=true")]
    assert "private" not in str(result)
    database.engine.dispose()
    assert jobs_snapshot(database) == result
    with database.session() as db:
        assert "private" not in str(db.get(ProviderObservation, "hermes-jobs").details)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"jobs": {}},
        {"jobs": [native_job(id="../admin")]},
        {"jobs": [native_job(enabled="false")]},
    ],
)
def test_malformed_inventory_is_unavailable_and_never_authorizes_pause(database, payload):
    result = service(database, lambda _: httpx.Response(200, json=payload)).inspect("owner")
    assert result["status"] == "unavailable"
    assert result["items"] == []


def test_pause_requires_observed_id_and_reads_back_the_exact_job(database):
    calls = []
    paused = False

    def handler(request):
        nonlocal paused
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/jobs":
            return httpx.Response(200, json={"jobs": [native_job()]})
        if request.method == "POST":
            paused = True
            return httpx.Response(200, json={"untrusted_ack": "private-value"})
        return httpx.Response(
            200,
            json={
                "job": native_job(
                    enabled=not paused,
                    state="paused" if paused else "scheduled",
                )
            },
        )

    jobs = service(database, handler)
    with pytest.raises(HTTPException) as error:
        jobs.pause(JOB_ID, "owner")
    assert error.value.status_code == 409 and calls == []
    jobs.inspect("owner")
    result = jobs.pause(JOB_ID, "owner")
    assert result["status"] == "confirmed" and result["job_id"] == JOB_ID
    assert calls[1:] == [
        ("GET", f"/api/jobs/{JOB_ID}"),
        ("POST", f"/api/jobs/{JOB_ID}/pause"),
        ("GET", f"/api/jobs/{JOB_ID}"),
    ]
    snapshot = jobs_snapshot(database)
    assert snapshot["items"][0]["enabled"] is False
    assert snapshot["last_pause"]["status"] == "confirmed"
    assert "private" not in str(snapshot)


@pytest.mark.parametrize("failure", ["readback", "still_enabled", "wrong_id", "post"])
def test_pause_never_claims_success_without_readback_and_persists_uncertainty(database, failure):
    posted = False

    def handler(request):
        nonlocal posted
        if request.url.path == "/api/jobs":
            return httpx.Response(200, json={"jobs": [native_job()]})
        if request.method == "POST":
            posted = True
            if failure == "post":
                raise httpx.ReadTimeout("private-server-error")
            return httpx.Response(200, json={"job": native_job(enabled=False, state="paused")})
        if posted and failure == "readback":
            raise httpx.ConnectError("private-server-error")
        job = native_job()
        if posted and failure == "wrong_id":
            job = native_job(id="111111111111", enabled=False, state="paused")
        return httpx.Response(200, json={"job": job})

    jobs = service(database, handler)
    jobs.inspect("owner")
    with pytest.raises(HTTPException) as error:
        jobs.pause(JOB_ID, "owner")
    assert error.value.status_code == 502
    assert "private" not in str(error.value.detail)
    assert jobs_snapshot(database)["last_pause"]["status"] == "uncertain"


def test_invalid_or_unobserved_id_never_reaches_gateway(database):
    calls = []
    jobs = service(database, lambda request: calls.append(request))
    for job_id in ("../admin", "123", "ABCDEF123456", JOB_ID):
        with pytest.raises(HTTPException):
            jobs.pause(job_id, "owner")
    assert not calls


def test_already_paused_job_is_confirmed_without_remote_mutation(database):
    calls = []

    def handler(request):
        calls.append(request.method)
        job = native_job(enabled=False, state="paused")
        return httpx.Response(
            200, json={"jobs": [job]} if request.url.path == "/api/jobs" else {"job": job}
        )

    jobs = service(database, handler)
    jobs.inspect("owner")
    assert jobs.pause(JOB_ID, "owner")["status"] == "confirmed"
    assert calls == ["GET", "GET"]


def test_fresh_inventory_reconciles_a_previously_uncertain_pause(database):
    paused = False
    fail_readback = True

    def handler(request):
        nonlocal paused
        job = native_job(enabled=not paused, state="paused" if paused else "scheduled")
        if request.url.path == "/api/jobs":
            return httpx.Response(200, json={"jobs": [job]})
        if request.method == "POST":
            paused = True
            return httpx.Response(200, json={})
        if paused and fail_readback:
            raise httpx.ReadTimeout("private-error")
        return httpx.Response(200, json={"job": job})

    jobs = service(database, handler)
    jobs.inspect("owner")
    with pytest.raises(HTTPException):
        jobs.pause(JOB_ID, "owner")
    assert jobs_snapshot(database)["last_pause"]["status"] == "uncertain"
    fail_readback = False
    assert jobs.inspect("owner")["last_pause"]["status"] == "confirmed"


def test_pause_total_deadline_leaves_room_for_the_http_envelope(database, monkeypatch):
    import time

    paused = False

    def handler(request):
        nonlocal paused
        if request.method == "POST":
            paused = True
        job = native_job(enabled=not paused, state="paused" if paused else "scheduled")
        return httpx.Response(
            200, json={"jobs": [job]} if request.url.path == "/api/jobs" else {"job": job}
        )

    jobs = service(database, handler)
    jobs.inspect("owner")
    deadlines = []
    original = jobs.client.request

    def request(*args, **kwargs):
        deadlines.append(kwargs["deadline"])
        return original(*args, **kwargs)

    monkeypatch.setattr(jobs.client, "request", request)
    started = time.monotonic()
    jobs.pause(JOB_ID, "owner")
    assert len(set(deadlines)) == 1
    assert deadlines[0] <= started + 9


def test_delayed_inspection_cannot_erase_concurrent_uncertain_pause(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    reading, release = Event(), Event()
    delay = False

    def handler(request):
        if request.url.path == "/api/jobs":
            if delay:
                reading.set()
                assert release.wait(5)
            return httpx.Response(200, json={"jobs": [native_job()]})
        if request.method == "POST":
            raise httpx.ReadTimeout("private lost pause response")
        return httpx.Response(200, json={"job": native_job()})

    jobs = service(database, handler)
    jobs.inspect("owner")
    delay = True
    with ThreadPoolExecutor(max_workers=1) as pool:
        delayed = pool.submit(jobs.inspect, "owner")
        assert reading.wait(5)
        try:
            with pytest.raises(HTTPException):
                jobs.pause(JOB_ID, "owner")
            assert jobs_snapshot(database)["last_pause"]["status"] == "uncertain"
        finally:
            release.set()
        delayed.result(timeout=5)
    assert jobs_snapshot(database)["last_pause"]["status"] == "uncertain"


def test_delayed_paused_inventory_cannot_confirm_a_newer_pause_request(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    reading, release = Event(), Event()
    delay = False

    def handler(request):
        if request.url.path == "/api/jobs":
            if delay:
                reading.set()
                assert release.wait(5)
            return httpx.Response(200, json={"jobs": [native_job(enabled=False, state="paused")]})
        if request.method == "POST":
            raise httpx.ReadTimeout("private lost response")
        return httpx.Response(200, json={"job": native_job()})

    jobs = service(database, handler)
    jobs.inspect("owner")
    delay = True
    with ThreadPoolExecutor(max_workers=1) as pool:
        delayed = pool.submit(jobs.inspect, "owner")
        assert reading.wait(5)
        try:
            with pytest.raises(HTTPException):
                jobs.pause(JOB_ID, "owner")
        finally:
            release.set()
        delayed.result(timeout=5)
    assert jobs_snapshot(database)["last_pause"]["status"] == "uncertain"


def test_delayed_confirmation_is_bound_to_its_request_not_a_newer_uncertainty(database):
    jobs = service(database, lambda _: httpx.Response(200, json={"jobs": [native_job()]}))
    jobs.inspect("owner")
    first = jobs._record_pause(JOB_ID, "uncertain", "owner")
    jobs._record_pause(JOB_ID, "uncertain", "owner")
    observed = jobs_snapshot(database)["items"][0] | {"enabled": False, "state": "paused"}
    read_sequence, _ = jobs._start_read("owner")
    jobs._record_pause(
        JOB_ID,
        "confirmed",
        "owner",
        observed,
        request_id=first["_request_id"],
        proof_sequence=read_sequence,
    )
    assert jobs_snapshot(database)["last_pause"]["status"] == "uncertain"


def test_older_inventory_cannot_replace_a_newer_inspection(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    reading, release = Event(), Event()
    hold_next = False
    current = native_job()

    def handler(request):
        nonlocal hold_next
        payload = {"jobs": [dict(current)]}
        if hold_next:
            hold_next = False
            reading.set()
            assert release.wait(5)
        return httpx.Response(200, json=payload)

    jobs = service(database, handler)
    jobs.inspect("owner")
    hold_next = True
    with ThreadPoolExecutor(max_workers=1) as pool:
        delayed = pool.submit(jobs.inspect, "owner")
        assert reading.wait(5)
        try:
            current = native_job(enabled=False, state="paused")
            assert jobs.inspect("owner")["items"][0]["state"] == "paused"
        finally:
            release.set()
        delayed.result(timeout=5)
    assert jobs_snapshot(database)["items"][0]["state"] == "paused"


def test_later_external_resume_is_not_hidden_by_old_confirmed_pause(database):
    paused = False

    def handler(request):
        nonlocal paused
        if request.method == "POST":
            paused = True
        job = native_job(enabled=not paused, state="paused" if paused else "scheduled")
        return httpx.Response(
            200, json={"jobs": [job]} if request.url.path == "/api/jobs" else {"job": job}
        )

    jobs = service(database, handler)
    jobs.inspect("owner")
    jobs.pause(JOB_ID, "owner")
    assert jobs_snapshot(database)["items"][0]["state"] == "paused"
    paused = False  # Another trusted native operator resumes it outside AI TEAM.
    snapshot = jobs.inspect("owner")
    assert snapshot["items"][0]["enabled"] is True
    assert snapshot["items"][0]["state"] == "scheduled"


def test_delayed_pause_readback_cannot_overlay_a_later_external_resume_inspection(database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    reading, release = Event(), Event()
    paused = False
    block_readback = True

    def handler(request):
        nonlocal paused, block_readback
        if request.method == "POST":
            paused = True
            return httpx.Response(200, json={})
        job = native_job(enabled=not paused, state="paused" if paused else "scheduled")
        if request.url.path == "/api/jobs":
            return httpx.Response(200, json={"jobs": [job]})
        if paused and block_readback:
            block_readback = False
            reading.set()
            assert release.wait(5)
        return httpx.Response(200, json={"job": job})

    jobs = service(database, handler)
    jobs.inspect("owner")
    with ThreadPoolExecutor(max_workers=1) as pool:
        pausing = pool.submit(jobs.pause, JOB_ID, "owner")
        assert reading.wait(5)
        try:
            paused = False
            assert jobs.inspect("owner")["items"][0]["enabled"] is True
        finally:
            release.set()
        assert pausing.result(timeout=5)["status"] == "confirmed"
    assert jobs_snapshot(database)["items"][0]["enabled"] is True
    assert jobs_snapshot(database)["items"][0]["state"] == "scheduled"


def test_confirmed_pause_projection_is_independent_for_each_observed_job(database):
    other_id = "111111111111"
    rows = {job_id: native_job(id=job_id) for job_id in (JOB_ID, other_id)}

    def handler(request):
        if request.url.path == "/api/jobs":
            return httpx.Response(200, json={"jobs": list(rows.values())})
        job_id = request.url.path.split("/")[3]
        if request.method == "POST":
            rows[job_id].update(enabled=False, state="paused")
        return httpx.Response(200, json={"job": rows[job_id]})

    jobs = service(database, handler)
    jobs.inspect("owner")
    jobs.pause(JOB_ID, "owner")
    jobs.pause(other_id, "owner")
    snapshot = jobs_snapshot(database)
    assert all(not item["enabled"] and item["state"] == "paused" for item in snapshot["items"])
    assert snapshot["last_pause"]["job_id"] == other_id


def test_ci_canary_lifecycle_is_guarded_future_only_and_read_only_after_restart(
    tmp_path, monkeypatch
):
    import importlib.util
    from datetime import UTC, datetime, timedelta
    from pathlib import Path

    path = Path(__file__).resolve().parents[3] / "infra/hermes/runtime_smoke.py"
    spec = importlib.util.spec_from_file_location("ci_jobs_probe", path)
    smoke = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(smoke)
    calls, job = [], {}

    def request(path, key, *, method="GET", body=None):
        nonlocal job
        calls.append((method, path))
        if path == "/api/jobs?include_disabled=true":
            return 200, {"jobs": [job | {"latest_execution": None}] if job else []}
        if path == "/api/jobs" and method == "POST":
            assert body["paused"] is True and body["repeat"] == 1
            assert body["schedule"] == "every 365d"
            job = native_job(
                id=JOB_ID,
                name=body["name"],
                enabled=False,
                state="paused",
                next_run_at=None,
                last_status=None,
                script=None,
                skills=[],
                deliver="local",
            )
        elif path.endswith("/resume") and method == "POST":
            job.update(
                enabled=True,
                state="scheduled",
                next_run_at=(datetime.now(UTC) + timedelta(days=365)).isoformat(),
            )
        elif path.endswith("/pause") and method == "POST":
            job.update(enabled=False, state="paused")
        elif path != f"/api/jobs/{JOB_ID}" or method != "GET":
            raise AssertionError("Unexpected native mutation")
        return 200, {"job": dict(job)}

    monkeypatch.setattr(smoke, "request", request)
    monkeypatch.delenv("AI_TEAM_RUNTIME_CI", raising=False)
    with pytest.raises(smoke.SmokeFailure, match="explicit CI job mutation guard"):
        smoke.check_ci_jobs(tmp_path, "12-1", "synthetic-key", True)
    assert calls == []
    monkeypatch.setenv("AI_TEAM_RUNTIME_CI", "true")
    smoke.check_ci_jobs(tmp_path, "12-1", "synthetic-key", True)
    assert [path for method, path in calls if method == "POST"] == [
        "/api/jobs",
        f"/api/jobs/{JOB_ID}/resume",
        f"/api/jobs/{JOB_ID}/pause",
    ]
    calls.clear()
    smoke.check_ci_jobs(tmp_path, "12-1", "synthetic-key", False)
    assert all(method == "GET" for method, _ in calls)
