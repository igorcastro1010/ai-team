"""Owner-only native job inventory and explicit pause; no general-purpose jobs proxy."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from .auth import require_owner
from .hermes import HermesClient
from .hermes_jobs import HermesJobs, JobsView, PauseView, jobs_snapshot

router = APIRouter(prefix="/hermes/jobs")
Owner = Annotated[str, Depends(require_owner)]


class PauseDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]


@router.get("", response_model=JobsView)
def cached_jobs(request: Request, owner: Owner):
    return jobs_snapshot(request.app.state.database)


@router.post("/inspect", response_model=JobsView)
def inspect_jobs(request: Request, owner: Owner):
    return HermesJobs(request.app.state.database, HermesClient(
        request.app.state.settings, database=request.app.state.database,
    )).inspect(
        owner
    )


@router.post("/{job_id}/pause", response_model=PauseView)
def pause_job(job_id: str, data: PauseDecision, request: Request, owner: Owner):
    return HermesJobs(request.app.state.database, HermesClient(
        request.app.state.settings, database=request.app.state.database,
    )).pause(
        job_id,
        owner,
    )
