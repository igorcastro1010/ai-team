import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Project


def payload(**changes):
    return {
        "project_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "title": "Apresentação",
        "format": "vertical",
        "consent": True,
        "scenes": [{"text": "Olá, equipe!", "duration": 2}],
        **changes,
    }


def test_video_schema_rejects_unbounded_and_unapproved_inputs():
    from ai_team.video_routes import VideoInput

    for change in (
        {"consent": False},
        {"scenes": [{"text": "x", "duration": 61}]},
        {"url": "https://example.com"},
        {"scenes": []},
        {"scenes": [{"text": "x", "duration": 11}] * 6},
    ):
        with pytest.raises(ValidationError):
            VideoInput(**payload(**change))
    assert VideoInput(**payload()).format == "vertical"


@pytest.fixture
def store(tmp_path):
    from ai_team.video_store import VideoStore

    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'video.db'}"))
    database.initialize()
    return VideoStore(database)


def create(store):
    from ai_team.video_routes import VideoInput

    data = VideoInput(**payload())
    with store.database.session() as db:
        db.add(Project(id=str(data.project_id), name="Video"))
        db.commit()
    return data, store.create(data)


def test_video_approval_digest_idempotency_and_project_scope(store):
    data, job = create(store)
    assert job["status"] == "pending_approval"
    assert store.claim() is None
    assert store.create(data)["id"] == job["id"]
    with pytest.raises(HTTPException) as error:
        store.decide(job["id"], "0" * 64, True)
    assert error.value.status_code == 409
    assert store.snapshot(str(uuid.uuid4()))["items"] == []
    approved = store.decide(job["id"], job["digest"], True)
    assert approved["status"] == "queued"
    claim = store.claim()
    assert claim["id"] == job["id"] and claim["lease_token"]
    assert store.claim() is None
    store.cancel(job["id"])
    assert not store.active(job["id"], claim["lease_token"])
    assert not store.finish(job["id"], claim["lease_token"], "completed")


def test_video_request_conflict_and_active_limit(store):
    data, job = create(store)
    from ai_team.video_routes import VideoInput

    changed = data.model_copy(update={"title": "Outro"})
    with pytest.raises(HTTPException):
        store.create(changed)
    second = VideoInput(**payload(project_id=str(data.project_id)))
    store.create(second)
    with pytest.raises(HTTPException) as error:
        store.create(VideoInput(**payload(project_id=str(data.project_id))))
    assert error.value.status_code == 409
    store.cancel(job["id"])
    assert store.create(VideoInput(**payload(project_id=str(data.project_id))))


def test_missing_renderer_blocks_without_claiming_success(store, tmp_path):
    from ai_team.video_worker import VideoWorker

    data, job = create(store)
    store.decide(job["id"], job["digest"], True)
    worker = VideoWorker(store, tmp_path, executable="/missing/ffmpeg")
    assert worker.once()
    assert store.get(job["id"])["status"] == "blocked"
    assert not list(tmp_path.glob("*.mp4"))


def test_video_http_auth_csrf_and_download_guards(tmp_path):
    from fastapi.testclient import TestClient

    from ai_team.auth import create_owner
    from ai_team.main import create_app
    from ai_team.video_routes import router

    settings = Settings(database_url=f"sqlite:///{tmp_path / 'http.db'}")
    database = Database(settings)
    database.initialize()
    with database.session() as db:
        create_owner(db, "video-owner", "local-video-password-9217")
    app = create_app(settings, database)
    if not any(getattr(route, "path", "") == "/videos" for route in app.routes):
        app.include_router(router)
    data = payload()
    with TestClient(app, headers={"origin": settings.public_origin}) as client:
        assert client.get(f"/videos?project_id={data['project_id']}").status_code == 401
        assert client.post("/videos", json=data).status_code == 401
        assert client.get(f"/videos/{uuid.uuid4()}/download").status_code == 401
        assert (
            client.post(
                "/auth/login",
                json={"username": "video-owner", "password": "local-video-password-9217"},
            ).status_code
            == 200
        )
        with database.session() as db:
            db.add(Project(id=data["project_id"], name="Video"))
            db.commit()
        assert (
            client.post(
                "/videos", json=data, headers={"origin": "https://evil.example"}
            ).status_code
            == 403
        )
        response = client.post("/videos", json=data)
        assert response.status_code == 201
        job = response.json()
        assert client.get(f"/videos/{job['id']}/download").status_code == 409
        assert (
            client.post(
                f"/videos/{job['id']}/decision", json={"digest": job["digest"], "approve": True}
            ).json()["status"]
            == "queued"
        )
        assert (
            client.post(
                f"/videos/{job['id']}/decision", json={"digest": job["digest"], "approve": True}
            ).status_code
            == 409
        )
        assert client.post(f"/videos/{job['id']}/cancel").json()["status"] == "cancelled"


