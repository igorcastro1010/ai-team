from fastapi.testclient import TestClient

from ai_team.auth import create_owner
from ai_team.config import Settings
from ai_team.db import Database
from ai_team.main import create_app


def test_memory_api_auth_csrf_scope_and_vault_incremental_sync(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'routes.db'}", memory_vault=str(tmp_path / "vault")
    )
    database = Database(settings)
    database.initialize()
    with database.session() as db:
        create_owner(db, "owner", "MemoryTests123!Only")
    with TestClient(
        create_app(settings, database), headers={"origin": "http://localhost:3000"}
    ) as client:
        assert client.get("/memory/missing").status_code == 401
        client.post("/auth/login", json={"username": "owner", "password": "MemoryTests123!Only"})
        project = client.post("/projects", json={"name": "Conhecimento"}).json()["id"]
        data = {"title": "Python", "content": "Usar biblioteca padrão e testes unittest."}
        assert (
            client.post(
                f"/memory/{project}", json=data, headers={"origin": "http://evil"}
            ).status_code
            == 403
        )
        saved = client.post(f"/memory/{project}", json=data)
        assert saved.status_code == 201, saved.text
        note = saved.json()
        assert client.get(f"/memory/{project}/{note['id']}").json()["content"] == data["content"]
        assert client.post(f"/memory/{project}/{note['id']}/export", json={}).status_code == 200
        synced = client.post(f"/memory/{project}/sync").json()
        assert synced["imported"] == 0
        file = tmp_path / "vault" / project / "external.md"
        file.write_text("# Decisão\nPostgreSQL privado.", encoding="utf-8")
        assert client.post(f"/memory/{project}/sync").json()["imported"] == 1
        assert client.post(f"/memory/{project}/sync").json()["imported"] == 0
        assert len(client.get(f"/memory/{project}").json()["items"]) == 2
        assert client.get(f"/memory/{project}/search", params={"q": "PostgreSQL"}).json()["items"]
        assert client.get("/memory/missing").status_code == 404
        assert len(client.get(f"/memory/{project}/{note['id']}/history").json()["items"]) == 1
