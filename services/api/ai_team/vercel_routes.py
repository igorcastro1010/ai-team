from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .auth import require_owner
from .models import Event, ProviderObservation
from .vercel_access import VercelClient, VercelVault

router = APIRouter(prefix="/vercel")
Owner = Annotated[str, Depends(require_owner)]


class ProjectView(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_]{1,100}$")
    name: Literal["ai-team"]


class DeploymentView(BaseModel):
    id: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=40)
    created_at: int | None = None


class Observation(BaseModel):
    verified_at: int = Field(ge=0)
    project: ProjectView | None
    deployments: list[DeploymentView] = Field(max_length=10)


def observation_snapshot(database):
    with database.session() as db:
        row = db.get(ProviderObservation, "vercel")
        return {"connection": Observation.model_validate(row.details).model_dump() if row else None}


def save_observation(database, details, owner):
    sanitized = Observation.model_validate(details).model_dump()
    with database.session() as db:
        db.merge(ProviderObservation(id="vercel", details=sanitized))
        db.add(
            Event(
                kind="vercel.inspected",
                actor=owner,
                summary="Consulta Vercel registrada; nenhuma publicação realizada",
            )
        )
        db.commit()
    return sanitized


@router.get("")
def snapshot(request: Request, owner: Owner):
    return observation_snapshot(request.app.state.database)


@router.post("/inspect", response_model=Observation)
def inspect(request: Request, owner: Owner):
    client = None
    try:
        credentials = VercelVault().load()
        if credentials is None:
            raise HTTPException(409, "Configure a credencial Vercel no cofre do executor")
        client = VercelClient(
            credentials["token"],
            credentials.get("team_id"),
            project_id=credentials.get("project_id"),
        )
        return save_observation(request.app.state.database, client.probe(), owner)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            502, "Consulta Vercel indisponível. Confira a credencial e o escopo."
        ) from None
    finally:
        if client:
            client.close()
