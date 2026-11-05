"""Owner-only issue proposals and local tracking; all remote writes stay in worker queue."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .auth import require_owner
from .github_client import GitHubClient, GitHubError
from .issue_store import Agent, IssueProposal, IssueStore, Priority, Status

router = APIRouter(prefix="/issues")
Owner = Annotated[str, Depends(require_owner)]


class IssuePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent: Agent | None = None
    priority: Priority | None = None
    status: Status | None = None
    branch: str | None = Field(default=None, max_length=90)
    commit_sha: str | None = Field(default=None, max_length=40)
    pull_request_number: int | None = Field(default=None, gt=0, le=2147483647)


@router.get("")
def snapshot(
    request: Request,
    owner: Owner,
    project_id: str,
    agent: Agent | None = None,
    status: Status | None = None,
    priority: Priority | None = None,
):
    return IssueStore(request.app.state.database).list(
        project_id, agent=agent, status=status, priority=priority
    )


@router.post("", status_code=201)
def propose(data: IssueProposal, request: Request, owner: Owner):
    return IssueStore(request.app.state.database).create(data.model_dump(), owner)


@router.patch("/{issue_id}")
def update(issue_id: str, data: IssuePatch, request: Request, owner: Owner):
    try:
        # Validate the merged metadata in the store, preserving omitted fields.
        return IssueStore(request.app.state.database).update(
            issue_id, data.model_dump(exclude_unset=True), owner
        )
    except ValidationError:
        raise HTTPException(422, "Metadados locais inválidos") from None


@router.post("/{issue_id}/sync")
def sync(issue_id: str, request: Request, owner: Owner):
    class LazyProvider:
        def issue(self, number):
            provider = GitHubClient()
            try:
                return provider.issue(number)
            finally:
                provider.close()

    try:
        return IssueStore(request.app.state.database).sync(issue_id, LazyProvider(), owner)
    except GitHubError as error:
        raise HTTPException(502, str(error)) from None
