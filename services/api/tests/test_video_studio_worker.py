from test_video import create
from test_video import store as store


def test_1080_admission_is_disabled_until_server_enables_it(store, monkeypatch):
    import uuid

    import pytest
    from fastapi import HTTPException

    from ai_team.models import Project
    from ai_team.video_routes import VideoInput

    project = str(uuid.uuid4())
    with store.database.session() as db:
        db.add(Project(id=project, name="1080 control"))
        db.commit()
    monkeypatch.delenv("AI_TEAM_VIDEO_1080P", raising=False)
    data = VideoInput(
        project_id=project,
        request_id=uuid.uuid4(),
        title="1080",
        resolution="1080p",
        consent=True,
        scenes=[{"text": "Teste", "duration": 1}],
    )
    with pytest.raises(HTTPException) as blocked:
        store.create(data)
    assert blocked.value.status_code == 409
    monkeypatch.setenv("AI_TEAM_VIDEO_1080P", "1")
    assert store.create(data)["resolution"] == "1080p"


def test_video_progress_is_persistent_monotonic_and_requires_active_lease(store):
    _, job = create(store)
    store.decide(job["id"], job["digest"], True)
    assert store.get(job["id"])["phase"] == "queued"
    claimed = store.claim()
    assert not store.progress(job["id"], "wrong", 90, "encoding")
    assert store.progress(job["id"], claimed["lease_token"], 30, "encoding")
    assert not store.progress(job["id"], claimed["lease_token"], 10, "encoding")
    assert store.get(job["id"])["progress"] == 30
    store.database.engine.dispose()
    assert store.get(job["id"])["progress"] == 30
    store.cancel(job["id"])
    assert store.get(job["id"])["phase"] == "cancelled"
    assert not store.progress(job["id"], claimed["lease_token"], 50, "encoding")


def test_worker_checks_approved_media_hash_before_starting_ffmpeg(store, monkeypatch, tmp_path):
    import uuid

    from ai_team import video_media, video_worker
    from ai_team.models import Project
    from ai_team.video_routes import VideoInput

    monkeypatch.setenv("AI_TEAM_VIDEO_ROOT", str(tmp_path / "library"))
    monkeypatch.setattr(
        video_media, "probe", lambda *_: {"width": 2, "height": 2, "duration": None}
    )
    project = str(uuid.uuid4())
    with store.database.session() as db:
        db.add(Project(id=project, name="Immutable media"))
        db.commit()
    media = video_media.MediaStore(store.database)
    asset = media.upload(project, "foto.png", "image/png", b"\x89PNG\r\n\x1a\nfixture")
    data = VideoInput(
        project_id=project,
        request_id=uuid.uuid4(),
        title="Imagem",
        consent=True,
        scenes=[{"media_id": asset["id"], "duration": 1}],
    )
    job = store.create(data)
    assert job["_media"][asset["id"]]["sha256"] == asset["sha256"]
    store.decide(job["id"], job["digest"], True)
    path, _ = media.content(project, asset["id"])
    path.write_bytes(b"\x89PNG\r\n\x1a\nchanged")
    monkeypatch.setattr(
        video_worker,
        "render",
        lambda *_args, **_kw: (_ for _ in ()).throw(AssertionError("Must not render")),
    )
    assert video_worker.VideoWorker(store, output=tmp_path / "output").once()
    assert store.get(job["id"])["status"] == "failed"
    assert not (tmp_path / "output" / f"{job['id']}.mp4").exists()


def test_worker_exports_real_uploaded_image_clip_audio_and_records_progress(
    store, tmp_path, monkeypatch
):
    import uuid

    import pytest
    from test_video_render_studio import ffmpeg, probe

    from ai_team.models import Project
    from ai_team.video_media import MediaStore
    from ai_team.video_render import renderer_status
    from ai_team.video_routes import VideoInput
    from ai_team.video_worker import VideoWorker

    if not renderer_status()["available"]:
        pytest.skip("Local FFmpeg/font required")
    monkeypatch.setenv("AI_TEAM_VIDEO_ROOT", str(tmp_path / "library"))
    project = str(uuid.uuid4())
    with store.database.session() as db:
        db.add(Project(id=project, name="Studio real worker"))
        db.commit()
    image, clip, audio = tmp_path / "image.png", tmp_path / "clip.mp4", tmp_path / "tone.wav"
    ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=320x240", "-frames:v", "1", str(image))
    ffmpeg("-f", "lavfi", "-i", "testsrc2=s=320x240:r=24", "-t", "1", "-c:v", "libx264", str(clip))
    ffmpeg("-f", "lavfi", "-i", "sine=frequency=440", "-t", "1", str(audio))
    media = MediaStore(store.database)
    assets = [
        media.upload(project, p.name, m, p.read_bytes())
        for p, m in [(image, "image/png"), (clip, "video/mp4"), (audio, "audio/wav")]
    ]
    data = VideoInput(
        project_id=project,
        request_id=uuid.uuid4(),
        title="Workflow real",
        format="square",
        consent=True,
        scenes=[
            {
                "media_id": assets[0]["id"],
                "text": "Imagem",
                "duration": 2,
                "animation": "zoom",
                "transition": "fade",
            },
            {
                "media_id": assets[1]["id"],
                "text": "Clipe",
                "duration": 2,
                "text_animation": "slide",
            },
        ],
        audio={"media_id": assets[2]["id"], "volume": 0.2, "fade_in": 0.3, "fade_out": 0.3},
    )
    job = store.create(data)
    store.decide(job["id"], job["digest"], True)
    assert VideoWorker(store, output=tmp_path / "output").once()
    saved = store.get(job["id"])
    assert saved["status"] == "completed", saved["error"]
    assert saved["progress"] == 100
    metadata = probe(tmp_path / "output" / f"{job['id']}.mp4")
    assert {"video", "audio"} <= {s["codec_type"] for s in metadata["streams"]}
    assert float(metadata["format"]["duration"]) == 4
