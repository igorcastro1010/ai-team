"""Recorrências autorizadas: transação local, sem inferência ou ferramentas externas."""

import time
from typing import Annotated, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select, update

from .models import Event, Project, Run, Schedule, ScheduleOccurrence, new_id

ACTIVE_RUNS = ("queued", "running", "awaiting_approval", "blocked")


class ScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1, max_length=36)
    prompt: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=5000)]
    mode: Literal["manual", "supervised", "automatic"]
    interval_seconds: int = Field(ge=3600, le=7 * 86400, strict=True)
    starts_at: int = Field(strict=True)
    max_runs: int = Field(ge=1, le=5, strict=True)
    consent: Literal[True]


class ScheduleStore:
    def __init__(self, database):
        self.database = database

    def all(self):
        with self.database.session() as db:
            return list(
                db.scalars(select(Schedule).order_by(Schedule.created_at.desc(), Schedule.id))
            )

    def get(self, schedule_id):
        with self.database.session() as db:
            row = db.get(Schedule, schedule_id)
            if row is None:
                raise HTTPException(404, "Agendamento não encontrado")
            return row

    def create(self, payload, actor, *, now=None):
        now = int(time.time()) if now is None else now
        data = ScheduleInput.model_validate(payload)
        if not now < data.starts_at <= now + 7 * 86400:
            raise HTTPException(422, "Escolha um início futuro nos próximos sete dias")
        with self.database.session() as db:
            if db.get(Project, data.project_id) is None:
                raise HTTPException(404, "Projeto não encontrado")
            row = Schedule(
                project_id=data.project_id,
                prompt=data.prompt,
                mode=data.mode,
                interval_seconds=data.interval_seconds,
                next_run_at=data.starts_at,
                max_runs=data.max_runs,
                created_at=now,
                expires_at=now + 30 * 86400,
            )
            db.add(row)
            db.flush()
            db.add(
                Event(
                    kind="schedule.authorized",
                    resource_id=row.id,
                    actor=actor,
                    summary=f"Recorrência textual: {data.max_runs} ocorrências, modo {data.mode}",
                )
            )
            db.commit()
            return row

    def cancel(self, schedule_id, actor):
        self.get(schedule_id)
        with self.database.session() as db:
            changed = db.execute(
                update(Schedule)
                .where(
                    Schedule.id == schedule_id,
                    Schedule.status == "active",
                )
                .values(status="cancelled")
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "Agendamento já encerrado")
            db.add(
                Event(
                    kind="schedule.cancelled",
                    resource_id=schedule_id,
                    actor=actor,
                    summary="Recorrência cancelada; execuções já criadas preservadas",
                )
            )
            db.commit()
        return self.get(schedule_id)

    def tick(self, *, now=None):
        now = int(time.time()) if now is None else now
        with self.database.session() as db:
            expired = list(
                db.scalars(
                    select(Schedule.id).where(
                        Schedule.status == "active",
                        Schedule.expires_at <= now,
                    )
                )
            )
            for schedule_id in expired:
                changed = db.execute(
                    update(Schedule)
                    .where(
                        Schedule.id == schedule_id,
                        Schedule.status == "active",
                        Schedule.expires_at <= now,
                    )
                    .values(status="expired")
                )
                if changed.rowcount:
                    db.add(
                        Event(
                            kind="schedule.expired",
                            resource_id=schedule_id,
                            actor="scheduler",
                            summary="Autorização de recorrência expirou",
                        )
                    )
            db.commit()
            due = list(
                db.scalars(
                    select(Schedule)
                    .where(
                        Schedule.status == "active",
                        Schedule.next_run_at <= now,
                    )
                    .order_by(Schedule.next_run_at, Schedule.id)
                    .limit(20)
                )
            )
        emitted = 0
        for row in due:
            with self.database.session() as db:
                # CAS takes the row write lock before checking active occurrences.
                changed = db.execute(
                    update(Schedule)
                    .where(
                        Schedule.id == row.id,
                        Schedule.status == "active",
                        Schedule.emitted == row.emitted,
                        Schedule.next_run_at == row.next_run_at,
                        Schedule.expires_at > now,
                        Schedule.emitted < Schedule.max_runs,
                    )
                    .values(
                        next_run_at=now + row.interval_seconds,
                        emitted=row.emitted + 1,
                        status="completed" if row.emitted + 1 == row.max_runs else "active",
                    )
                )
                if changed.rowcount != 1:
                    continue
                busy = db.scalar(
                    select(Run.id)
                    .join(
                        ScheduleOccurrence,
                        ScheduleOccurrence.run_id == Run.id,
                    )
                    .where(ScheduleOccurrence.schedule_id == row.id, Run.status.in_(ACTIVE_RUNS))
                    .limit(1)
                )
                if busy:
                    db.rollback()
                    continue
                run = Run(
                    id=new_id(),
                    project_id=row.project_id,
                    prompt=row.prompt,
                    mode=row.mode,
                    scope="draft_only",
                    created_at=now,
                )
                db.add(run)
                db.flush()
                db.add(
                    ScheduleOccurrence(
                        schedule_id=row.id, number=row.emitted + 1, run_id=run.id, created_at=now
                    )
                )
                db.add(
                    Event(
                        kind="schedule.enqueued",
                        resource_id=run.id,
                        actor="scheduler",
                        summary=f"Ocorrência {row.emitted + 1}/{row.max_runs}: somente texto",
                    )
                )
                db.commit()
                emitted += 1
        return emitted
