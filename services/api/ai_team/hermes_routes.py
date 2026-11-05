from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, StringConstraints

from .auth import require_owner
from .hermes import HermesClient
from .hermes_jobs import jobs_snapshot
from .hermes_journal import HermesJournal
from .hermes_monitor import ReconciliationStore
from .hermes_operations import HermesOperations
from .models import Event, ProviderObservation

router = APIRouter(prefix="/hermes")
Owner = Annotated[str, Depends(require_owner)]


class Observation(BaseModel):
    status: Literal["not_configured", "unavailable", "unsafe_configuration", "reachable"]
    checked_at: int | None
    inference_verified: Literal[False] = False
    text_only: Literal[True] = True


def observation_snapshot(database):
    with database.session() as db:
        row = db.get(ProviderObservation, "hermes")
        return {
            "connection": Observation.model_validate(row.details).model_dump() if row else None,
            "executions": HermesJournal(database).page(),
            "monitor": ReconciliationStore(database).snapshot(),
            "jobs": jobs_snapshot(database),
        }


@router.get("")
def snapshot(request: Request, owner: Owner):
    return observation_snapshot(request.app.state.database)


@router.post("/inspect", response_model=Observation)
def inspect(request: Request, owner: Owner):
    result = Observation.model_validate(
        HermesClient(request.app.state.settings, database=request.app.state.database).inspect()
    ).model_dump()
    with request.app.state.database.session() as db:
        db.merge(ProviderObservation(id="hermes", details=result))
        db.add(
            Event(
                kind="hermes.inspected",
                actor=owner,
                summary=f"Diagnóstico Hermes: {result['status']}; sem inferência",
            )
        )
        db.commit()
    return result


class StopDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: Literal[True]


@router.get("/executions")
def executions(
    request: Request,
    owner: Owner,
    before: Annotated[str | None, StringConstraints(max_length=36)] = None,
):
    return HermesJournal(request.app.state.database).page(before=before)


@router.post("/executions/{attempt_id}/refresh")
def refresh_execution(attempt_id: str, request: Request, owner: Owner):
    return HermesOperations(
        request.app.state.database,
        HermesClient(request.app.state.settings, database=request.app.state.database),
    ).refresh(attempt_id)


@router.post("/executions/{attempt_id}/stop")
def stop_execution(attempt_id: str, data: StopDecision, request: Request, owner: Owner):
    return HermesOperations(
        request.app.state.database,
        HermesClient(request.app.state.settings, database=request.app.state.database),
    ).stop(attempt_id)
