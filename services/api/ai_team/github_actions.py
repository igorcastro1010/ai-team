"""Propostas imutáveis e fila de ações GitHub; toda escrita exige aprovação."""

import hashlib
import json
import re
import time
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update

from .github_client import GitHubClient, GitHubError
from .memory_safety import validate_text
from .models import Event, GitHubAction, GitHubVerification, Project, new_id


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1, max_length=36)
    operation: Literal["branch", "commit", "issue", "pull_request"]
    title: str = Field(min_length=5, max_length=180)
    branch: str = Field(default="", max_length=90)
    expected_sha: str = Field(default="", max_length=40)
    path: str = Field(default="", max_length=180)
    content: str = Field(default="", max_length=20000)
    body: str = Field(default="", max_length=8000)
    draft: bool = True

    @model_validator(mode="after")
    def validate_scope(self):
        validate_text(self.title + "\n" + self.content + "\n" + self.body, maximum=100000)
        if self.operation != "issue" and not re.fullmatch(
            r"codex/ai-team/[a-z0-9][a-z0-9-]{0,60}", self.branch
        ):
            raise ValueError("Branch deve estar no namespace codex/ai-team/")
        if self.operation in {"branch", "commit", "pull_request"} and not re.fullmatch(
            "[a-f0-9]{40}", self.expected_sha
        ):
            raise ValueError("Informe o SHA revisado de 40 caracteres")
        if self.operation == "commit":
            if not re.fullmatch(r"docs/agent-output/[a-z0-9][a-z0-9-]{0,80}\.md", self.path):
                raise ValueError("Nesta versão, commits somente em docs/agent-output/*.md")
            if not self.content.strip():
                raise ValueError("Informe o conteúdo textual do commit")
            if not re.match(r"(?:feat|fix|docs|test|chore)(?:\([a-z0-9-]+\))?: ", self.title):
                raise ValueError("Use uma mensagem de commit convencional")
        if re.search(
            r"-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}",
            self.title + self.content + self.body,
        ):
            raise ValueError("Não inclua credenciais na proposta")
        return self


def content_digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


class ActionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    payload: dict
    digest: str
    status: str
    result: dict
    error: str
    created_at: float


