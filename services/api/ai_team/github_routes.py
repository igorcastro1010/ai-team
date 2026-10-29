from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .auth import require_owner
from .github_actions import ActionView, GitHubStore, Proposal
from .github_client import GitHubClient, GitHubError

router = APIRouter(prefix="/github")
Owner = Annotated[str, Depends(require_owner)]


class Decision(BaseModel):
    digest: str = Field(max_length=64)
    approve: bool


@router.get("")
def snapshot(request: Request, owner: Owner):
    return GitHubStore(request.app.state.database).snapshot()


@router.post("/verify")
def verify(request: Request, owner: Owner):
    client = None
    try:
        client = GitHubClient()
        details = client.verify()
        details["head_sha"] = client.head(details)
        GitHubStore(request.app.state.database).verified(details, owner)
        return details
    except GitHubError as error:
        raise HTTPException(502, str(error)) from None
    except Exception:
        raise HTTPException(502, "Não foi possível verificar a App no cofre") from None
    finally:
        if client:
            client.close()


@router.post("/proposals", response_model=ActionView, status_code=201)
def propose(data: Proposal, request: Request, owner: Owner):
    return GitHubStore(request.app.state.database).create(data.model_dump(), owner)


@router.post("/proposals/{action_id}/decision", response_model=ActionView)
def decide(action_id: str, data: Decision, request: Request, owner: Owner):
    return GitHubStore(request.app.state.database).decide(
        action_id, data.digest, data.approve, owner
    )
