from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from .auth import require_owner
from .schedules import ScheduleInput, ScheduleStore

router = APIRouter(prefix="/schedules")
Owner = Annotated[str, Depends(require_owner)]


class ScheduleView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    prompt: str
    mode: str
    interval_seconds: int
    next_run_at: int
    expires_at: int
    max_runs: int
    emitted: int
    status: str
    created_at: int


@router.get("", response_model=list[ScheduleView])
def list_schedules(request: Request, owner: Owner):
    return ScheduleStore(request.app.state.database).all()


@router.post("", response_model=ScheduleView, status_code=201)
def create(data: ScheduleInput, request: Request, owner: Owner):
    return ScheduleStore(request.app.state.database).create(data.model_dump(), owner)


@router.post("/{schedule_id}/cancel", response_model=ScheduleView)
def cancel(schedule_id: str, request: Request, owner: Owner):
    return ScheduleStore(request.app.state.database).cancel(schedule_id, owner)