class GitHubStore:
    def __init__(self, database):
        self.database = database

    def snapshot(self):
        with self.database.session() as db:
            verification = db.get(GitHubVerification, "github")
            active = {"pending", "approved", "running"}
            actions = list(
                db.scalars(
                    select(GitHubAction)
                    .where(GitHubAction.status.in_(active))
                    .order_by(GitHubAction.created_at, GitHubAction.id)
                )
            )
            actions += list(
                db.scalars(
                    select(GitHubAction)
                    .where(GitHubAction.status.not_in(active))
                    .order_by(GitHubAction.created_at.desc(), GitHubAction.id)
                    .limit(200)
                )
            )
            return {
                "connection": verification.details if verification else None,
                "actions": [ActionView.model_validate(row).model_dump() for row in actions],
            }

    def verified(self, details, owner):
        with self.database.session() as db:
            db.merge(GitHubVerification(id="github", details=details))
            db.add(
                Event(
                    kind="github.verified",
                    summary="GitHub App: instalação seletiva verificada",
                    actor=owner,
                )
            )
            db.commit()

    def create(self, data, owner):
        payload = Proposal.model_validate(data).model_dump()
        with self.database.session() as db:
            if not db.get(Project, payload["project_id"]):
                raise HTTPException(404, "Projeto não encontrado")
            row = GitHubAction(
                project_id=payload["project_id"], payload=payload, digest=content_digest(payload)
            )
            db.add(row)
            db.flush()
            db.add(
                Event(
                    kind="github.proposed",
                    resource_id=row.id,
                    summary=f"Proposta GitHub: {payload['operation']}",
                    actor=owner,
                )
            )
            db.commit()
            return row

    def decide(self, action_id, digest, approve, owner):
        with self.database.session() as db:
            row = db.get(GitHubAction, action_id)
            if row is None:
                raise HTTPException(404, "Proposta não encontrada")
            status = "approved" if approve else "rejected"
            result = db.execute(
                update(GitHubAction)
                .where(
                    GitHubAction.id == action_id,
                    GitHubAction.status == "pending",
                    GitHubAction.digest == digest,
                )
                .values(status=status)
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Proposta já decidida ou conteúdo diferente do revisado")
            db.add(
                Event(
                    kind="github.decided",
                    resource_id=row.id,
                    summary=f"Proposta GitHub: {status}",
                    actor=owner,
                )
            )
            db.commit()
            db.refresh(row)
            return row

    def claim(self):
        now = int(time.time())
        with self.database.session() as db:
            expired = list(
                db.scalars(
                    select(GitHubAction).where(
                        GitHubAction.status == "running", GitHubAction.lease_expires_at <= now
                    )
                )
            )
            for row in expired:
                changed = db.execute(
                    update(GitHubAction)
                    .where(
                        GitHubAction.id == row.id,
                        GitHubAction.status == "running",
                        GitHubAction.lease_token == row.lease_token,
                        GitHubAction.lease_expires_at <= now,
                    )
                    .values(status="uncertain", error="Executor interrompido. Confira no GitHub.")
                )
                if changed.rowcount:
                    db.add(
                        Event(
                            kind="github.uncertain",
                            resource_id=row.id,
                            summary="Ação GitHub interrompida; sem repetição automática",
                        )
                    )
            db.commit()
            row = db.scalar(
                select(GitHubAction)
                .where(GitHubAction.status == "approved")
                .order_by(GitHubAction.created_at, GitHubAction.id)
                .limit(1)
            )
            if row is None:
                return None
            token = new_id()
            claimed = db.execute(
                update(GitHubAction)
                .where(GitHubAction.id == row.id, GitHubAction.status == "approved")
                .values(status="running", lease_token=token, lease_expires_at=now + 300)
            )
            db.commit()
            if claimed.rowcount != 1:
                return None
            db.refresh(row)
            return row

    def finish(self, claim, status, result=None, error=""):
        with self.database.session() as db:
            updated = db.execute(
                update(GitHubAction)
                .where(
                    GitHubAction.id == claim.id,
                    GitHubAction.status == "running",
                    GitHubAction.lease_token == claim.lease_token,
                )
                .values(
                    status=status,
                    result=result or {},
                    error=error,
                    lease_token="",
                    lease_expires_at=0,
                )
            )
            if updated.rowcount:
                db.add(
                    Event(
                        kind=f"github.{status}",
                        resource_id=claim.id,
                        summary=f"Execução GitHub: {status}",
                    )
                )
            db.commit()


class GitHubWorker:
    def __init__(self, database, provider_factory=GitHubClient, tick=None):
        self.store, self.provider_factory = GitHubStore(database), provider_factory
        self.tick = tick or (lambda: None)

    def once(self):
        claim = self.store.claim()
        if claim is None:
            return False
        provider = None
        try:
            payload = Proposal.model_validate(claim.payload).model_dump()
            if content_digest(payload) != claim.digest:
                raise ValueError("Conteúdo diferente da aprovação")
            provider = self.provider_factory()
            provider.tick = self.tick
            result = provider.execute(payload)
            self.store.finish(
                claim,
                "uncertain" if result.get("requires_review") else "succeeded",
                result,
                "SHA do PR mudou durante a criação; revise no GitHub."
                if result.get("requires_review")
                else "",
            )
        except Exception as error:
            uncertain = provider is not None and getattr(provider, "mutation_attempted", False)
            reason = (
                str(error) if isinstance(error, GitHubError) else "Falha de validação ou executor."
            )
            self.store.finish(
                claim,
                "uncertain" if uncertain else "failed",
                error=reason
                + " "
                + (
                    "Confira a ação no GitHub antes de propor novamente; sem repetição automática."
                    if uncertain
                    else "Ação bloqueada ou integração indisponível. Revise a configuração."
                ),
            )
        finally:
            if provider:
                provider.close()
        return True
