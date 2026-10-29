import hashlib
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from ai_team.auth import create_owner
from ai_team.config import Settings
from ai_team.db import Database
from ai_team.main import create_app
from ai_team.models import AuthSession, Event

ORIGIN = "http://localhost:3000"
PASSWORD = "teste-apenas-local-493!"


def test_first_owner_can_be_created_after_unsuccessful_login(tmp_path):
    from ai_team.models import LoginThrottle, Owner

    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'first-owner.db'}"))
    database.initialize()
    app = create_app(database=database)
    with TestClient(app, headers={"origin": ORIGIN}) as browser:
        assert (
            browser.post(
                "/auth/login",
                json={
                    "username": "admin",
                    "password": PASSWORD,
                },
            ).status_code
            == 401
        )
        with database.session() as db:
            throttle = db.scalar(select(LoginThrottle))
            original_attempts = throttle.attempts
            create_owner(db, "admin", PASSWORD)
            assert db.scalar(select(Owner.username)) == "admin"
            assert db.scalar(select(LoginThrottle)).attempts == original_attempts
        assert (
            browser.post(
                "/auth/login",
                json={
                    "username": "admin",
                    "password": PASSWORD,
                },
            ).status_code
            == 200
        )


@pytest.fixture
def app(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")
    database = Database(settings)
    database.initialize()
    with database.session() as db:
        create_owner(db, "igor", PASSWORD)
    return create_app(settings, database)


@pytest.fixture
def client(app):
    with TestClient(app, headers={"origin": ORIGIN}) as c:
        yield c


def login(client):
    response = client.post("/auth/login", json={"username": "igor", "password": PASSWORD})
    assert response.status_code == 200
    return response


def test_private_routes_require_login(client):
    for path in ["/auth/me", "/workspace", "/projects", "/tasks", "/events", "/integrations"]:
        assert client.get(path).status_code == 401


def test_session_is_hashed_http_only_and_revoked(client, app):
    response = login(client)
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie
    token = client.cookies.get("ai_team_session")
    with app.state.database.session() as db:
        session = db.scalar(select(AuthSession))
        assert session.token_hash == hashlib.sha256(token.encode()).hexdigest()
        assert session.token_hash != token
    assert client.get("/auth/me").json()["username"] == "igor"
    assert client.post("/auth/logout").status_code == 204
    client.cookies.set("ai_team_session", token)
    assert client.get("/workspace").status_code == 401


def test_expired_session_is_denied(client, app):
    login(client)
    with app.state.database.session() as db:
        session = db.scalar(select(AuthSession))
        session.expires_at = int(time.time()) - 1
        db.commit()
    assert client.get("/workspace").status_code == 401


def test_login_brute_force_persists_across_clients(client, app):
    for _ in range(5):
        assert (
            client.post("/auth/login", json={"username": "igor", "password": "wrong"}).status_code
            == 401
        )
    with TestClient(app, headers={"origin": ORIGIN}) as other:
        response = other.post("/auth/login", json={"username": "igor", "password": PASSWORD})
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) > 0


@pytest.mark.parametrize("origin", ["https://evil.example", "null", ""])
def test_mutations_reject_foreign_or_missing_origin(client, origin):
    response = client.post(
        "/auth/login", headers={"origin": origin}, json={"username": "igor", "password": PASSWORD}
    )
    assert response.status_code == 403


def test_projects_tasks_and_audit_are_persistent(client, app):
    login(client)
    assert client.get("/workspace").json()["projects"] == []
    project = client.post(
        "/projects", json={"name": "Projeto original", "description": "Descrição com acentos"}
    ).json()
    assert project["name"] == "Projeto original"
    task = client.post(
        "/tasks", json={"project_id": project["id"], "title": "Validar arquitetura", "agent": "QA"}
    ).json()
    assert task["status"] == "backlog"
    for status in ["in_progress", "review", "done"]:
        response = client.patch(f"/tasks/{task['id']}", json={"status": status})
        assert response.status_code == 200
    # Another connection sees committed data; app restart doesn't require seed fixtures.
    with app.state.database.session() as db:
        assert len(list(db.scalars(select(Event)))) == 6  # login + project + task + 3 changes
    snapshot = client.get("/workspace").json()
    assert snapshot["tasks"][0]["status"] == "done"
    assert snapshot["usage"]["cost_usd"] is None  # no fabricated billing estimate
    assert snapshot["runs"] == []


def test_validation_and_invalid_transitions_do_not_write(client):
    login(client)
    assert client.post("/projects", json={"name": "   "}).status_code == 422
    assert client.post("/projects", json={"name": "x" * 121}).status_code == 422
    assert (
        client.post("/tasks", json={"project_id": "missing", "title": "tarefa"}).status_code == 404
    )
    project = client.post("/projects", json={"name": "Projeto"}).json()
    task = client.post("/tasks", json={"project_id": project["id"], "title": "Minha tarefa"}).json()
    assert client.patch(f"/tasks/{task['id']}", json={"status": "done"}).status_code == 409
    assert client.patch("/tasks/missing", json={"status": "review"}).status_code == 404
    assert client.patch(f"/tasks/{task['id']}", json={"status": "invalid"}).status_code == 422
    assert client.get("/tasks").json()[0]["status"] == "backlog"


def test_integration_status_never_claims_tested_without_probe(client):
    login(client)
    statuses = client.get("/integrations").json()
    assert all(
        item["status"] in {"not_configured", "configured", "planned", "available"}
        for item in statuses
    )
    assert all(item["verified_at"] is None for item in statuses)


def test_owner_cannot_be_registered_over_http(client):
    assert client.post("/auth/register", json={}).status_code == 404


def test_duplicate_owner_and_weak_password_rejected(app):
    with app.state.database.session() as db:
        with pytest.raises(ValueError):
            create_owner(db, "other", "short")
        with pytest.raises(ValueError):
            create_owner(db, "other", PASSWORD)


def test_parallel_login_attempts_cannot_bypass_limit(app):
    def attempt(_):
        with TestClient(app, headers={"origin": ORIGIN}) as parallel:
            return parallel.post(
                "/auth/login", json={"username": "igor", "password": "wrong"}
            ).status_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(attempt, range(12)))
    assert statuses.count(401) == 5
    assert statuses.count(429) == 7


def test_production_requires_https_and_postgres():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(environment="production")
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(environment="production", public_origin="https://example.com")


def test_project_data_survives_application_restart(client, app):
    login(client)
    project = client.post("/projects", json={"name": "Persistir reinício"}).json()
    restarted = create_app(app.state.settings, Database(app.state.settings))
    with TestClient(restarted, headers={"origin": ORIGIN}) as other:
        login(other)
        assert other.get("/projects").json()[0]["id"] == project["id"]


def test_audit_preserves_insertion_order_with_same_timestamp(client, app):
    login(client)
    with app.state.database.session() as db:
        db.add(Event(id="aaa", kind="first", summary="Primeiro", created_at=2000000000))
        db.flush()
        db.add(Event(id="zzz", kind="second", summary="Segundo", created_at=2000000000))
        db.commit()
    assert [event["kind"] for event in client.get("/events").json()[:2]] == ["second", "first"]
