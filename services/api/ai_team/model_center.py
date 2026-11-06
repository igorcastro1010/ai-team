"""Zero-charge policy: unknown eligibility/cost never authorizes dispatch."""

import os
import time
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .github_actions import content_digest
from .memory_safety import validate_text
from .model_center_models import ModelCall, ModelPreference, ModelProviderState, ModelRequest
from .models import Event, Project, Run, RunExecutor

ROLES = ("CEO", "DEV", "DESIGNER", "QA", "PESQUISADOR")
GEMINI_MODEL = "gemini-2.5-flash-lite"
CATALOG = [
    {
        "provider": "gemini",
        "model": GEMINI_MODEL,
        "capabilities": ["text", "json"],
        "cost": "requires_free_eligibility",
        "dispatch": "verified_free_only",
    },
    {
        "provider": "codex",
        "model": "codex-supervised",
        "capabilities": ["code", "review"],
        "cost": "subscription_limits_unknown",
        "dispatch": "supervised_handoff",
    },
]


class CentralDeferred(RuntimeError):
    def __init__(self, reason, status="waiting_model", *, not_dispatched=True):
        super().__init__(reason)
        self.status, self.not_dispatched = status, not_dispatched


class Preference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["automatic", "manual"] = "automatic"
    provider: Literal["gemini", "codex"] = "gemini"
    model: Literal["gemini-2.5-flash-lite", "codex-supervised"] = GEMINI_MODEL
    enabled: bool = False
    quotas_confirmed: bool = False
    rpm: int = Field(default=2, ge=1, le=2)
    rpd: int = Field(default=10, ge=1, le=10)
    tpm: int = Field(default=40000, ge=1000, le=40000)

    @model_validator(mode="after")
    def bound_model(self):
        if (self.provider == "gemini") != (self.model == GEMINI_MODEL):
            raise ValueError("Modelo não corresponde ao provedor")
        if self.enabled and (self.provider != "gemini" or not self.quotas_confirmed):
            raise ValueError("Somente Gemini com cotas confirmadas pode ser autorizado")
        return self


class ModelCenter:
    def __init__(self, database):
        self.database = database
        with database.session() as db:
            if not db.get(ModelProviderState, "gemini"):
                db.add(ModelProviderState(id="gemini"))
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()

    def _project(self, db, project_id):
        if db.get(Project, project_id) is None:
            raise HTTPException(404, "Projeto não encontrado")

    def preference(self, project_id, agent):
        if agent not in ROLES:
            raise HTTPException(422, "Agente inválido")
        with self.database.session() as db:
            self._project(db, project_id)
            row = db.get(ModelPreference, (project_id, agent))
            return {
                **(row.policy if row else Preference().model_dump()),
                "agent": agent,
                "authorized_until": row.authorized_until if row else 0,
            }

    def configure(self, project_id, agent, policy, actor):
        self.preference(project_id, agent)
        policy = Preference.model_validate(policy).model_dump()
        with self.database.session() as db:
            db.merge(
                ModelPreference(
                    project_id=project_id,
                    agent=agent,
                    policy=policy,
                    authorized_until=int(time.time()) + 86400 if policy["enabled"] else 0,
                )
            )
            db.add(
                Event(
                    kind="models.configured",
                    resource_id=project_id,
                    actor=actor,
                    summary="Preferência e limites de modelo revisados; sem inferência",
                )
            )
            db.commit()
        return self.preference(project_id, agent)

    def request(self, project_id, request_id, prompt, actor):
        validate_text(prompt, maximum=5000)
        digest = content_digest({"project_id": project_id, "prompt": prompt})
        with self.database.session() as db:
            self._project(db, project_id)
            # Serialize request deduplication with the same project mutex as memory/optimizer.
            db.execute(update(Project).where(Project.id == project_id).values(name=Project.name))
            existing = db.scalar(
                select(ModelRequest).where(
                    ModelRequest.project_id == project_id, ModelRequest.request_id == request_id
                )
            )
            if existing:
                if existing.digest != digest:
                    raise HTTPException(409, "Identificador já vinculado a outro conteúdo")
                return db.get(Run, existing.run_id)
            project = db.get(Project, project_id)
            run = Run(project_id=project_id, prompt=prompt, mode=project.mode, scope="draft_only")
            run.executor_binding = RunExecutor(executor="central")
            db.add(run)
            db.flush()
            db.add(
                ModelRequest(
                    project_id=project_id, request_id=request_id, digest=digest, run_id=run.id
                )
            )
            db.add(
                Event(
                    kind="run.requested",
                    resource_id=run.id,
                    actor=actor,
                    summary="Solicitação central autorizada; política revalidada no worker",
                )
            )
            db.commit()
            return run

    def log(self, run, agent, provider, model, status, reason, **values):
        with self.database.session() as db:
            row = ModelCall(
                project_id=run.project_id,
                run_id=run.id,
                stage=run.stage,
                agent=agent,
                provider=provider,
                model=model,
                status=status,
                reason=reason,
                **values,
            )
            db.add(row)
            db.add(Event(kind="models.routed", resource_id=run.id, actor=agent, summary=reason))
            db.commit()
            return row.id

    def choose(self, run, agent):
        policy = self.preference(run.project_id, agent)
        complex_code = agent == "DEV" or run.scope != "draft_only"
        codex = policy["provider"] == "codex" if policy["mode"] == "manual" else complex_code
        if codex:
            reason = (
                "Codex requer execução supervisionada; custo/cota não verificáveis pela central"
            )
            self.log(run, agent, "codex", "codex-supervised", "awaiting_codex", reason)
            raise CentralDeferred(reason, "awaiting_codex")
        if not policy["enabled"] or policy["authorized_until"] <= time.time():
            reason = "Autorize chamadas gratuitas deste agente por até 24h antes da execução"
        elif not policy["quotas_confirmed"]:
            reason = "Cotas do projeto desconhecidas; confirme limites no AI Studio"
        else:
            return policy
        self.log(run, agent, "gemini", GEMINI_MODEL, "waiting_model", reason)
        raise CentralDeferred(reason)

    def snapshot(self, project_id):
        preferences = [self.preference(project_id, role) for role in ROLES]
        with self.database.session() as db:
            observation = db.get(ModelProviderState, "gemini").observation
            rows = db.scalars(
                select(ModelCall)
                .where(ModelCall.project_id == project_id)
                .order_by(ModelCall.created_at.desc(), ModelCall.id)
                .limit(100)
            ).all()
            waiting = db.scalars(
                select(Run)
                .join(RunExecutor)
                .where(
                    Run.project_id == project_id,
                    RunExecutor.executor == "central",
                    Run.status.in_(["waiting_model", "waiting_quota", "awaiting_codex"]),
                )
            ).all()
            return {
                "catalog": CATALOG,
                "preferences": preferences,
                "providers": [
                    {
                        "id": "gemini",
                        "configured": bool(os.getenv("AI_TEAM_GEMINI_API_KEY")),
                        "observation": observation,
                    },
                    {"id": "codex", "configured": False, "status": "supervised_only"},
                    {"id": "hermes", "status": "existing_executor_preserved"},
                ],
                "history": [
                    {c.name: getattr(r, c.name) for c in ModelCall.__table__.columns} for r in rows
                ],
                "waiting": [
                    {"id": r.id, "stage": r.stage, "status": r.status, "reason": r.error}
                    for r in waiting
                ],
                "measured_savings": None,
                "provider_quotas": "operator_verified_not_discovered",
                "local_caps": {"rpm": 2, "rpd": 10, "tpm": 40000},
            }
