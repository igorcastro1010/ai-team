"""Project persisted production steps onto existing office roles, without fake activity."""

import time

from sqlalchemy import select

from .content_factory import STAGES
from .content_factory_models import ContentProduction
from .video_models import VideoJob


def production_office(database, agents):
    now = int(time.time())
    with database.session() as db:
        rows = list(
            db.scalars(
                select(ContentProduction).order_by(ContentProduction.created_at.desc()).limit(100)
            )
        )
        for agent in agents:
            for row in reversed(rows):
                history = [
                    {
                        **step,
                        "run_id": row.id,
                        "executor": "local",
                        "deliverable": step["summary"] + " · Sem inferência de IA",
                    }
                    for step in row.steps
                    if step["agent"] == agent["id"]
                ]
                agent["history"] = [*reversed(history), *agent["history"]][:10]
                if history:
                    agent["enabled"] = True
                    if agent["status"] == "available":
                        agent["status"] = "completed"
            if agent["status"] in {"working", "awaiting_approval"}:
                continue
            ordered = sorted(
                rows,
                key=lambda row: (
                    0
                    if row.status in {"running", "waiting_render"}
                    else 1
                    if row.status in {"awaiting_approval", "waiting_media"}
                    else 2
                    if row.status == "queued"
                    else 3,
                    -row.created_at,
                ),
            )
            for row in ordered:
                owner = (
                    "DESIGNER"
                    if row.status in {"waiting_media", "awaiting_approval"}
                    else ("DEV" if row.status == "waiting_render" else STAGES[min(row.stage, 5)])
                )
                if owner != agent["id"]:
                    continue
                video = db.get(VideoJob, row.video_id) if row.video_id else None
                render_active = bool(
                    row.status == "waiting_render"
                    and video
                    and video.status == "rendering"
                    and video.lease_expires_at > now
                )
                working = (
                    bool(row.status == "running" and row.lease_expires_at > now) or render_active
                )
                agent.update(
                    enabled=True,
                    status=(
                        "working"
                        if working
                        else "awaiting_approval"
                        if row.status in {"waiting_media", "awaiting_approval"}
                        else "completed"
                        if row.status == "completed"
                        else "error"
                        if row.status == "failed"
                        else "available"
                    ),
                    animate=working,
                    activity="Produção local de vídeo · sem inferência",
                    run_id=row.id,
                    executor="local",
                    run_status=row.status,
                    error=row.error,
                    production_id=row.id,
                    project_id=row.project_id,
                )
                break
    return agents
