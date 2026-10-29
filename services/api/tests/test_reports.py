from test_api import app as app
from test_api import client as client
from test_api import login


def test_reports_are_private(client):
    assert client.get("/reports").status_code == 401


def test_report_counts_all_runs_and_paginates_stably_without_private_fields(client, app):
    from ai_team.models import Project, Run

    login(client)
    with app.state.database.session() as db:
        db.add(Project(id="reports", name="Relatórios"))
        db.flush()
        db.add_all(
            [
                Run(
                    id=f"report-{i:04}",
                    project_id="reports",
                    prompt="sensitive prompt",
                    mode="manual",
                    status="completed",
                    calls=2,
                    input_tokens=20,
                    output_tokens=10,
                    created_at=1000,
                    lease_token="private lease",
                )
                for i in range(205)
            ]
        )
        db.commit()
    result = client.get("/reports?limit=100")
    assert result.status_code == 200, result.text
    report = result.json()
    assert report["summary"]["runs"]["completed"] == 205
    assert report["summary"]["usage"] == {
        "calls": 410,
        "input_tokens": 4100,
        "output_tokens": 2050,
        "cost_usd": None,
    }
    assert "sensitive prompt" not in result.text and "private lease" not in result.text
    items = report["runs"]
    while report["next_cursor"]:
        report = client.get("/reports", params={"limit": 100, **report["next_cursor"]}).json()
        items.extend(report["runs"])
    assert len(items) == len({item["id"] for item in items}) == 205
    assert client.get("/reports?limit=101").status_code == 422
    assert client.get("/reports?before_created_at=1000").status_code == 422


def test_report_links_scheduled_occurrence_and_respects_cursor(client, app):
    from test_schedules import payload

    from ai_team.models import Project
    from ai_team.schedules import ScheduleStore

    login(client)
    with app.state.database.session() as db:
        db.add(Project(id="project", name="Rotina"))
        db.commit()
    store = ScheduleStore(app.state.database)
    schedule = store.create(payload(), "owner", now=1000)
    store.tick(now=1100)
    report = client.get("/reports").json()
    assert report["summary"]["occurrences"] == 1
    assert report["runs"][0]["schedule_id"] == schedule.id
    assert report["runs"][0]["occurrence"] == 1
