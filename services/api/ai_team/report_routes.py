import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, or_, select

from .auth import require_owner
from .models import GitHubAction, Project, Run, Schedule, ScheduleOccurrence, Task

router = APIRouter()
Owner = Annotated[str, Depends(require_owner)]


@router.get("/reports")
def report(
    request: Request,
    owner: Owner,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before_created_at: Annotated[int | None, Query(ge=0)] = None,
    before_id: Annotated[str | None, Query(min_length=1, max_length=36)] = None,
):
    if (before_created_at is None) != (before_id is None):
        raise HTTPException(422, "Informe os dois campos do cursor")
    with request.app.state.database.session() as db:

        def count(model):
            return db.scalar(select(func.count()).select_from(model))

        def statuses(model):
            return dict(db.execute(select(model.status, func.count()).group_by(model.status)).all())

        calls, inputs, outputs = db.execute(
            select(
                func.coalesce(func.sum(Run.calls), 0),
                func.coalesce(func.sum(Run.input_tokens), 0),
                func.coalesce(func.sum(Run.output_tokens), 0),
            )
        ).one()
        summary = {
            "projects": count(Project),
            "tasks": statuses(Task),
            "runs": statuses(Run),
            "github": statuses(GitHubAction),
            "schedules": statuses(Schedule),
            "occurrences": count(ScheduleOccurrence),
            "usage": {
                "calls": calls,
                "input_tokens": inputs,
                "output_tokens": outputs,
                "cost_usd": None,
            },
        }
        query = select(Run, ScheduleOccurrence).outerjoin(
            ScheduleOccurrence,
            ScheduleOccurrence.run_id == Run.id,
        )
        if before_created_at is not None:
            query = query.where(
                or_(
                    Run.created_at < before_created_at,
                    and_(Run.created_at == before_created_at, Run.id < before_id),
                )
            )
        rows = db.execute(
            query.order_by(Run.created_at.desc(), Run.id.desc()).limit(limit + 1)
        ).all()
        items = [
            {
                "id": run.id,
                "project_id": run.project_id,
                "status": run.status,
                "mode": run.mode,
                "calls": run.calls,
                "input_tokens": run.input_tokens,
                "output_tokens": run.output_tokens,
                "created_at": run.created_at,
                "schedule_id": occurrence.schedule_id if occurrence else None,
                "occurrence": occurrence.number if occurrence else None,
            }
            for run, occurrence in rows[:limit]
        ]
        cursor = None
        if len(rows) > limit:
            cursor = {"before_created_at": items[-1]["created_at"], "before_id": items[-1]["id"]}
        return {
            "generated_at": int(time.time()),
            "summary": summary,
            "runs": items,
            "next_cursor": cursor,
            "note": "Totais de todo o banco; execuções nesta página. Sem estimativa monetária.",
        }