def test_video_executor_rejects_tampered_approval_and_expires_lease(store):
    from sqlalchemy import update

    from ai_team.video_models import VideoJob

    _, job = create(store)
    store.decide(job["id"], job["digest"], True)
    with store.database.session() as db:
        db.execute(
            update(VideoJob)
            .where(VideoJob.id == job["id"])
            .values(
                payload={
                    "title": "Tampered",
                    "consent": True,
                    "format": "vertical",
                    "scenes": [{"text": "x", "duration": 1}],
                }
            )
        )
        db.commit()
    assert store.claim() is None
    assert store.get(job["id"])["status"] == "blocked"
    _, second = create(store)
    store.decide(second["id"], second["digest"], True)
    claim = store.claim()
    with store.database.session() as db:
        db.execute(update(VideoJob).where(VideoJob.id == second["id"]).values(lease_expires_at=0))
        db.commit()
    assert not store.active(second["id"], claim["lease_token"])
    assert store.claim() is None
    assert store.get(second["id"])["status"] == "failed"


def test_real_ffmpeg_render_has_mp4_and_literal_caption(tmp_path):
    from ai_team.video_render import render, renderer_status

    if not renderer_status()["available"]:
        pytest.skip("FFmpeg/font not installed on this host")
    private = tmp_path / "vídeo's demo"
    output = private / "proof.mp4"
    render(
        {
            "format": "vertical",
            "scenes": [
                {"text": "Olá! 100% %{n} : [x]; teste", "duration": 1},
                {"text": "Segunda cena", "duration": 1},
            ],
        },
        output,
        lambda: True,
    )
    content = output.read_bytes()
    assert b"ftyp" in content[:32]
    assert b"moov" in content
    assert output.stat().st_size > 1000
    assert len(list(private.iterdir())) == 1


def test_real_ffmpeg_cancellation_leaves_no_artifact(tmp_path):
    from ai_team.video_render import render, renderer_status

    if not renderer_status()["available"]:
        pytest.skip("FFmpeg/font not installed on this host")
    output = tmp_path / "cancelled.mp4"
    with pytest.raises(InterruptedError):
        render(
            {"format": "horizontal", "scenes": [{"text": "Olá", "duration": 3}]},
            output,
            lambda: False,
        )
    assert not output.exists()
    assert not list(tmp_path.iterdir())


def test_video_consent_requires_explicit_boolean_true():
    from ai_team.video_routes import VideoInput

    for consent in (1, "true", False):
        with pytest.raises(ValidationError):
            VideoInput(**payload(consent=consent))


def test_real_ffmpeg_caption_files_use_single_line_breaks(tmp_path, monkeypatch):
    from pathlib import Path

    from ai_team.video_render import render, renderer_status

    if not renderer_status()["available"]:
        pytest.skip("FFmpeg/font not installed on this host")
    original = Path.write_text
    captions = []

    def capture(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path.name.startswith("caption"):
            captions.append(path.read_bytes())
        return result

    monkeypatch.setattr(Path, "write_text", capture)
    render(
        {
            "format": "vertical",
            "scenes": [
                {"text": "Primeira linha de legenda. Segunda linha de legenda.", "duration": 1}
            ],
        },
        tmp_path / "linebreak.mp4",
        lambda: True,
    )
    assert captions and b"\n" in captions[0]
    assert b"\r" not in captions[0]
