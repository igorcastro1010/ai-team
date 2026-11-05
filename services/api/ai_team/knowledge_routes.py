from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from .auth import require_owner
from .knowledge_graph import MAX_NODES, KnowledgeGraph

router = APIRouter(prefix="/knowledge")
Owner = Annotated[str, Depends(require_owner)]


@router.get("/{project_id}/graph")
def graph(
    project_id: str,
    request: Request,
    owner: Owner,
    limit: Annotated[int, Query(ge=1, le=MAX_NODES)] = MAX_NODES,
):
    return KnowledgeGraph(request.app.state.database).snapshot(project_id, limit=limit)
