"""Immutable bounded local uploads; media bytes never come from model URLs."""

import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import func, select, update

from .memory_safety import validate_text
from .models import Project
from .video_render import artifact_root, executable_path
from .video_schema import StudioDocument
from .video_studio_models import MediaAsset

MAX_UPLOAD = 25 * 1024 * 1024
MAX_PROJECT_BYTES = 500 * 1024 * 1024
MAX_FILES = 100
MIME_ALIASES = {"audio/x-wav": "audio/wav", "audio/wave": "audio/wav",
                "image/jpg": "image/jpeg"}
FORMATS = {
    "image/png": ("png", "image", "png_pipe"),
    "image/jpeg": ("jpg", "image", "jpeg_pipe"),
    "image/webp": ("webp", "image", "webp_pipe"),
    "video/mp4": ("mp4", "video", "mov"),
    "video/webm": ("webm", "video", "matroska"),
    "audio/mpeg": ("mp3", "audio", "mp3"),
    "audio/wav": ("wav", "audio", "wav"),
    "audio/ogg": ("ogg", "audio", "ogg"),
}


def invalid():
    return HTTPException(422, "Mídia inválida, indisponível ou fora dos limites")


def magic(body, mime):
    return {
        "image/png": body.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": body.startswith(b"\xff\xd8\xff"),
        "image/webp": body[:4] == b"RIFF" and body[8:12] == b"WEBP",
        "video/mp4": len(body) >= 12 and body[4:8] == b"ftyp",
        "video/webm": body.startswith(b"\x1aE\xdf\xa3"),
        "audio/mpeg": body.startswith(b"ID3") or (
            len(body) > 1 and body[0] == 255 and body[1] & 224 == 224),
        "audio/wav": body[:4] == b"RIFF" and body[8:12] == b"WAVE",
        "audio/ogg": body.startswith(b"OggS"),
    }.get(mime, False)


def probe(path, mime):
    ffmpeg = executable_path()
    binary = shutil.which("ffprobe")
    if not binary and ffmpeg:
        sibling = Path(ffmpeg).with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
        binary = str(sibling) if sibling.is_file() else None
    if not binary:
        raise HTTPException(503, "FFprobe local necessário para validar mídia")
    env = {key: os.environ[key] for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")
           if key in os.environ}
    try:
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(
                [binary, "-v", "error", "-max_alloc", "67108864",
                 "-protocol_whitelist", "file", "-probesize", "1048576",
                 "-analyzeduration", "3000000", "-f", FORMATS[mime][2],
                 "-show_entries", "stream=codec_type,width,height,duration:format=duration",
                 "-of", "json", str(path)],
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.DEVNULL,
                timeout=8, env=env, shell=False,
            )
            if result.returncode or output.tell() > 65536:
                raise invalid()
            output.seek(0)
            data = json.load(output)
        streams = data.get("streams", [])
        expected = "audio" if mime.startswith("audio/") else "video"
        matching = [s for s in streams if s.get("codec_type") == expected]
        if len(matching) != 1 or len(streams) > 3:
            raise invalid()
        stream = matching[0]
        width, height = stream.get("width"), stream.get("height")
        if expected == "video" and (
            not isinstance(width, int) or not isinstance(height, int)
            or not 1 <= width <= 4096 or not 1 <= height <= 4096
            or width * height > 16000000
        ):
            raise invalid()
        duration = None
        if not mime.startswith("image/"):
            duration = float(data.get("format", {}).get("duration") or stream.get("duration"))
            if not math.isfinite(duration) or not 0 < duration <= 300:
                raise invalid()
        return {"width": width, "height": height, "duration": duration}
    except (OSError, ValueError, TypeError, subprocess.SubprocessError):
        raise invalid() from None


def asset_view(asset):
    return {key: getattr(asset, key) for key in (
        "id", "name", "kind", "mime", "bytes", "sha256", "duration", "width", "height")}


def media_path(project_id, asset_id, extension):
    try:
        project_id, asset_id = str(UUID(project_id)), str(UUID(asset_id))
        if extension not in {item[0] for item in FORMATS.values()}:
            raise ValueError
    except (ValueError, TypeError):
        raise invalid() from None
    root = artifact_root().absolute()
    path = root / "media" / project_id / f"{asset_id}.{extension}"
    for item in (path, *path.parents):
        if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
            raise invalid()
    if not path.resolve().is_relative_to(root.resolve()):
        raise invalid()
    return path


