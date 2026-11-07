import uuid

import pytest
from fastapi import HTTPException

from ai_team.config import Settings
from ai_team.db import Database
from ai_team.models import Project


@pytest.fixture
def studio(tmp_path, monkeypatch):
    from ai_team.video_media import MediaStore
    from ai_team.video_studio_routes import StudioStore

    monkeypatch.setenv("AI_TEAM_VIDEO_ROOT", str(tmp_path / "media"))
    database = Database(Settings(database_url=f"sqlite:///{tmp_path / 'studio.db'}"))
    database.initialize()
    project = str(uuid.uuid4())
    with database.session() as db:
        db.add(Project(id=project, name="Studio"))
        db.commit()
    return MediaStore(database), StudioStore(database), project


def document(**changes):
    return {"title": "Olá", "scenes": [{"text": "Olá", "duration": 2}], **changes}


def test_draft_compare_and_swap_and_restart(studio):
    _, store, project = studio
    assert store.draft(project) == {"revision": 0, "document": None}
    saved = store.save_draft(project, 0, document())
    assert saved["revision"] == 1
    assert type(store)(store.database).draft(project) == saved
    with pytest.raises(HTTPException) as error:
        store.save_draft(project, 0, document(title="Conflito"))
    assert error.value.status_code == 409
    with pytest.raises(HTTPException):
        store.save_draft(project, 1, document(title="api_key=" + "x" * 30))
    assert store.draft(project) == saved


def test_templates_are_six_editable_copies_and_project_scoped(studio):
    _, store, project = studio
    assert len(store.templates(project)["items"]) == 6
    template = store.save_template(project, "Minha abertura", document())
    assert template in store.templates(project)["items"]
    with pytest.raises(HTTPException) as error:
        store.templates(str(uuid.uuid4()))
    assert error.value.status_code == 404


def test_media_scope_manifest_integrity_and_type(studio, monkeypatch):
    from ai_team import video_media

    media, _, project = studio
    monkeypatch.setattr(
        video_media, "probe", lambda *_: {"width": 2, "height": 2, "duration": None}
    )
    asset = media.upload(project, "foto.png", "image/png", b"\x89PNG\r\n\x1a\nfixture")
    assert "path" not in asset and asset["kind"] == "image"
    data = document(scenes=[{"media_id": asset["id"], "duration": 2}])
    manifest = media.manifest(project, data)
    paths = media.resolve(project, manifest)
    assert paths[asset["id"]].is_file()
    with pytest.raises(HTTPException):
        media.manifest(str(uuid.uuid4()), data)
    with pytest.raises(HTTPException):
        media.manifest(project, document(audio={"media_id": asset["id"]}))
    paths[asset["id"]].write_bytes(b"changed")
    with pytest.raises(HTTPException):
        media.resolve(project, manifest)


@pytest.mark.parametrize(
    "name,mime,body",
    [
        ("x.svg", "image/svg+xml", b"<svg/>"),
        ("x.png", "image/png", b"<svg/>"),
        ("../x.png", "image/png", b"\x89PNG\r\n\x1a\n"),
        ("x.gif", "image/gif", b"GIF89a"),
    ],
)
def test_reject_unsafe_media(studio, name, mime, body):
    media, _, project = studio
    with pytest.raises(HTTPException):
        media.upload(project, name, mime, body)
    assert media.snapshot(project) == {"items": []}


def test_media_quotas_are_rejected(studio, monkeypatch, tmp_path):
    from ai_team import video_media

    media, _, project = studio
    monkeypatch.setattr(
        video_media, "probe", lambda *_: {"width": 2, "height": 2, "duration": None}
    )
    monkeypatch.setattr(video_media, "MAX_FILES", 0)
    with pytest.raises(HTTPException) as error:
        media.upload(project, "foto.png", "image/png", b"\x89PNG\r\n\x1a\nfixture")
    assert error.value.status_code == 409
    assert not list((tmp_path / "media").rglob("*.png"))
    monkeypatch.setattr(video_media, "MAX_FILES", 100)
    monkeypatch.setattr(video_media, "MAX_PROJECT_BYTES", 2)
    with pytest.raises(HTTPException) as error:
        media.upload(project, "foto.png", "image/png", b"\x89PNG\r\n\x1a\nfixture")
    assert error.value.status_code == 409
    assert media.snapshot(project) == {"items": []}


