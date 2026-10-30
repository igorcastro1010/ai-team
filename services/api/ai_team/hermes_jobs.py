"""Bounded native-job inventory and scheduling pause; never submit or resume work."""

import re
import time
from datetime import datetime
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .models import Event, ProviderObservation

JOB_ID = re.compile(r"[a-f0-9]{12}\Z")
MAX_JOBS = 100
STATES = {"scheduled", "paused", "completed", "error"}


class JobView(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(pattern=r"^[a-f0-9]{12}$")
    name: str = Field(max_length=200)
    enabled: bool
    state: Literal["scheduled", "paused", "completed", "error", "unknown"]
    schedule_kind: Literal["once", "interval", "cron", "unknown"]
    next_run_at: int | None = None
    last_run_at: int | None = None
    repeat_times: int | None = None
    repeat_completed: int = 0


class PauseView(BaseModel):
    job_id: str = Field(pattern=r"^[a-f0-9]{12}$")
    status: Literal["confirmed", "uncertain"]
    checked_at: int


class JobsView(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: Literal["not_configured", "unavailable", "reachable"] = "not_configured"
    checked_at: int | None = None
    items: list[JobView] = Field(default_factory=list, max_length=MAX_JOBS)
    truncated: bool = False
    last_pause: PauseView | None = None


def jobs_snapshot(database):
    with database.session() as db:
        row = db.get(ProviderObservation, "hermes-jobs")
        try:
            return JobsView.model_validate(row.details if row else {}).model_dump()
        except ValidationError:
            return JobsView(status="unavailable").model_dump()


def timestamp(value):
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return int(parsed.timestamp()) if parsed.tzinfo is not None else None
    except (ValueError, OverflowError, OSError):
        return None


def bounded_integer(value):
    return value if type(value) is int and 0 <= value <= 2_000_000_000 else None


def job_view(value):
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("id"), str)
        or not JOB_ID.fullmatch(value["id"])
        or type(value.get("enabled")) is not bool
    ):
        raise ValueError("Contrato de job inválido")
    schedule = value.get("schedule")
    schedule = schedule if isinstance(schedule, dict) else {}
    repeat = value.get("repeat")
    repeat = repeat if isinstance(repeat, dict) else {}
    name = value.get("name")
    name = (
        "".join(char for char in name if char.isprintable())[:200] if isinstance(name, str) else ""
    )
    return JobView(
        id=value["id"],
        name=name or "Job Hermes",
        enabled=value["enabled"],
        state=value.get("state") if value.get("state") in STATES else "unknown",
        schedule_kind=schedule.get("kind")
        if schedule.get("kind") in {"once", "interval", "cron"}
        else "unknown",
        next_run_at=timestamp(value.get("next_run_at")),
        last_run_at=timestamp(value.get("last_run_at")),
        repeat_times=bounded_integer(repeat.get("times")),
        repeat_completed=bounded_integer(repeat.get("completed")) or 0,
    ).model_dump()


class HermesJobs:
    def __init__(self, database, client):
        self.database, self.client = database, client

    def _save(self, snapshot, actor, kind, resource_id=""):
        result = JobsView.model_validate(snapshot).model_dump()
        with self.database.session() as db:
            db.merge(ProviderObservation(id="hermes-jobs", details=result))
            db.add(
                Event(
                    kind=kind,
                    actor=actor,
                    resource_id=resource_id,
                    summary="Inventário ou pausa de job Hermes observado",
                )
            )
            db.commit()
        return result

    def inspect(self, actor):
        result = jobs_snapshot(self.database)
        result.update(status="not_configured", checked_at=None)
        if not self.client.configured:
            result.update(items=[], truncated=False)
            return self._save(result, actor, "hermes.jobs.inspected")
        result.update(status="unavailable", checked_at=int(time.time()))
        try:
            payload = self.client.request("GET", "/api/jobs?include_disabled=true")
            rows = payload.get("jobs") if isinstance(payload, dict) else None
            if not isinstance(rows, list):
                raise ValueError("Inventário inválido")
            items = [job_view(row) for row in rows[:MAX_JOBS]]
            if len({row["id"] for row in items}) != len(items):
                raise ValueError("Identidade duplicada")
            result.update(status="reachable", items=items, truncated=len(rows) > MAX_JOBS)
            pause = result.get("last_pause")
            if (
                pause
                and pause["status"] == "uncertain"
                and any(
                    row["id"] == pause["job_id"] and not row["enabled"] and row["state"] == "paused"
                    for row in items
                )
            ):
                result["last_pause"] = {
                    **pause,
                    "status": "confirmed",
                    "checked_at": int(time.time()),
                }
        except (httpx.HTTPError, RuntimeError, TimeoutError, ValueError, TypeError):
            pass  # Keep only a sanitized prior snapshot; never persist upstream errors or payloads.
        return self._save(result, actor, "hermes.jobs.inspected")

    def _read(self, job_id, deadline):
        payload = self.client.request("GET", f"/api/jobs/{job_id}", deadline=deadline)
        value = job_view(payload.get("job") if isinstance(payload, dict) else None)
        if value["id"] != job_id:
            raise ValueError("Resposta pertence a outro job")
        return value

    def _record_pause(self, job_id, status, actor, observed=None):
        snapshot = jobs_snapshot(self.database)
        result = PauseView(job_id=job_id, status=status, checked_at=int(time.time())).model_dump()
        snapshot["last_pause"] = result
        if observed:
            snapshot["items"] = [
                observed if row["id"] == job_id else row for row in snapshot["items"]
            ]
        self._save(snapshot, actor, "hermes.job.pause", resource_id=job_id)
        return result

    def pause(self, job_id, actor):
        if not JOB_ID.fullmatch(job_id):
            raise HTTPException(400, "Identificador de job inválido")
        snapshot = jobs_snapshot(self.database)
        if job_id not in {row["id"] for row in snapshot["items"]}:
            raise HTTPException(409, "Consulte este job antes de confirmar a pausa")
        if not self.client.configured:
            raise HTTPException(503, "Gateway Hermes indisponível")
        deadline = time.monotonic() + 8
        try:
            current = self._read(job_id, deadline)
        except (httpx.HTTPError, RuntimeError, TimeoutError, ValueError, TypeError):
            raise HTTPException(503, "Não foi possível conferir o job no Hermes") from None
        if not current["enabled"] and current["state"] == "paused":
            return self._record_pause(job_id, "confirmed", actor, current)
        if current["state"] not in {"scheduled", "paused"}:
            raise HTTPException(409, "O estado atual deste job não permite pausar o agendamento")
        # Persist uncertainty BEFORE a remote mutation; a lost response is never auto-retried.
        self._record_pause(job_id, "uncertain", actor)
        try:
            self.client.request("POST", f"/api/jobs/{job_id}/pause", deadline=deadline)
            observed = self._read(job_id, deadline)
            if observed["enabled"] or observed["state"] != "paused":
                raise ValueError("Pausa não confirmada")
        except (httpx.HTTPError, RuntimeError, TimeoutError, ValueError, TypeError):
            raise HTTPException(
                502, "Pausa não confirmada; confira o gateway antes de tentar novamente"
            ) from None
        return self._record_pause(job_id, "confirmed", actor, observed)
