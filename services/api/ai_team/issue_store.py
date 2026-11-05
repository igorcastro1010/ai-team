"""Bounded local proposals, request idempotency, and read-only issue synchronization."""

import re
import time
from typing import Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .github_actions import ActionView, Proposal, content_digest
from .github_client import REPOSITORY, GitHubError
from .issue_models import IssueLink
from .models import Event, GitHubAction, Project, Task

Agent = Literal["CEO", "DEV", "DESIGNER", "QA", "PESQUISADOR"]
Priority = Literal["low", "medium", "high", "critical"]
Status = Literal["todo", "in_progress", "blocked", "done"]


class IssueMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent: Agent = "DEV"
    priority: Priority = "medium"
    status: Status = "todo"
    branch: str = Field(default="", max_length=90)
    commit_sha: str = Field(default="", max_length=40)
    pull_request_number: int | None = Field(default=None, gt=0, le=2147483647)

    @model_validator(mode="after")
    def validate_links(self):
        if self.branch and not re.fullmatch(r"codex/ai-team/[a-z0-9][a-z0-9-]{0,60}", self.branch):
            raise ValueError("Branch fora do namespace autorizado")
        if self.commit_sha and not re.fullmatch("[a-f0-9]{40}", self.commit_sha):
            raise ValueError("SHA deve ter 40 caracteres hexadecimais")
        return self


class IssueProposal(IssueMetadata):
    request_id: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.:-]+$")
    project_id: str = Field(min_length=1, max_length=36)
    task_id: str | None = Field(default=None, min_length=1, max_length=36)
    parent_issue_id: str | None = Field(default=None, min_length=1, max_length=36)
    title: str = Field(min_length=5, max_length=180)
    body: str = Field(default="", max_length=8000)

    @model_validator(mode="after")
    def validate_proposal(self):
        Proposal(project_id=self.project_id, operation="issue", title=self.title, body=self.body)
        return self


class IssueStore:
    def __init__(self, database):
        self.database = database

    def _view(self, db, row):
        action = db.get(GitHubAction, row.action_id)
        return {
            **{
                column.name: getattr(row, column.name)
                for column in IssueLink.__table__.columns
                if column.name != "request_digest"
            },
            "title": action.payload["title"],
            "body": action.payload["body"],
            "action": ActionView.model_validate(action).model_dump(),
        }

    def _get(self, db, issue_id):
        row = db.get(IssueLink, issue_id)
        if row is None:
            raise HTTPException(404, "Issue local não encontrada")
        return row

    def create(self, data, actor):
        data = IssueProposal.model_validate(data).model_dump()
        digest = content_digest(data)
        payload = Proposal(
            project_id=data["project_id"], operation="issue", title=data["title"], body=data["body"]
        ).model_dump()
        with self.database.session() as db:
            if not db.get(Project, data["project_id"]):
                raise HTTPException(404, "Projeto não encontrado")
            existing = db.scalar(
                select(IssueLink).where(
                    IssueLink.project_id == data["project_id"],
                    IssueLink.request_id == data["request_id"],
                )
            )
            if existing:
                return self._dedup(db, existing, digest)
            if data["task_id"]:
                task = db.get(Task, data["task_id"])
                if task is None or task.project_id != data["project_id"]:
                    raise HTTPException(404, "Tarefa fora do projeto")
            if data["parent_issue_id"]:
                parent = self._get(db, data["parent_issue_id"])
                if parent.project_id != data["project_id"]:
                    raise HTTPException(404, "Issue pai fora do projeto")
            action = GitHubAction(
                project_id=data["project_id"], payload=payload, digest=content_digest(payload)
            )
            db.add(action)
            db.flush()
            row = IssueLink(
                **{k: v for k, v in data.items() if k not in {"title", "body"}},
                action_id=action.id,
                request_digest=digest,
            )
            db.add(row)
            db.add(
                Event(
                    kind="issue.proposed",
                    resource_id=action.id,
                    summary="Issue local preparada; publicação requer revisão",
                    actor=actor,
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                existing = db.scalar(
                    select(IssueLink).where(
                        IssueLink.project_id == data["project_id"],
                        IssueLink.request_id == data["request_id"],
                    )
                )
                if existing is None:
                    raise HTTPException(409, "Conflito de associação") from None
                return self._dedup(db, existing, digest)
            return self._view(db, row)

    def _dedup(self, db, row, digest):
        if row.request_digest != digest:
            raise HTTPException(409, "request_id já vinculado a outro conteúdo")
        return self._view(db, row)

    def list(self, project_id, *, agent=None, status=None, priority=None):
        with self.database.session() as db:
            if not db.get(Project, project_id):
                raise HTTPException(404, "Projeto não encontrado")
            query = select(IssueLink).where(IssueLink.project_id == project_id)
            for key, value in {"agent": agent, "status": status, "priority": priority}.items():
                if value is not None:
                    query = query.where(getattr(IssueLink, key) == value)
            rows = db.scalars(query.order_by(IssueLink.created_at.desc(), IssueLink.id).limit(200))
            return {"issues": [self._view(db, row) for row in rows]}

    def update(self, issue_id, data, actor):
        with self.database.session() as db:
            row = self._get(db, issue_id)
            current = {key: getattr(row, key) for key in IssueMetadata.model_fields}
            validated = IssueMetadata.model_validate({**current, **data}).model_dump()
            for key, value in validated.items():
                setattr(row, key, value)
            db.add(
                Event(
                    kind="issue.updated",
                    resource_id=row.id,
                    summary="Associação local da issue atualizada",
                    actor=actor,
                )
            )
            db.commit()
            return self._view(db, row)

    def prepare_task(self, task_id, request_id):
        with self.database.session() as db:
            task = db.get(Task, task_id)
            if task is None:
                raise HTTPException(404, "Tarefa não encontrada")
            data = {
                "project_id": task.project_id,
                "task_id": task.id,
                "request_id": request_id,
                "title": task.title,
                "body": task.description,
                "agent": task.agent,
            }
        return self.create(data, "CEO")

    def sync(self, issue_id, provider, actor):
        with self.database.session() as db:
            row = self._get(db, issue_id)
            action = db.get(GitHubAction, row.action_id)
            number = action.result.get("number")
            if action.status != "succeeded" or type(number) is not int or number <= 0:
                raise HTTPException(409, "Publicação não confirmada; reconciliar manualmente")
        remote = provider.issue(number)
        if (
            remote.get("number") != number
            or remote.get("state") not in {"open", "closed"}
            or "pull_request" in remote
            or remote.get("html_url") != f"https://github.com/{REPOSITORY}/issues/{number}"
        ):
            raise GitHubError("Resposta de issue fora do escopo autorizado")
        with self.database.session() as db:
            row = self._get(db, issue_id)
            row.remote_state, row.synced_at = remote["state"], int(time.time())
            db.add(
                Event(
                    kind="issue.synced",
                    resource_id=row.id,
                    summary="Estado remoto consultado sem escrita GitHub",
                    actor=actor,
                )
            )
            db.commit()
            return self._view(db, row)