def test_media_missing_project_size_and_collision_fail_closed(studio, monkeypatch, tmp_path):
    from ai_team import video_media

    media, _, project = studio
    body = b"\x89PNG\r\n\x1a\nfixture"
    monkeypatch.setattr(
        video_media, "probe", lambda *_: {"width": 2, "height": 2, "duration": None}
    )
    with pytest.raises(HTTPException) as error:
        media.upload(str(uuid.uuid4()), "foto.png", "image/png", body)
    assert error.value.status_code == 404
    assert not (tmp_path / "media").exists()
    monkeypatch.setattr(video_media, "MAX_UPLOAD", 1)
    with pytest.raises(HTTPException) as error:
        media.upload(project, "foto.png", "image/png", body)
    assert error.value.status_code == 413
    monkeypatch.setattr(video_media, "MAX_UPLOAD", 25 * 1024 * 1024)
    fixed = uuid.uuid4()
    monkeypatch.setattr(video_media, "uuid4", lambda: fixed)
    asset = media.upload(project, "foto.png", "image/png", body)
    with pytest.raises(HTTPException):
        media.upload(project, "foto.png", "image/png", body)
    assert media.content(project, asset["id"])[0].read_bytes() == body


def test_probe_timeout_is_sanitized(studio, monkeypatch):
    import subprocess

    from ai_team import video_media

    media, _, project = studio
    monkeypatch.setattr(video_media.shutil, "which", lambda _: "ffprobe")

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 8 and kwargs["shell"] is False
        assert "-protocol_whitelist" in args[0] and "-max_alloc" in args[0]
        assert not any("TOKEN" in key or "KEY" in key for key in kwargs["env"])
        raise subprocess.TimeoutExpired("privatepath", 8, stderr="secret-error")

    monkeypatch.setattr(video_media.subprocess, "run", timeout)
    with pytest.raises(HTTPException) as error:
        media.upload(project, "foto.png", "image/png", b"\x89PNG\r\n\x1a\nfixture")
    assert error.value.status_code == 422
    assert "secret-error" not in error.value.detail and "privatepath" not in error.value.detail
    assert media.snapshot(project) == {"items": []}


def test_api_auth_csrf_scope_range_and_revision(studio, monkeypatch):
    from fastapi.testclient import TestClient

    from ai_team import video_media
    from ai_team.auth import create_owner
    from ai_team.main import create_app
    from ai_team.video_studio_routes import router

    media, _, project = studio
    monkeypatch.setattr(
        video_media, "probe", lambda *_: {"width": 2, "height": 2, "duration": None}
    )
    app = create_app(media.database.settings, media.database)
    app.include_router(router)
    with media.database.session() as db:
        create_owner(db, "owner", "StudioTests123!Only")
    base = f"/video-studio/{project}"
    with TestClient(app, headers={"origin": "http://localhost:3000"}) as client:
        assert client.get(base + "/media").status_code == 401
        assert (
            client.post(
                "/auth/login", json={"username": "owner", "password": "StudioTests123!Only"}
            ).status_code
            == 200
        )
        body = b"\x89PNG\r\n\x1a\nfixture"
        assert (
            client.post(
                base + "/media?name=foto.png",
                content=body,
                headers={"origin": "http://evil", "content-type": "image/png"},
            ).status_code
            == 403
        )
        response = client.post(
            base + "/media?name=foto.png", content=body, headers={"content-type": "image/png"}
        )
        assert response.status_code == 201, response.text
        asset = response.json()
        url = base + f"/media/{asset['id']}/content"
        ranged = client.get(url, headers={"range": "bytes=0-7"})
        assert ranged.status_code == 206 and ranged.content == body[:8]
        assert (
            client.get(f"/video-studio/{uuid.uuid4()}/media/{asset['id']}/content").status_code
            == 404
        )
        data = {"revision": 0, "document": document()}
        assert client.put(base + "/draft", json=data).status_code == 200
        assert client.put(base + "/draft", json=data).status_code == 409
        assert client.get(base + "/draft").json()["revision"] == 1
        assert (
            client.post(
                base + "/render",
                json={"request_id": str(uuid.uuid4()), "document": document(), "consent": False},
            ).status_code
            == 422
        )
        request = {"request_id": str(uuid.uuid4()), "document": document(), "consent": True}
        response = client.post(base + "/render", json=request)
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "pending_approval"
        assert client.post(base + "/render", json=request).json()["id"] == response.json()["id"]
        assert (
            client.post(
                base + "/render",
                json={
                    **request,
                    "request_id": str(uuid.uuid4()),
                    "document": document(scenes=[{"text": "", "duration": 2}]),
                },
            ).status_code
            == 422
        )


