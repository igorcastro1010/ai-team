from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .auth import require_owner
from .workflow import WorkflowStore

router = APIRouter()
Owner = Annotated[str, Depends(require_owner)]


class RunInput(BaseModel):
    project_id: Annotated[str, StringConstraints(min_length=1, max_length=36)]
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=5000)]
    consent: Literal[True]
    executor: Literal["codex", "hermes"] = "codex"


class Decision(BaseModel):
    stage: int = Field(ge=1, le=4)
    approve: bool


class RunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    executor: str
    project_id: str
    prompt: str
    mode: str
    scope: str
    status: str
    stage: int
    steps: list[dict]
    calls: int
    input_tokens: int
    output_tokens: int
    error: str
    created_at: int


@router.get("/runs", response_model=list[RunView])
def list_runs(request: Request, owner: Owner):
    return WorkflowStore(request.app.state.database).all()


@router.post("/runs", response_model=RunView, status_code=201)
def request_run(data: RunInput, request: Request, owner: Owner):
    return WorkflowStore(request.app.state.database).create(
        data.project_id, data.prompt, owner, executor=data.executor
    )


@router.get("/runs/{run_id}", response_model=RunView)
def get_run(run_id: str, request: Request, owner: Owner):
    return WorkflowStore(request.app.state.database).get(run_id)


@router.post("/runs/{run_id}/decision", response_model=RunView)
def decide(run_id: str, data: Decision, request: Request, owner: Owner):
    return WorkflowStore(request.app.state.database).decide(run_id, data.stage, data.approve, owner)


@router.post("/runs/{run_id}/cancel", response_model=RunView)
def cancel(run_id: str, request: Request, owner: Owner):
    return WorkflowStore(request.app.state.database).cancel(run_id, owner)


@router.post("/runs/{run_id}/resume", response_model=RunView)
def resume(run_id: str, request: Request, owner: Owner):
    return WorkflowStore(request.app.state.database).unblock(run_id, owner)