class MediaStore:
    def __init__(self, database):
        self.database = database

    def require_project(self, project_id):
        with self.database.session() as db:
            if not db.get(Project, project_id):
                raise HTTPException(404, "Projeto não encontrado")

    def snapshot(self, project_id):
        with self.database.session() as db:
            if not db.get(Project, project_id):
                raise HTTPException(404, "Projeto não encontrado")
            return {"items": [asset_view(asset) for asset in db.scalars(
                select(MediaAsset).where(MediaAsset.project_id == project_id)
                .order_by(MediaAsset.created_at.desc()).limit(MAX_FILES))]}

    def upload(self, project_id, name, mime, body):
        self.require_project(project_id)
        mime = mime.split(";", 1)[0].strip().lower()
        mime = MIME_ALIASES.get(mime, mime)
        try:
            validate_text(name, maximum=120)
        except ValueError:
            raise invalid() from None
        if (not name.strip() or any(c in name for c in '/\\:')
                or any(ord(c) < 32 for c in name)
                or mime not in FORMATS or not body or not magic(body, mime)):
            raise invalid()
        if len(body) > MAX_UPLOAD:
            raise HTTPException(413, "Upload máximo de25MB")
        extension, kind, _ = FORMATS[mime]
        asset_id = str(uuid4())
        path = media_path(project_id, asset_id, extension)
        path.parent.mkdir(parents=True, exist_ok=True)
        created = False
        try:
            with path.open("xb") as target:
                created = True
                target.write(body)
            metadata = probe(path, mime)
            with self.database.session() as db:
                if not db.execute(update(Project).where(Project.id == project_id)
                                  .values(name=Project.name)).rowcount:
                    raise HTTPException(404, "Projeto não encontrado")
                count, total = db.execute(select(func.count(), func.coalesce(
                    func.sum(MediaAsset.bytes), 0)).where(
                        MediaAsset.project_id == project_id)).one()
                if count >= MAX_FILES or total + len(body) > MAX_PROJECT_BYTES:
                    raise HTTPException(409, "Limite de mídia do projeto atingido")
                asset = MediaAsset(id=asset_id, project_id=project_id, name=name.strip(),
                                   mime=mime, kind=kind, extension=extension, bytes=len(body),
                                   sha256=hashlib.sha256(body).hexdigest(), **metadata)
                db.add(asset)
                db.commit()
                return asset_view(asset)
        except OSError:
            if created:
                path.unlink(missing_ok=True)
            raise invalid() from None
        except BaseException:
            if created:
                path.unlink(missing_ok=True)
            raise

    def content(self, project_id, asset_id):
        with self.database.session() as db:
            asset = db.get(MediaAsset, asset_id)
            if not asset or asset.project_id != project_id:
                raise HTTPException(404, "Mídia não encontrada")
            path = media_path(project_id, asset.id, asset.extension)
            if not path.is_file() or path.stat().st_size != asset.bytes:
                raise invalid()
            return path, asset_view(asset)

    def manifest(self, project_id, document):
        doc = (document if isinstance(document, StudioDocument)
               else StudioDocument.model_validate(document))
        requested = [(str(s.media_id), ("image", "video"))
                     for s in doc.scenes if s.media_id]
        if doc.audio:
            requested.append((str(doc.audio.media_id), ("audio",)))
        result = {}
        for asset_id, kinds in requested:
            _, item = self.content(project_id, asset_id)
            if item["kind"] not in kinds:
                raise invalid()
            result[asset_id] = {k: item[k] for k in (
                "sha256", "kind", "mime", "bytes", "duration", "width", "height")}
        self.resolve(project_id, result)
        return result

    def resolve(self, project_id, manifest):
        if not isinstance(manifest, dict) or len(manifest) > 7:
            raise invalid()
        result = {}
        for asset_id, expected in manifest.items():
            path, item = self.content(project_id, asset_id)
            if (not isinstance(expected, dict) or expected != {k: item[k] for k in (
                "sha256", "kind", "mime", "bytes", "duration", "width", "height")}
                    or path.stat().st_size > MAX_UPLOAD
                    or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]):
                raise invalid()
            result[asset_id] = path
        return result