def test_real_probe_accepts_png_and_rejects_corruption(studio):
    import base64

    media, _, project = studio
    # A real one pixel PNG, no decoder mocks.
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1s"
        "AAAAASUVORK5CYII="
    )
    try:
        asset = media.upload(project, "pixel.png", "image/png", png)
    except HTTPException as error:
        if error.status_code == 503:
            pytest.skip("FFprobe local indisponível")
        raise
    assert asset["width"] == asset["height"] == 1
    with pytest.raises(HTTPException):
        media.upload(project, "quebrado.png", "image/png", b"\x89PNG\r\n\x1a\ncorruption")


def test_builtin_templates_cover_the_six_requested_use_cases():
    from ai_team.video_templates import builtin_templates

    templates = builtin_templates()
    assert {item["name"] for item in templates} == {
        "Reels de divulgação",
        "Apresentação de produtos",
        "Promoções",
        "Tutorial rápido",
        "Anúncios de serviços",
        "Vídeo institucional",
    }
    assert all(len(item["document"]["scenes"]) >= 2 for item in templates)
    assert all(not scene["media_id"] for item in templates for scene in item["document"]["scenes"])
    templates[0]["document"]["title"] = "Mutado"
    assert builtin_templates()[0]["document"]["title"] != "Mutado"


@pytest.mark.parametrize(
    ("mime", "extension", "source", "codec"),
    [
        ("image/jpeg", "jpg", "color=c=orange:s=32x32", None),
        ("image/webp", "webp", "color=c=orange:s=32x32", "libwebp"),
        ("video/webm", "webm", "color=c=orange:s=32x32:r=24", "libvpx-vp9"),
        ("audio/mpeg", "mp3", "sine=frequency=440", "libmp3lame"),
        ("audio/ogg", "ogg", "sine=frequency=440", "libvorbis"),
    ],
)
def test_real_upload_matrix_for_advertised_formats(
    studio, tmp_path, mime, extension, source, codec
):
    from test_video_render_studio import ffmpeg

    from ai_team.video_render import executable_path

    if not executable_path():
        pytest.skip("Local FFmpeg required")
    media, _, project = studio
    path = tmp_path / f"sample.{extension}"
    arguments = ["-f", "lavfi", "-i", source]
    if mime.startswith("image/"):
        arguments += ["-frames:v", "1"]
    else:
        arguments += ["-t", "0.25"]
    if codec:
        arguments += ["-c:a" if mime.startswith("audio/") else "-c:v", codec]
    arguments += ["-threads", "1", str(path)]
    ffmpeg(*arguments)
    asset = media.upload(project, path.name, mime, path.read_bytes())
    assert asset["mime"] == mime
    assert asset["kind"] == mime.split("/")[0]
    assert asset["bytes"] == path.stat().st_size
