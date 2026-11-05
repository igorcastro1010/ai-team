import io
import zipfile
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .auth import require_owner
from .models import RepositoryJob
from .repository_policy import RepositoryPolicy
from .repository_runs import RepositoryStore
from .workflow import WorkflowStore

router = APIRouter(prefix="/repository-runs")
Owner = Annotated[str, Depends(require_owner)]


class RepositoryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1, max_length=36)
    prompt: str = Field(min_length=5, max_length=5000)
    executor: Literal["codex", "hermes"] = "codex"
    consent: Literal[True]
    policy: RepositoryPolicy


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    approve: bool


@router.get("")
def list_runs(request: Request, owner: Owner):
    store = RepositoryStore(request.app.state.database)
    with store.database.session() as db:
        ids = list(db.scalars(select(RepositoryJob.run_id).limit(100)))
    return [store.view(run_id) for run_id in reversed(ids)]


@router.post("", status_code=201)
def create(data: RepositoryRequest, request: Request, owner: Owner):
    store = RepositoryStore(request.app.state.database)
    run = store.create(data.project_id, data.prompt, data.policy, owner, data.executor)
    return store.view(run.id)


@router.get("/{run_id}")
def get_run(run_id: str, request: Request, owner: Owner):
    return RepositoryStore(request.app.state.database).view(run_id)


@router.post("/{run_id}/decision")
def decide(run_id: str, data: Decision, request: Request, owner: Owner):
    return RepositoryStore(request.app.state.database).decide(
        run_id, data.digest, data.approve, owner
    )


@router.post("/{run_id}/cancel")
def cancel(run_id: str, request: Request, owner: Owner):
    store = RepositoryStore(request.app.state.database)
    store.view(run_id)
    WorkflowStore(store.database).cancel(run_id, owner)
    return store.view(run_id)


@router.post("/{run_id}/publish")
def publish_run(run_id: str, data: Decision, request: Request, owner: Owner):
    if not data.approve:
        raise HTTPException(422, "Publicação exige autorização afirmativa")
    return RepositoryStore(request.app.state.database).request_publication(
        run_id, data.digest, owner
    )


@router.get("/{run_id}/artifacts")
def artifacts(run_id: str, request: Request, owner: Owner):
    state = RepositoryStore(request.app.state.database).view(run_id)["state"]
    if "bundle" not in state:
        raise HTTPException(409, "Artefatos ainda indisponíveis")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in state["bundle"]["files"]:
            archive.writestr(file["path"], file["content"])
        archive.writestr("review.diff", state.get("diff", ""))
    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="ai-team-repository.zip"',
        },
    )
