from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from .auth import require_owner
from .hermes import HermesClient
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
        return {"connection": Observation.model_validate(row.details).model_dump() if row else None}


@router.get("")
def snapshot(request: Request, owner: Owner):
    return observation_snapshot(request.app.state.database)


@router.post("/inspect", response_model=Observation)
def inspect(request: Request, owner: Owner):
    result = Observation.model_validate(
        HermesClient(request.app.state.settings).inspect()
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
