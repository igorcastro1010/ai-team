from types import SimpleNamespace

from ai_team.office import office_snapshot


def test_repository_research_and_testing_are_real_stage_projections():
    researching = run(scope="repository_code", stage=1)
    snapshot = office_snapshot([researching], worker_online=True)
    researcher = next(a for a in snapshot if a["id"] == "PESQUISADOR")
    assert researcher["enabled"] and researcher["animate"]
    assert researcher["activity"] == "Pesquisando"
    testing = run(
        scope="repository_code",
        stage=5,
        steps=[{"agent": "QA", "execution_started": True, "summary": "Testes gerados"}],
    )
    snapshot = office_snapshot([testing], worker_online=True)
    assert next(a for a in snapshot if a["id"] == "QA")["animate"]


def run(**changes):
    values = dict(
        id="test",
        executor="hermes",
        status="running",
        stage=1,
        steps=[],
        error="",
        created_at=100,
        lease_expires_at=9999999999,
    )
    return SimpleNamespace(**(values | changes))


def test_office_never_animates_without_valid_worker_evidence():
    snapshot = office_snapshot([run()], worker_online=False)
    dev = next(agent for agent in snapshot if agent["id"] == "DEV")
    assert dev["status"] == "working"
    assert dev["animate"] is False
    assert dev["run_id"] == "test"


def test_next_office_tracks_real_suite_then_report_without_queued_animation():
    steps = [
        {"stage": i, "agent": name, "summary": name, "deliverable": "artefato"}
        for i, name in enumerate(["CEO", "DEV", "DESIGNER", "QA"])
    ]
    steps[3]["execution_started"] = True
    current = run(scope="nextjs_code", stage=4, steps=steps)
    snapshot = office_snapshot([current], worker_online=True)
    assert next(a for a in snapshot if a["id"] == "QA")["animate"] is True
    steps[3]["test_result"] = {"status": "passed"}
    current.status = "queued"
    assert not any(a["animate"] for a in office_snapshot([current], worker_online=True))
    current.status = "running"
    snapshot = office_snapshot([current], worker_online=True)
    assert next(a for a in snapshot if a["id"] == "CEO")["animate"] is True


def test_office_uses_persisted_stage_and_approval_owner():
    snapshot = office_snapshot([run()], worker_online=True)
    assert next(agent for agent in snapshot if agent["id"] == "DEV")["animate"] is True
    awaiting = run(
        status="awaiting_approval",
        stage=1,
        steps=[{"agent": "CEO", "summary": "Plano", "deliverable": "Artefato persistido"}],
    )
    snapshot = office_snapshot([awaiting], worker_online=True)
    ceo = next(agent for agent in snapshot if agent["id"] == "CEO")
    assert ceo["status"] == "awaiting_approval"
    assert not ceo["animate"]
    assert ceo["history"][0]["deliverable"] == "Artefato persistido"


def test_expired_lease_never_animates_and_prepared_roles_have_no_fake_history():
    snapshot = office_snapshot([run(lease_expires_at=1)], worker_online=True)
    assert not any(agent["animate"] for agent in snapshot)
    assert len(snapshot) == 7
    researcher = next(agent for agent in snapshot if agent["id"] == "PESQUISADOR")
    assert not researcher["enabled"]
    assert researcher["history"] == []
    assert researcher["run_id"] is None


def test_active_work_has_priority_over_more_recent_terminal_history():
    snapshot = office_snapshot(
        [
            run(id="recent", status="failed", created_at=200),
            run(id="active", created_at=100),
        ],
        worker_online=True,
    )
    assert next(agent for agent in snapshot if agent["id"] == "DEV")["run_id"] == "active"


def test_running_has_priority_over_newer_queued_work():
    snapshot = office_snapshot(
        [
            run(id="queued", status="queued", created_at=200),
            run(id="active", created_at=100),
        ],
        worker_online=True,
    )
    dev = next(agent for agent in snapshot if agent["id"] == "DEV")
    assert dev["run_id"] == "active"
    assert dev["animate"]
