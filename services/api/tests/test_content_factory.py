import uuid

import pytest
from fastapi import HTTPException

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Project


@pytest.fixture
def factory(tmp_path, monkeypatch):
    from ai_team.content_factory import FactoryStore

    monkeypatch.setenv("AI_TEAM_VIDEO_ROOT", str(tmp_path / "media"))
    db = Database(Settings(database_url=f"sqlite:///{tmp_path / 'factory.db'}"))
    db.initialize()
    project = str(uuid.uuid4())
    with db.session() as session:
        session.add(Project(id=project, name="Fábrica"))
        session.commit()
    return FactoryStore(db), project


def request(project, **changes):
    from ai_team.content_factory import ProductionInput

    return ProductionInput(
        project_id=project,
        request_id=str(uuid.uuid4()),
        prompt="Crie um Reels de 15 segundos com a logo FORTALAKA. Preto, branco e vermelho.",
        **changes,
    )


def test_idempotency_secret_rejection_and_project_isolation(factory):
    store, project = factory
    data = request(project)
    created = store.create(data)
    assert store.create(data)["id"] == created["id"]
    with pytest.raises(HTTPException):
        store.get(str(uuid.uuid4()), created["id"])
    with pytest.raises(HTTPException):
        store.create(data.model_copy(update={"prompt": "api_key=" + "x" * 40}))
    with pytest.raises(HTTPException):
        store.create(data.model_copy(update={"prompt": "Outro conteúdo"}))


def test_durable_stages_wait_for_media_and_cancel(factory):
    from ai_team.content_factory import FactoryWorker

    store, project = factory
    row = store.create(request(project))
    for _ in range(3):
        assert FactoryWorker(type(store)(store.database)).once()
    current = store.get(project, row["id"])
    assert current["status"] == "waiting_media"
    assert [step["agent"] for step in current["steps"]] == ["CEO", "PESQUISADOR", "DESIGNER"]
    assert current["video_id"] is None
    assert current["steps"][0]["details"]["supplied_media"] == 0
    assert current["steps"][1]["details"]["durations"] == [4, 4, 4, 3]
    assert all(step["inference"] is False for step in current["steps"])
    store.cancel(project, row["id"])
    assert store.get(project, row["id"])["status"] == "cancelled"
    assert not FactoryWorker(store).once()


def upload_logo(store, project):
    import base64

    from ai_team.video_media import MediaStore

    # Original disposable one-pixel fixture; not the user's FORTALAKA logo.
    body = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jGv8AAAAASUVORK5CYII="
    )
    return MediaStore(store.database).upload(project, "fixture.png", "image/png", body)


def test_review_digest_edit_isolation_and_real_mp4(factory):
    from ai_team.content_factory import FactoryWorker
    from ai_team.video_render import artifact_root, renderer_status
    from ai_team.video_store import VideoStore
    from ai_team.video_worker import VideoWorker

    if not renderer_status()["available"]:
        pytest.skip("FFmpeg e fonte locais necessários")
    store, project = factory
    asset = upload_logo(store, project)
    row = store.create(request(project, media_ids=[asset["id"]]))
    for _ in range(3):
        assert FactoryWorker(store).once()
    review = store.get(project, row["id"])
    assert review["status"] == "awaiting_approval"
    assert len(review["document"]["scenes"]) == 4
    assert sum(s["duration"] for s in review["document"]["scenes"]) == 15
    assert review["document"]["scenes"][0]["text"] == "FORTALAKA"
    assert not VideoStore(store.database).snapshot(project)["items"]
    edited = store.edit(project, row["id"], 0, {**review["document"], "title": "Minha revisão"})
    with pytest.raises(HTTPException):
        store.approve(project, row["id"], review["digest"])
    store.approve(project, row["id"], edited["digest"])
    with pytest.raises(HTTPException):
        store.approve(project, row["id"], edited["digest"])
    worker = VideoWorker(VideoStore(store.database), output=artifact_root())
    for _ in range(5):
        worker.once()
    result = store.get(project, row["id"])
    assert result["status"] == "completed", (
        result["stage"],
        result["steps"],
        VideoStore(store.database).snapshot(project),
    )
    assert [step["agent"] for step in result["steps"]] == [
        "CEO",
        "PESQUISADOR",
        "DESIGNER",
        "DEV",
        "QA",
        "CEO",
    ]
    assert "720×1280" in result["steps"][-2]["summary"]
    assert (artifact_root() / f"{result['video_id']}.mp4").is_file()


