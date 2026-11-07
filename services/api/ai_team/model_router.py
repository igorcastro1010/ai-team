"""Bounded central provider; no paid fallbacks and no Desktop credential access."""

import json
import time

from sqlalchemy import select, update

from .gemini import GeminiBlocked, GeminiClient, GeminiRateLimited
from .memory_safety import validate_text
from .model_center import GEMINI_MODEL, CentralDeferred, ModelCenter
from .model_center_models import ModelProbe, ModelProviderState
from .orchestration import BOUNDARIES, STAGES, DraftContent
from .workflow import WorkflowStore


def reservation_estimate(role, instructions, context):
    text = json.dumps(
        {"role": role, "untrusted_context": json.dumps(context, ensure_ascii=False)},
        ensure_ascii=False,
    )
    body = {
        "system": instructions + BOUNDARIES,
        "text": text,
        "schema": DraftContent.model_json_schema(),
    }
    return len(json.dumps(body, ensure_ascii=False).encode()) + 8192


def observe(database, observation):
    with database.session() as db:
        row = db.get(ModelProviderState, "gemini")
        row.observation = observation
        db.commit()


def check_pending(database, factory=GeminiClient):
    ModelCenter(database)
    with database.session() as db:
        db.execute(
            update(ModelProbe)
            .where(ModelProbe.status == "running", ModelProbe.expires_at < time.time())
            .values(status="failed")
        )
        probe = db.scalar(select(ModelProbe).where(ModelProbe.status == "queued").limit(1))
        if probe is None:
            db.commit()
            return False
        claim = db.execute(
            update(ModelProbe)
            .where(ModelProbe.id == probe.id, ModelProbe.status == "queued")
            .values(status="running", expires_at=int(time.time()) + 120)
        )
        db.commit()
        if claim.rowcount != 1:
            return False
        probe_id = probe.id
    provider = factory()
    try:
        observation = provider.check()
    except GeminiBlocked:
        observation = {
            "status": "blocked",
            "reason": "Configuração, elegibilidade ou conexão não verificadas",
        }
    except Exception:
        observation = {
            "status": "unavailable",
            "reason": "Verificação indisponível; sem inferência",
        }
    finally:
        provider.close()
    observe(database, observation)
    with database.session() as db:
        db.execute(
            update(ModelProbe)
            .where(ModelProbe.id == probe_id, ModelProbe.status == "running")
            .values(status="completed")
        )
        db.commit()
    return True


class CentralProvider:
    def __init__(self, database, run=None, factory=GeminiClient):
        self.database, self.run, self.factory = database, run, factory
        self.center = ModelCenter(database)

    def for_run(self, database, run):
        return CentralProvider(database, run, self.factory)

    def ready(self):
        # Readiness is policy-driven in preflight; configured does not mean connected.
        return True

    def preflight(self, role=None):
        role = role or STAGES[self.run.stage]
        self.center.choose(self.run, role)
        provider = self.factory()
        try:
            proof = provider.check()
            observe(self.database, proof)
            return proof
        except GeminiBlocked:
            reason = "Gemini gratuito não verificado; confira a configuração privada"
            self.center.log(self.run, role, "gemini", GEMINI_MODEL, "waiting_model", reason)
            raise CentralDeferred(reason) from None
        finally:
            provider.close()

    def generate(self, role, instructions, context, on_tick):
        proof = self.preflight(role)
        on_tick()
        call_id = self.center.admit(
            self.run,
            role,
            proof["project_key"],
            reservation_estimate(role, instructions, context),
        )
        if not WorkflowStore(self.database).reserve_call(self.run):
            self.center.finish(call_id, "blocked")
            raise CentralDeferred("Limite de execução atingido")
        provider, started = self.factory(), time.monotonic()
        try:

            def tick():
                on_tick()
                # Revocation during metadata checks prevents the eventual POST.
                self.center.choose(self.run, role)

            draft = provider.generate(
                role, instructions, json.dumps(context, ensure_ascii=False), tick, authorized=True
            )
            validate_text(draft.summary + "\n" + draft.deliverable, maximum=64000)
            self.center.finish(
                call_id,
                "succeeded",
                draft=draft,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            return draft
        except GeminiRateLimited as error:
            self.center.finish(call_id, "limited", retry_after=error.retry_after)
            raise CentralDeferred(
                "Cota Gemini esgotada; respeite Retry-After", "waiting_quota", not_dispatched=False
            ) from None
        except BaseException:
            self.center.finish(call_id, "uncertain")
            raise
        finally:
            provider.close()
