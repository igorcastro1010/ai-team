from fastapi.testclient import TestClient

from ai_team.auth import create_owner
from ai_team.config import Settings
from ai_team.db import Database
from ai_team.main import create_app


def test_export_review_binds_existing_markdown_and_note_version(tmp_path):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'review.db'}", memory_vault=str(tmp_path / "vault")
    )
    database = Database(settings)
    database.initialize()
    with database.session() as db:
        create_owner(db, "owner", "ReviewTests123!Only")
    with TestClient(
        create_app(settings, database), headers={"origin": "http://localhost:3000"}
    ) as client:
        assert client.get("/memory/missing/missing/export").status_code == 401
        client.post("/auth/login", json={"username": "owner", "password": "ReviewTests123!Only"})
        project = client.post("/projects", json={"name": "Vault review"}).json()["id"]
        note = client.post(
            f"/memory/{project}", json={"title": "Decisão", "content": "Original"}
        ).json()
        url = f"/memory/{project}/{note['id']}/export"
        review = client.get(url)
        assert review.status_code == 200, review.text
        assert review.json()["exists"] is False
        assert client.post(url, json={"expected_version": 1}).status_code == 200
        review = client.get(url).json()
        assert review["content"] == "Original" and review["exists"] is True
        assert len(review["digest"]) == 64
        client.put(
            f"/memory/{project}/{note['id']}",
            json={"title": "Decisão", "content": "Nova", "expected_version": 1},
        )
        assert (
            client.post(
                url, json={"expected_digest": review["digest"], "expected_version": 1}
            ).status_code
            == 409
        )
        review = client.get(url).json()
        assert review["note_content"] == "Nova" and review["note_version"] == 2
        mirror = tmp_path / "vault" / project / (note["id"] + ".md")
        mirror.write_text("Edição externa", encoding="utf-8")
        assert (
            client.post(
                url, json={"expected_digest": review["digest"], "expected_version": 2}
            ).status_code
            == 409
        )
        assert mirror.read_text(encoding="utf-8") == "Edição externa"
        review = client.get(url).json()
        assert (
            client.post(
                url, json={"expected_digest": review["digest"], "expected_version": 2}
            ).status_code
            == 200
        )
        assert mirror.read_text(encoding="utf-8") == "Nova"
        other = client.post("/projects", json={"name": "Outro"}).json()["id"]
        assert client.get(f"/memory/{other}/{note['id']}/export").status_code == 404