def test_media_resume_and_cross_project_denial(factory, monkeypatch):
    from ai_team import video_media
    from ai_team.content_factory import FactoryWorker

    monkeypatch.setattr(
        video_media, "probe", lambda *_: {"width": 1, "height": 1, "duration": None}
    )
    store, project = factory
    asset = upload_logo(store, project)
    with store.database.session() as db:
        other = Project(name="Outro")
        db.add(other)
        db.commit()
        other_id = other.id
    with pytest.raises(HTTPException):
        store.create(request(other_id, media_ids=[asset["id"]]))
    row = store.create(request(project))
    for _ in range(3):
        FactoryWorker(store).once()
    store.resume(project, row["id"], [asset["id"]])
    assert FactoryWorker(store).once()
    assert store.get(project, row["id"])["status"] == "awaiting_approval"


def test_expired_checkpoint_recovers_without_repeating_completed_steps(factory):
    from ai_team.content_factory import FactoryWorker
    from ai_team.content_factory_models import ContentProduction

    store, project = factory
    row = store.create(request(project))
    FactoryWorker(store).once()
    with store.database.session() as db:
        record = db.get(ContentProduction, row["id"])
        record.status, record.lease_token, record.lease_expires_at = "running", "stale", 1
        db.commit()
    FactoryWorker(store).once()
    result = store.get(project, row["id"])
    assert [step["agent"] for step in result["steps"]] == ["CEO", "PESQUISADOR"]


def test_cancel_between_video_creation_and_approval_never_renders(factory, monkeypatch):
    from ai_team import video_media
    from ai_team.content_factory import FactoryWorker
    from ai_team.video_store import VideoStore

    monkeypatch.setattr(
        video_media, "probe", lambda *_: {"width": 1, "height": 1, "duration": None}
    )
    store, project = factory
    asset = upload_logo(store, project)
    row = store.create(request(project, media_ids=[asset["id"]]))
    worker = FactoryWorker(store)
    for _ in range(3):
        worker.once()
    store.approve(project, row["id"], store.get(project, row["id"])["digest"])
    original = VideoStore.create

    def cancel_before_link(self, *args, **kwargs):
        video = original(self, *args, **kwargs)
        store.cancel(project, row["id"])
        return video

    monkeypatch.setattr(VideoStore, "create", cancel_before_link)
    worker.once()
    assert store.get(project, row["id"])["status"] == "cancelled"
    assert VideoStore(store.database).snapshot(project)["items"][0]["status"] == "cancelled"
    assert VideoStore(store.database).claim() is None


def test_office_reports_local_approval_without_inference(factory):
    from ai_team.content_factory import FactoryWorker
    from ai_team.content_factory_office import production_office
    from ai_team.office import office_snapshot

    store, project = factory
    store.create(request(project))
    for _ in range(3):
        FactoryWorker(store).once()
    result = production_office(store.database, office_snapshot([], worker_online=False))
    designer = next(a for a in result if a["id"] == "DESIGNER")
    assert designer["status"] == "awaiting_approval"
    assert designer["executor"] == "local" and not designer["animate"]
    assert "Sem inferência" in designer["history"][0]["deliverable"]


def test_failed_render_retry_requires_new_digest_and_approval(factory, monkeypatch):
    from ai_team import video_media
    from ai_team.content_factory import FactoryWorker
    from ai_team.content_factory_models import ContentProduction

    monkeypatch.setattr(
        video_media, "probe", lambda *_: {"width": 1, "height": 1, "duration": None}
    )
    store, project = factory
    asset = upload_logo(store, project)
    job = store.create(request(project, media_ids=[asset["id"]]))
    for _ in range(3):
        FactoryWorker(store).once()
    old = store.get(project, job["id"])
    with store.database.session() as db:
        row = db.get(ContentProduction, job["id"])
        row.status, row.stage = "failed", 4
        db.commit()
    resumed = store.resume(project, job["id"])
    assert resumed["status"] == "awaiting_approval" and resumed["revision"] == 1
    assert old["digest"] != resumed["digest"]
    with pytest.raises(HTTPException):
        store.approve(project, job["id"], old["digest"])
    assert not FactoryWorker(store).once()


@pytest.mark.parametrize("duration", ["nan", "inf", "-inf"])
def test_qa_rejects_nonfinite_duration(tmp_path, monkeypatch, duration):
    import json
    from types import SimpleNamespace

    from ai_team import content_factory_qa as qa

    path = tmp_path / "artifact.mp4"
    path.write_bytes(b"disposable-local-fixture")
    monkeypatch.setattr(qa, "executable_path", lambda: "/fixture/ffmpeg")
    monkeypatch.setattr(
        qa.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(
            stdout=json.dumps(
                {
                    "streams": [
                        {"codec_type": "video", "codec_name": "h264", "width": 720, "height": 1280}
                    ],
                    "format": {"duration": duration},
                }
            ).encode()
        ),
    )
    with pytest.raises(ValueError):
        qa.inspect_mp4(
            path, {"format": "vertical", "resolution": "720p", "scenes": [{"duration": 15}]}
        )
