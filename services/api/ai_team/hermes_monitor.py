"""Read-only reconciliation process. Never admits, resumes or stops remote work."""

import argparse
import time
from dataclasses import dataclass

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .config import Settings
from .db import Database
from .hermes import HermesClient
from .hermes_journal import REMOTE_ID, TERMINAL, HermesJournal
from .models import Event, HermesAttempt, HermesPoll, ProviderObservation, Run, new_id

INTERVAL = 30
MAX_BACKOFF = 900
LEASE_SECONDS = 90


@dataclass(frozen=True)
class PollLease:
    attempt_id: str
    remote_id: str
    token: str
    failures: int
    previous_result: str


def orphan_conditions(now):
    return (
        HermesAttempt.remote_id != "",
        HermesAttempt.remote_status.not_in(TERMINAL),
        or_(Run.status != "running", Run.stage != HermesAttempt.stage, Run.lease_expires_at <= now),
    )


class ReconciliationStore:
    def __init__(self, database):
        self.database = database

    def heartbeat(self, status, now):
        with self.database.session() as db:
            db.merge(
                ProviderObservation(
                    id="hermes-monitor",
                    details={
                        "status": status,
                        "checked_at": now,
                    },
                )
            )
            db.commit()

    def claim(self, *, now):
        with self.database.session() as db:
            candidate = db.execute(
                select(HermesAttempt, HermesPoll)
                .join(Run, Run.id == HermesAttempt.run_id)
                .outerjoin(HermesPoll, HermesPoll.attempt_id == HermesAttempt.id)
                .where(
                    *orphan_conditions(now),
                    or_(
                        HermesPoll.attempt_id.is_(None),
                        and_(
                            HermesPoll.next_poll_at <= now,
                            HermesPoll.lease_expires_at <= now,
                        ),
                    ),
                )
                .order_by(
                    func.coalesce(HermesPoll.next_poll_at, 0),
                    HermesAttempt.created_at,
                    HermesAttempt.id,
                )
                .limit(1)
            ).first()
            if candidate is None:
                return None
            attempt, previous = candidate
            token = new_id()
            if previous is None:
                db.add(
                    HermesPoll(
                        attempt_id=attempt.id,
                        lease_token=token,
                        lease_expires_at=now + LEASE_SECONDS,
                    )
                )
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    return None
            else:
                changed = db.execute(
                    update(HermesPoll)
                    .where(
                        HermesPoll.attempt_id == attempt.id,
                        HermesPoll.next_poll_at <= now,
                        HermesPoll.lease_expires_at <= now,
                    )
                    .values(lease_token=token, lease_expires_at=now + LEASE_SECONDS)
                )
                if changed.rowcount != 1:
                    db.rollback()
                    return None
            lease = PollLease(
                attempt.id,
                attempt.remote_id,
                token,
                previous.failures if previous else 0,
                previous.last_result if previous else "pending",
            )
            db.commit()
            return lease

    def finish(self, lease, *, now, success):
        failures = 0 if success else min(lease.failures + 1, 30)
        delay = INTERVAL if success else min(INTERVAL * 2 ** min(failures, 5), MAX_BACKOFF)
        result = "observed" if success else "unavailable"
        with self.database.session() as db:
            changed = db.execute(
                update(HermesPoll)
                .where(
                    HermesPoll.attempt_id == lease.attempt_id,
                    HermesPoll.lease_token == lease.token,
                )
                .values(
                    last_polled_at=now,
                    failures=failures,
                    last_result=result,
                    next_poll_at=now + delay,
                    lease_token="",
                    lease_expires_at=0,
                )
            )
            if changed.rowcount and result != lease.previous_result:
                db.add(
                    Event(
                        kind="hermes.reconciled",
                        resource_id=lease.attempt_id,
                        actor="hermes-monitor",
                        summary="Consulta remota: "
                        + ("estado observado" if success else "indisponível; backoff aplicado"),
                    )
                )
            db.commit()

    def state(self, attempt_id):
        with self.database.session() as db:
            row = db.get(HermesPoll, attempt_id)
            return (
                {
                    field: getattr(row, field)
                    for field in (
                        "next_poll_at",
                        "last_polled_at",
                        "failures",
                        "last_result",
                    )
                }
                if row
                else None
            )

    def snapshot(self, *, now=None):
        now = int(time.time()) if now is None else now
        with self.database.session() as db:
            row = db.get(ProviderObservation, "hermes-monitor")
            details = row.details if row else {}
            stamp = details.get("checked_at")
            connection = {
                "status": details.get("status", "not_started"),
                "checked_at": stamp,
                "recent": type(stamp) is int and 0 <= now - stamp <= 45,
            }
            query = (
                select(func.count())
                .select_from(HermesAttempt)
                .join(Run, Run.id == HermesAttempt.run_id)
                .where(*orphan_conditions(now))
            )
            pending = db.scalar(query)
            failed = db.scalar(
                query.join(HermesPoll, HermesPoll.attempt_id == HermesAttempt.id).where(
                    HermesPoll.failures > 0
                )
            )
            return {"connection": connection, "pending": pending, "failed": failed}


class HermesMonitor:
    def __init__(self, database, settings, client):
        self.store = ReconciliationStore(database)
        self.journal = HermesJournal(database)
        self.client = client

    def once(self, *, now=None):
        now = int(time.time()) if now is None else now
        if not self.client.configured:
            self.store.heartbeat("not_configured", now)
            return False
        self.store.heartbeat("running", now)
        lease = self.store.claim(now=now)
        if lease is None:
            return False
        try:
            if not REMOTE_ID.fullmatch(lease.remote_id):
                raise ValueError("Invalid stored reference")
            response = self.client.request("GET", f"/v1/runs/{lease.remote_id}")
            self.journal.observe(lease.attempt_id, response)
        except Exception:
            self.store.finish(lease, now=now, success=False)
        else:
            self.store.finish(lease, now=now, success=True)
        return True


def main():
    parser = argparse.ArgumentParser(description="Monitor Hermes somente leitura")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    database = Database(settings)
    if settings.environment != "production":
        database.initialize()
    monitor = HermesMonitor(database, settings, HermesClient(settings))
    print(
        "Monitor Hermes: consultas de estado; nenhuma inferência ou interrupção automática.",
        flush=True,
    )
    while True:
        try:
            monitor.once()
        except KeyboardInterrupt:
            break
        except Exception:
            # Configuration/provider/DB errors may contain secrets; never print them.
            print(
                "Monitor temporariamente indisponível; confira a configuração privada.", flush=True
            )
        if args.once:
            break
        time.sleep(5)


if __name__ == "__main__":
    main()
