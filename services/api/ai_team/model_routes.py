"""Owner-only control plane. No generation or long connection checks in HTTP."""

import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator
from sqlalchemy import select, update

from .auth import require_owner
from .github_actions import content_digest
from .memory_safety import validate_text
from .model_center import ModelCenter, Preference
from .model_center_models import ModelProbe, ModelProviderState
from .models import Event, Run, new_id
from .orchestration import BOUNDARIES, INSTRUCTIONS, STAGES, Draft, DraftContent
from .run_routes import RunView
from .workflow import WorkflowStore

router = APIRouter(prefix="/model-center/{project_id}")
Owner = Annotated[str, Depends(require_owner)]


class Consent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent: StrictBool

    @model_validator(mode="after")
    def explicit(self):
        if not self.consent:
            raise ValueError("Consentimento explícito necessário")
        return self


class RequestInput(Consent):
    request_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.:-]+$")
    prompt: str = Field(min_length=5, max_length=5000)


class HandoffInput(Consent):
    digest: str = Field(pattern="^[a-f0-9]{64}$")
    draft: DraftContent


def scoped(request, project_id, run_id):
    run = WorkflowStore(request.app.state.database).get(run_id)
    if run.project_id != project_id or run.executor != "central":
        raise HTTPException(404, "Execução central não encontrada neste projeto")
    return run


def handoff_payload(run):
    if run.status != "awaiting_codex" or not 0 <= run.stage < len(STAGES):
        raise HTTPException(409, "Execução não aguarda Codex supervisionado")
    payload = {
        "run_id": run.id,
        "project_id": run.project_id,
        "stage": run.stage,
        "role": STAGES[run.stage],
        "instructions": INSTRUCTIONS[run.stage] + BOUNDARIES,
        "context": {"request": run.prompt, "previous_steps": run.steps},
        "response_schema": DraftContent.model_json_schema(),
    }
    return {**payload, "digest": content_digest(payload)}


@router.get("")
def snapshot(project_id: str, request: Request, owner: Owner):
    return ModelCenter(request.app.state.database).snapshot(project_id)


@router.put("/preferences/{agent}")
def configure(project_id: str, agent: str, data: Preference, request: Request, owner: Owner):
    return ModelCenter(request.app.state.database).configure(project_id, agent, data, owner)


@router.post("/check", status_code=202)
def check(project_id: str, request: Request, owner: Owner):
    center = ModelCenter(request.app.state.database)
    center.preference(project_id, "CEO")
    with center.database.session() as db:
        db.execute(
            update(ModelProviderState)
            .where(ModelProviderState.id == "gemini")
            .values(locked_at=int(time.time()))
        )
        existing = db.scalar(select(ModelProbe).where(ModelProbe.status.in_(["queued", "running"])))
        if existing is None:
            existing = ModelProbe(project_id=project_id)
            db.add(existing)
        db.add(
            Event(
                kind="models.check_requested",
                resource_id=project_id,
                actor=owner,
                summary="Verificação sem geração enfileirada para o worker",
            )
        )
        db.commit()
        return {"status": existing.status, "id": existing.id, "inference_calls": 0}


@router.post("/requests", response_model=RunView, status_code=201)
def create_request(project_id: str, data: RequestInput, request: Request, owner: Owner):
    return ModelCenter(request.app.state.database).request(
        project_id, data.request_id, data.prompt, owner
    )


@router.post("/resume/{run_id}", response_model=RunView)
def resume(project_id: str, run_id: str, data: Consent, request: Request, owner: Owner):
    run = scoped(request, project_id, run_id)
    if run.status not in {"waiting_model", "waiting_quota"}:
        raise HTTPException(409, "Somente espera sem resultado incerto pode ser reavaliada")
    with request.app.state.database.session() as db:
        changed = db.execute(
            update(Run)
            .where(Run.id == run.id, Run.status == run.status, Run.stage == run.stage)
            .values(status="queued", error="")
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Execução mudou; atualize antes de retomar")
        db.add(
            Event(
                kind="models.resumed",
                resource_id=run.id,
                actor=owner,
                summary="Reavaliação autorizada; elegibilidade/cota serão verificadas",
            )
        )
        db.commit()
    return WorkflowStore(request.app.state.database).get(run.id)


@router.get("/handoff/{run_id}")
def handoff(project_id: str, run_id: str, request: Request, owner: Owner):
    return handoff_payload(scoped(request, project_id, run_id))


@router.post("/handoff/{run_id}", response_model=RunView)
def complete_handoff(
    project_id: str, run_id: str, data: HandoffInput, request: Request, owner: Owner
):
    run = scoped(request, project_id, run_id)
    if handoff_payload(run)["digest"] != data.digest:
        raise HTTPException(409, "Contexto diferente do revisado")
    validate_text(data.draft.model_dump_json(), maximum=100000)
    with request.app.state.database.session() as db:
        token = new_id()
        changed = db.execute(
            update(Run)
            .where(Run.id == run.id, Run.status == "awaiting_codex", Run.stage == run.stage)
            .values(status="running", lease_token=token, lease_expires_at=int(time.time()) + 120)
        )
        if changed.rowcount != 1:
            raise HTTPException(409, "Contexto já utilizado")
        db.add(
            Event(
                kind="models.manual_result",
                resource_id=run.id,
                actor=owner,
                summary="Resultado manual informado; execução Codex e tokens não atestados",
            )
        )
        db.commit()
        run = db.get(Run, run.id)
    WorkflowStore(request.app.state.database).save_step(run, Draft(**data.draft.model_dump()))
    return WorkflowStore(request.app.state.database).get(run.id)
