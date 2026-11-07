"""Owner-only local studio library, optimistic drafts and editable templates."""

import asyncio
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import func, select, update

from .auth import require_owner
from .memory_safety import validate_text
from .models import Project
from .video_media import MAX_UPLOAD, MediaStore
from .video_schema import StudioDocument
from .video_studio_models import VideoDraft, VideoTemplate
from .video_templates import builtin_templates

router = APIRouter(prefix="/video-studio")
Owner = Annotated[str, Depends(require_owner)]


def clean_document(document):
    value = StudioDocument.model_validate(document).model_dump(mode="json")
    try:
        validate_text(json.dumps(value, ensure_ascii=False), maximum=16000)
    except ValueError:
        raise HTTPException(422, "Documento inválido ou contém credenciais") from None
    return value


class StudioStore:
    def __init__(self, database):
        self.database = database

    @staticmethod
    def project(db, project_id, lock=False):
        exists = (db.execute(update(Project).where(Project.id == project_id)
                             .values(name=Project.name)).rowcount
                  if lock else db.get(Project, project_id))
        if not exists:
            raise HTTPException(404, "Projeto não encontrado")

    def draft(self, project_id):
        with self.database.session() as db:
            self.project(db, project_id)
            row = db.get(VideoDraft, project_id)
            return {"revision": row.revision, "document": row.document} if row else {
                "revision": 0, "document": None}

    def save_draft(self, project_id, revision, document):
        value = clean_document(document)
        MediaStore(self.database).manifest(project_id, value)
        with self.database.session() as db:
            self.project(db, project_id, lock=True)
            row = db.get(VideoDraft, project_id)
            if (row.revision if row else 0) != revision:
                raise HTTPException(409, "Rascunho atualizado em outra sessão; recarregue")
            if row:
                row.revision += 1
                row.document = value
            else:
                row = VideoDraft(project_id=project_id, revision=1, document=value)
                db.add(row)
            db.commit()
            return {"revision": row.revision, "document": row.document}

    def templates(self, project_id):
        with self.database.session() as db:
            self.project(db, project_id)
            return {"items": builtin_templates() + [
                {"id": row.id, "name": row.name, "document": row.document}
                for row in db.scalars(select(VideoTemplate).where(
                    VideoTemplate.project_id == project_id).order_by(VideoTemplate.id).limit(100))]}

    def save_template(self, project_id, name, document):
        value = clean_document(document)
        try:
            validate_text(name, maximum=80)
            if not name.strip():
                raise ValueError
        except ValueError:
            raise HTTPException(422, "Nome do template inválido") from None
        MediaStore(self.database).manifest(project_id, value)
        with self.database.session() as db:
            self.project(db, project_id, lock=True)
            count = db.scalar(select(func.count()).select_from(VideoTemplate).where(
                VideoTemplate.project_id == project_id))
            if count >= 100:
                raise HTTPException(409, "Limite de templates do projeto atingido")
            row = VideoTemplate(project_id=project_id, name=name.strip(), document=value)
            db.add(row)
            db.commit()
            return {"id": row.id, "name": row.name, "document": row.document}


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    document: StudioDocument


class TemplateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    document: StudioDocument


class RenderInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    document: StudioDocument
    consent: Literal[True]

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Consentimento explícito necessário")
        return value


@router.get("/{project_id}/media")
def media(project_id: UUID, request: Request, owner: Owner):
    return MediaStore(request.app.state.database).snapshot(str(project_id))


@router.post("/{project_id}/media", status_code=201)
async def upload(project_id: UUID, name: str, request: Request, owner: Owner):
    # Blocking filesystem/probe/DB work belongs on the thread pool, never the event loop.
    from starlette.concurrency import run_in_threadpool

    if not hasattr(request.app.state, "video_upload_semaphore"):
        request.app.state.video_upload_semaphore = asyncio.Semaphore(2)
    async with request.app.state.video_upload_semaphore:
        store = MediaStore(request.app.state.database)
        await run_in_threadpool(store.require_project, str(project_id))
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_UPLOAD:
                raise HTTPException(413, "Upload máximo de25MB")
            body.extend(chunk)
        return await run_in_threadpool(
            store.upload, str(project_id), name,
            request.headers.get("content-type", ""), bytes(body))


@router.get("/{project_id}/media/{asset_id}/content")
def content(project_id: UUID, asset_id: UUID, request: Request, owner: Owner):
    path, asset = MediaStore(request.app.state.database).content(str(project_id), str(asset_id))
    return FileResponse(path, media_type=asset["mime"], headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/{project_id}/draft")
def draft(project_id: UUID, request: Request, owner: Owner):
    return StudioStore(request.app.state.database).draft(str(project_id))


@router.put("/{project_id}/draft")
def save_draft(project_id: UUID, data: DraftInput, request: Request, owner: Owner):
    return StudioStore(request.app.state.database).save_draft(
        str(project_id), data.revision, data.document.model_dump(mode="json"))


@router.get("/{project_id}/templates")
def templates(project_id: UUID, request: Request, owner: Owner):
    return StudioStore(request.app.state.database).templates(str(project_id))


@router.post("/{project_id}/templates", status_code=201)
def save_template(project_id: UUID, data: TemplateInput, request: Request, owner: Owner):
    return StudioStore(request.app.state.database).save_template(
        str(project_id), data.name, data.document.model_dump(mode="json"))


@router.post("/{project_id}/render", status_code=201)
def render(project_id: UUID, data: RenderInput, request: Request, owner: Owner):
    from .video_routes import VideoInput
    from .video_store import VideoStore

    document = clean_document(data.document.model_dump(mode="json"))
    try:
        payload = VideoInput(project_id=project_id, request_id=data.request_id,
                             consent=data.consent, **document)
    except ValidationError:
        raise HTTPException(422, "Roteiro inválido para renderização") from None
    return VideoStore(request.app.state.database).create(payload, owner)
