"""Durable local references to native Hermes runs, never a second execution engine."""

import re
import time

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError

from .models import Event, HermesAttempt, Run

REMOTE_ID = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")
TERMINAL = {"completed", "failed", "cancelled", "interrupted"}
REMOTE_STATES = TERMINAL | {"started", "queued", "running", "unknown", "awaiting_approval"}


class HermesJournal:
    def __init__(self, database):
        self.database = database

    def get(self, attempt_id):
        with self.database.session() as db:
            attempt = db.get(HermesAttempt, attempt_id)
            if attempt is None:
                raise HTTPException(404, "Tentativa Hermes não encontrada")
            return attempt

    def begin(self, run, identity):
        if not re.fullmatch(r"ai-team-[A-Za-z0-9_-]{1,80}", identity):
            raise ValueError("Identidade de admissão inválida")
        with self.database.session() as db:
            # Acquire the same row before admission; cancellation/other workers serialize here.
            eligible = db.execute(
                update(Run)
                .where(
                    Run.id == run.id,
                    Run.status == "running",
                    Run.stage == run.stage,
                    Run.lease_token == run.lease_token,
                    Run.scope == "draft_only",
                    Run.lease_expires_at > int(time.time()),
                )
                .values(lease_token=Run.lease_token)
            )
            current = db.get(Run, run.id)
            if eligible.rowcount != 1 or current.executor != "hermes":
                db.rollback()
                raise RuntimeError("Execução ou lease não autoriza admissão Hermes")
            attempt = HermesAttempt(run_id=run.id, stage=run.stage, admission_key=identity)
            db.add(attempt)
            try:
                db.flush()
                db.add(
                    Event(
                        kind="hermes.admitting",
                        resource_id=attempt.id,
                        actor="worker",
                        summary="Admissão Hermes registrada antes do envio",
                    )
                )
                db.commit()
            except IntegrityError:
                db.rollback()
                raise RuntimeError(
                    "Tentativa já registrada; não readmitir automaticamente"
                ) from None
            return attempt

    def admitted(self, attempt_id, remote_id):
        if not isinstance(remote_id, str) or not REMOTE_ID.fullmatch(remote_id):
            raise ValueError("Identificador remoto inválido")
        with self.database.session() as db:
            changed = db.execute(
                update(HermesAttempt)
                .where(
                    HermesAttempt.id == attempt_id,
                    HermesAttempt.remote_id == "",
                )
                .values(
                    remote_id=remote_id,
                    remote_status="started",
                    bridge_status="running",
                    updated_at=int(time.time()),
                )
            )
            if changed.rowcount != 1:
                db.rollback()
                raise RuntimeError("Admissão já vinculada ou tentativa inexistente")
            db.add(
                Event(
                    kind="hermes.admitted",
                    resource_id=attempt_id,
                    actor="worker",
                    summary="Execução nativa Hermes identificada",
                )
            )
            db.commit()

    def observe(self, attempt_id, response):
        status = response.get("status") if isinstance(response, dict) else None
        if status not in REMOTE_STATES:
            raise ValueError("Estado remoto Hermes inválido")
        attempt = self.get(attempt_id)
        if response.get("run_id", attempt.remote_id) != attempt.remote_id:
            raise ValueError("Resposta pertence a outra execução Hermes")
        usage = response.get("usage")
        usage = usage if isinstance(usage, dict) else {}
        values = {"remote_status": status, "updated_at": int(time.time())}
        for field in ("input_tokens", "output_tokens"):
            value = usage.get(field)
            if type(value) is int and 0 <= value <= 2_000_000_000:
                values[field] = value
        with self.database.session() as db:
            changed = db.execute(
                update(HermesAttempt)
                .where(
                    HermesAttempt.id == attempt_id,
                    HermesAttempt.remote_status.not_in(TERMINAL),
                )
                .values(**values)
            )
            if changed.rowcount and attempt.remote_status != status:
                db.add(
                    Event(
                        kind="hermes.observed",
                        resource_id=attempt_id,
                        actor="hermes",
                        summary=f"Estado remoto Hermes observado: {status}",
                    )
                )
            if status in TERMINAL:
                db.execute(
                    update(HermesAttempt)
                    .where(
                        HermesAttempt.id == attempt_id,
                        HermesAttempt.remote_status == status,
                        HermesAttempt.stop_status.in_(["requested", "uncertain"]),
                    )
                    .values(
                        stop_status="confirmed"
                        if status in {"cancelled", "interrupted"}
                        else "already_finished"
                    )
                )
            db.commit()

    def finish(self, attempt_id, status):
        if status not in {"succeeded", "failed", "uncertain", "interrupted", "timed_out"}:
            raise ValueError("Estado do adaptador inválido")
        with self.database.session() as db:
            changed = db.execute(
                update(HermesAttempt)
                .where(
                    HermesAttempt.id == attempt_id,
                    HermesAttempt.bridge_status != "succeeded",
                )
                .values(bridge_status=status, updated_at=int(time.time()))
            )
            if changed.rowcount:
                db.add(
                    Event(
                        kind="hermes.finished",
                        resource_id=attempt_id,
                        actor="worker",
                        summary=f"Adaptador Hermes: {status}",
                    )
                )
            db.commit()

    def mark_stop(self, attempt_id, status):
        if status not in {"requested", "uncertain"}:
            raise ValueError("Estado de interrupção inválido")
        with self.database.session() as db:
            db.execute(
                update(HermesAttempt)
                .where(
                    HermesAttempt.id == attempt_id,
                    HermesAttempt.stop_status.not_in(["confirmed", "already_finished"]),
                )
                .values(stop_status=status, updated_at=int(time.time()))
            )
            db.add(
                Event(
                    kind="hermes.stop",
                    resource_id=attempt_id,
                    actor="owner_or_worker",
                    summary=f"Interrupção Hermes: {status}; conferir estado remoto",
                )
            )
            db.commit()

    @staticmethod
    def view(attempt):
        return {
            key: getattr(attempt, key)
            for key in (
                "id",
                "run_id",
                "stage",
                "remote_id",
                "remote_status",
                "bridge_status",
                "stop_status",
                "input_tokens",
                "output_tokens",
                "created_at",
                "updated_at",
            )
        } | {"local_status": attempt.run.status}

    def page(self, *, before=None):
        with self.database.session() as db:
            query = select(HermesAttempt)
            if before:
                cursor = db.get(HermesAttempt, before)
                if cursor is None:
                    raise HTTPException(404, "Cursor Hermes não encontrado")
                query = query.where(
                    or_(
                        HermesAttempt.created_at < cursor.created_at,
                        and_(
                            HermesAttempt.created_at == cursor.created_at,
                            HermesAttempt.id < cursor.id,
                        ),
                    )
                )
            rows = list(
                db.scalars(
                    query.order_by(
                        HermesAttempt.created_at.desc(),
                        HermesAttempt.id.desc(),
                    ).limit(51)
                )
            )
            return {
                "items": [self.view(row) for row in rows[:50]],
                "next_cursor": rows[49].id if len(rows) > 50 else None,
            }
