"""Owner-only short HTTP operations. Rendering occurs exclusively in video_worker."""

from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from .auth import require_owner
from .video_render import artifact_root, renderer_status
from .video_store import VideoStore

router = APIRouter(prefix="/videos")
Owner = Annotated[str, Depends(require_owner)]


class SceneInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=240)
    duration: int = Field(ge=1, le=20, strict=True)

    @field_validator("text")
    @classmethod
    def readable(cls, value):
        if not value.strip() or any(ord(c) < 32 and c != "\n" for c in value):
            raise ValueError("Texto inválido")
        return value.strip()


class VideoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    request_id: UUID
    title: str = Field(min_length=1, max_length=120)
    format: Literal["vertical", "horizontal"] = "vertical"
    scenes: list[SceneInput] = Field(min_length=1, max_length=6)
    consent: Literal[True]

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("Consentimento explícito necessário")
        return value

    @model_validator(mode="after")
    def bounded(self):
        if sum(scene.duration for scene in self.scenes) > 60 or not self.title.strip():
            raise ValueError("Use até 60 segundos e informe um título")
        return self


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str = Field(pattern="^[a-f0-9]{64}$")
    approve: StrictBool


@router.get("")
def videos(project_id: UUID, request: Request, owner: Owner):
    return {
        **VideoStore(request.app.state.database).snapshot(str(project_id)),
        "renderer": renderer_status(),
    }


@router.post("", status_code=201)
def create(data: VideoInput, request: Request, owner: Owner):
    return VideoStore(request.app.state.database).create(data, owner)


@router.post("/{job_id}/decision")
def decide(job_id: UUID, data: DecisionInput, request: Request, owner: Owner):
    return VideoStore(request.app.state.database).decide(
        str(job_id), data.digest, data.approve, owner
    )


@router.post("/{job_id}/cancel")
def cancel(job_id: UUID, request: Request, owner: Owner):
    return VideoStore(request.app.state.database).cancel(str(job_id), owner)


@router.get("/{job_id}/download")
def download(job_id: UUID, request: Request, owner: Owner):
    job = VideoStore(request.app.state.database).get(str(job_id))
    path = artifact_root() / f"{job_id}.mp4"
    if job["status"] != "completed" or not path.is_file() or path.is_symlink():
        raise HTTPException(409, "Vídeo ainda não disponível")
    if path.resolve().parent != artifact_root().resolve():
        raise HTTPException(409, "Artefato inválido")
    return FileResponse(Path(path), media_type="video/mp4", filename=f"video-{job_id}.mp4")
