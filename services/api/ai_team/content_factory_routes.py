from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from .auth import require_owner
from .content_factory import FactoryStore, ProductionInput
from .video_schema import StudioDocument

router = APIRouter(prefix="/content-factory")
Owner = Annotated[str, Depends(require_owner)]


class EditInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=0, strict=True)
    document: StudioDocument


class ApprovalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str = Field(pattern="^[a-f0-9]{64}$")


class ResumeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    media_ids: list[UUID] = Field(max_length=10)


@router.post("", status_code=201)
def create(data: ProductionInput, request: Request, owner: Owner):
    return FactoryStore(request.app.state.database).create(data)


@router.get("/{project_id}")
def snapshot(project_id: UUID, request: Request, owner: Owner):
    return FactoryStore(request.app.state.database).snapshot(str(project_id))


@router.put("/{project_id}/{production_id}")
def edit(project_id: UUID, production_id: UUID, data: EditInput, request: Request, owner: Owner):
    return FactoryStore(request.app.state.database).edit(
        str(project_id), str(production_id), data.revision, data.document.model_dump(mode="json")
    )


@router.post("/{project_id}/{production_id}/approve")
def approve(
    project_id: UUID, production_id: UUID, data: ApprovalInput, request: Request, owner: Owner
):
    return FactoryStore(request.app.state.database).approve(
        str(project_id), str(production_id), data.digest
    )


@router.post("/{project_id}/{production_id}/cancel")
def cancel(project_id: UUID, production_id: UUID, request: Request, owner: Owner):
    return FactoryStore(request.app.state.database).cancel(str(project_id), str(production_id))


@router.post("/{project_id}/{production_id}/resume")
def resume(
    project_id: UUID, production_id: UUID, data: ResumeInput, request: Request, owner: Owner
):
    return FactoryStore(request.app.state.database).resume(
        str(project_id), str(production_id), data.media_ids
    )
