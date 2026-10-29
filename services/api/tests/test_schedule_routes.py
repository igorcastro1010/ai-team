import time

from test_api import app as app
from test_api import client as client
from test_api import login


def data(client):
    project = client.post("/projects", json={"name": "Agenda"}).json()
    return {
        "project_id": project["id"],
        "prompt": "Planeje uma revisão semanal.",
        "mode": "supervised",
        "interval_seconds": 86400,
        "starts_at": int(time.time()) + 300,
        "max_runs": 3,
        "consent": True,
    }


def test_schedule_api_requires_owner_and_origin(client):
    assert client.get("/schedules").status_code == 401
    assert client.post("/schedules", json={}).status_code == 401
    login(client)
    assert (
        client.post(
            "/schedules", json=data(client), headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_schedule_api_persists_reviewed_scope_and_audits_cancellation(client):
    login(client)
    payload = data(client)
    response = client.post("/schedules", json=payload)
    assert response.status_code == 201, response.text
    schedule = response.json()
    assert schedule["mode"] == "supervised" and schedule["max_runs"] == 3
    assert schedule["expires_at"] <= int(time.time()) + 30 * 86400
    assert client.get("/workspace").json()["schedules"][0]["id"] == schedule["id"]
    assert client.get("/schedules").json()[0]["prompt"] == payload["prompt"]
    assert client.post(f"/schedules/{schedule['id']}/cancel").status_code == 200
    assert client.post(f"/schedules/{schedule['id']}/cancel").status_code == 409
    assert client.get("/schedules").json()[0]["status"] == "cancelled"
    assert any(event["kind"] == "schedule.cancelled" for event in client.get("/events").json())


def test_schedule_api_rejects_unreviewed_fields_and_missing_consent(client):
    login(client)
    payload = data(client)
    assert client.post("/schedules", json={**payload, "scope": "shell"}).status_code == 422
    assert client.post("/schedules", json={**payload, "consent": False}).status_code == 422
    assert client.get("/schedules").json() == []
