"""Owner-only local optimizer previews and budget configuration."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import require_owner
from .token_optimizer import OptimizerStore, estimate

router = APIRouter(prefix="/projects/{project_id}/optimizer")
Owner = Annotated[str, Depends(require_owner)]


class BudgetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["project", "agent", "task"]
    scope_id: str = Field(default="", max_length=80)
    limit: int = Field(ge=1, le=100000000)


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    context: dict
    budget: int = Field(default=50000, ge=1, le=500000)

    @field_validator("context")
    @classmethod
    def bounded_context(cls, context):
        if estimate(context) > 250000:
            raise ValueError("Contexto excede 250000 bytes")
        return context


@router.get("")
def summary(project_id: str, request: Request, owner: Owner):
    return OptimizerStore(request.app.state.database).summary(project_id)


@router.put("/budgets")
def budget(project_id: str, data: BudgetInput, request: Request, owner: Owner):
    return OptimizerStore(request.app.state.database).set_budget(
        project_id, data.scope, data.scope_id, data.limit, owner
    )


@router.post("/preview")
def preview(project_id: str, data: PreviewInput, request: Request, owner: Owner):
    from .memory_store import MemoryStore

    database = request.app.state.database
    store = OptimizerStore(database)
    store.summary(project_id)  # Validate isolation before retrieval.
    memory = MemoryStore(database)
    return store.prepare(
        project_id=project_id,
        agent="CEO",
        task_id="preview",
        stage=0,
        instructions="preview",
        context=data.context,
        memories=memory.search(project_id, str(data.context.get("request", "")), limit=6),
        revision=memory.revision(project_id),
        permissions="owner-preview",
        budget=data.budget,
    )
