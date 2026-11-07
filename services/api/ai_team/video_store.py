"""Transactional approval, idempotency and bounded admission for local video jobs."""

import hashlib
import json
import time
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from .memory_safety import validate_text
from .models import Event, Project
from .video_models import VideoJob

ACTIVE = ("pending_approval", "queued", "rendering")


def digest_payload(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def view(job):
    return {
        "id": job.id,
        "project_id": job.project_id,
        "request_id": job.request_id,
        **job.payload,
        "digest": job.digest,
        "status": job.status,
        "error": job.error,
        "created_at": job.created_at,
    }


class VideoStore:
    def __init__(self, database):
        self.database = database

    def create(self, data, actor="owner"):
        payload = data.model_dump(mode="json")
        try:
            validate_text(json.dumps(payload, ensure_ascii=False), maximum=10000)
        except ValueError:
            raise HTTPException(422, "Roteiro inválido ou contém credenciais") from None
        project_id, request_id = payload.pop("project_id"), payload.pop("request_id")
        fingerprint = digest_payload({"project_id": project_id, **payload})
        with self.database.session() as db:
            # Serialize project admission on both PostgreSQL and SQLite without a long transaction.
            exists = db.execute(
                update(Project).where(Project.id == project_id).values(name=Project.name)
            ).rowcount
            if not exists:
                raise HTTPException(404, "Projeto não encontrado")
            old = db.scalar(
                select(VideoJob).where(
                    VideoJob.project_id == project_id, VideoJob.request_id == request_id
                )
            )
            if old:
                if old.digest != fingerprint:
                    raise HTTPException(409, "Identificador já usado com outro roteiro")
                return view(old)
            count = db.scalar(
                select(func.count())
                .select_from(VideoJob)
                .where(VideoJob.project_id == project_id, VideoJob.status.in_(ACTIVE))
            )
            if count >= 2:
                raise HTTPException(409, "Limite de dois vídeos ativos por projeto")
            job = VideoJob(
                project_id=project_id, request_id=request_id, payload=payload, digest=fingerprint
            )
            db.add(job)
            try:
                db.flush()
                db.add(
                    Event(
                        kind="video.requested",
                        resource_id=job.id,
                        actor=actor,
                        summary="Roteiro preparado para revisão: " + fingerprint,
                    )
                )
                db.commit()
            except IntegrityError:
                db.rollback()
                raise HTTPException(409, "Solicitação concorrente; atualize a lista") from None
            return view(job)

    def snapshot(self, project_id):
        with self.database.session() as db:
            return {
                "items": [
                    view(job)
                    for job in db.scalars(
                        select(VideoJob)
                        .where(VideoJob.project_id == project_id)
                        .order_by(VideoJob.created_at.desc())
                        .limit(100)
                    )
                ]
            }

    def get(self, job_id):
        with self.database.session() as db:
            job = db.get(VideoJob, job_id)
            if not job:
                raise HTTPException(404, "Vídeo não encontrado")
            return view(job)

    def decide(self, job_id, digest, approve, actor="owner"):
        with self.database.session() as db:
            status = "queued" if approve else "cancelled"
            result = db.execute(
                update(VideoJob)
                .where(
                    VideoJob.id == job_id,
                    VideoJob.status == "pending_approval",
                    VideoJob.digest == digest,
                )
                .values(status=status, approved_digest=digest if approve else "")
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Aprovação desatualizada; revise o roteiro")
            db.add(
                Event(
                    kind="video.approved" if approve else "video.rejected",
                    resource_id=job_id,
                    actor=actor,
                    summary="Decisão vinculada ao roteiro: " + digest,
                )
            )
            db.commit()
        return self.get(job_id)

    def cancel(self, job_id, actor="owner"):
        self.get(job_id)
        with self.database.session() as db:
            changed = db.execute(
                update(VideoJob)
                .where(VideoJob.id == job_id, VideoJob.status.in_(ACTIVE))
                .values(status="cancelled", lease_token="")
            )
            if changed.rowcount:
                db.add(
                    Event(
                        kind="video.cancelled",
                        resource_id=job_id,
                        actor=actor,
                        summary="Cancelamento revogou a execução local",
                    )
                )
            db.commit()
        return self.get(job_id)

    def claim(self):
        now = int(time.time())
        with self.database.session() as db:
            # A crashed render is never silently replayed; its output is untrusted.
            db.execute(
                update(VideoJob)
                .where(VideoJob.status == "rendering", VideoJob.lease_expires_at < now)
                .values(status="failed", error="Worker interrompido")
            )
            candidates = list(
                db.scalars(
                    select(VideoJob)
                    .where(VideoJob.status == "queued")
                    .order_by(VideoJob.created_at)
                    .limit(10)
                )
            )
            for job in candidates:
                fingerprint = digest_payload({"project_id": job.project_id, **job.payload})
                if fingerprint != job.digest or job.approved_digest != job.digest:
                    db.execute(
                        update(VideoJob)
                        .where(VideoJob.id == job.id, VideoJob.status == "queued")
                        .values(status="blocked", error="Roteiro sem aprovação válida")
                    )
                    continue
                token = str(uuid.uuid4())
                result = db.execute(
                    update(VideoJob)
                    .where(VideoJob.id == job.id, VideoJob.status == "queued")
                    .values(status="rendering", lease_token=token, lease_expires_at=now + 240)
                )
                if result.rowcount:
                    db.add(
                        Event(
                            kind="video.rendering",
                            resource_id=job.id,
                            actor="video-worker",
                            summary="Renderização local iniciada com aprovação válida",
                        )
                    )
                    db.commit()
                    return {**self.get(job.id), "lease_token": token}
            db.commit()
        return None

    def active(self, job_id, token):
        with self.database.session() as db:
            return bool(
                db.scalar(
                    select(VideoJob.id).where(
                        VideoJob.id == job_id,
                        VideoJob.status == "rendering",
                        VideoJob.lease_token == token,
                        VideoJob.lease_expires_at >= int(time.time()),
                    )
                )
            )

    def finish(self, job_id, token, status, error=""):
        with self.database.session() as db:
            result = db.execute(
                update(VideoJob)
                .where(
                    VideoJob.id == job_id,
                    VideoJob.status == "rendering",
                    VideoJob.lease_token == token,
                    VideoJob.lease_expires_at >= int(time.time()),
                )
                .values(status=status, error=error, lease_token="", lease_expires_at=0)
            )
            if result.rowcount:
                db.add(
                    Event(
                        kind="video.finished",
                        resource_id=job_id,
                        actor="video-worker",
                        summary="Renderização local: " + status,
                    )
                )
            db.commit()
            return result.rowcount == 1
