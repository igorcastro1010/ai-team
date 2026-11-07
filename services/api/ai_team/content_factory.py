"""Local rule-based content pipeline. No model calls, shell or remote media."""

import json
import re
import time
from typing import Literal, TypedDict
from uuid import UUID, uuid4, uuid5

from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select, update

from .content_factory_models import ContentProduction
from .memory_safety import validate_text
from .models import Event, Project
from .video_media import MediaStore
from .video_routes import VideoInput
from .video_schema import StudioDocument
from .video_store import VideoStore, digest_payload

STAGES = ["CEO", "PESQUISADOR", "DESIGNER", "DEV", "QA", "CEO"]
ACTIVE = ("queued", "running", "waiting_media", "awaiting_approval", "waiting_render")


class ProductionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    request_id: UUID
    prompt: str = Field(min_length=8, max_length=2000)
    format: Literal["vertical", "square", "horizontal"] = "vertical"
    duration: int = Field(default=15, ge=4, le=60, strict=True)
    style: Literal["professional", "tutorial", "promotion", "institutional"] = "professional"
    media_ids: list[UUID] = Field(default_factory=list, max_length=10)
    audio_id: UUID | None = None


def view(row):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "project_id",
            "request_id",
            "request",
            "document",
            "steps",
            "status",
            "stage",
            "revision",
            "digest",
            "video_id",
            "error",
            "created_at",
        )
    }


class FactoryStore:
    def __init__(self, database):
        self.database = database

    def assets(self, project, request):
        library = {a["id"]: a for a in MediaStore(self.database).snapshot(project)["items"]}
        if any(
            str(asset) not in library or library[str(asset)]["kind"] == "audio"
            for asset in request["media_ids"]
        ):
            raise HTTPException(422, "Selecione mídias visuais deste projeto")
        if request.get("audio_id") and (
            str(request["audio_id"]) not in library
            or library[str(request["audio_id"])]["kind"] != "audio"
        ):
            raise HTTPException(422, "Selecione áudio deste projeto")
        return library

    def fingerprint(self, project, document, revision):
        return digest_payload(
            {
                "project_id": project,
                "revision": revision,
                "document": document,
                "media": MediaStore(self.database).manifest(project, document),
            }
        )

    def create(self, data):
        payload = data.model_dump(mode="json")
        try:
            validate_text(json.dumps(payload, ensure_ascii=False), maximum=8000)
        except ValueError:
            raise HTTPException(422, "Pedido inválido ou contém credenciais") from None
        project, request_id = payload.pop("project_id"), payload.pop("request_id")
        self.assets(project, payload)
        with self.database.session() as db:
            if not db.execute(
                update(Project).where(Project.id == project).values(name=Project.name)
            ).rowcount:
                raise HTTPException(404, "Projeto não encontrado")
            old = db.scalar(
                select(ContentProduction).where(
                    ContentProduction.project_id == project,
                    ContentProduction.request_id == request_id,
                )
            )
            if old:
                if old.request != payload:
                    raise HTTPException(409, "Identificador utilizado para outro pedido")
                return view(old)
            count = db.scalar(
                select(func.count())
                .select_from(ContentProduction)
                .where(
                    ContentProduction.project_id == project, ContentProduction.status.in_(ACTIVE)
                )
            )
            if count >= 2:
                raise HTTPException(409, "Limite de duas produções ativas por projeto")
            row = ContentProduction(project_id=project, request_id=request_id, request=payload)
            db.add(row)
            db.flush()
            db.add(
                Event(
                    kind="content.requested",
                    resource_id=row.id,
                    actor="owner",
                    summary="Produção determinística local solicitada, sem inferência",
                )
            )
            db.commit()
            return view(row)

    def get(self, project, production):
        with self.database.session() as db:
            row = db.get(ContentProduction, production)
            if not row or row.project_id != project:
                raise HTTPException(404, "Produção não encontrada")
            return view(row)

    def snapshot(self, project):
        MediaStore(self.database).require_project(project)
        with self.database.session() as db:
            return {
                "items": [
                    view(row)
                    for row in db.scalars(
                        select(ContentProduction)
                        .where(ContentProduction.project_id == project)
                        .order_by(ContentProduction.created_at.desc())
                        .limit(100)
                    )
                ]
            }

    def edit(self, project, production, revision, document):
        from .video_studio_routes import clean_document

        document = clean_document(document)
        fingerprint = self.fingerprint(project, document, revision + 1)
        self.get(project, production)
        with self.database.session() as db:
            result = db.execute(
                update(ContentProduction)
                .where(
                    ContentProduction.id == production,
                    ContentProduction.revision == revision,
                    ContentProduction.status == "awaiting_approval",
                )
                .values(
                    document=document, revision=revision + 1, digest=fingerprint, approved_digest=""
                )
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Roteiro desatualizado ou já em execução")
            db.add(
                Event(
                    kind="content.edited",
                    resource_id=production,
                    actor="owner",
                    summary="Novo roteiro exige nova aprovação: " + fingerprint,
                )
            )
            db.commit()
        return self.get(project, production)

    def approve(self, project, production, digest):
        row = self.get(project, production)
        if not row["document"] or digest != self.fingerprint(
            project, row["document"], row["revision"]
        ):
            raise HTTPException(409, "Digest desatualizado")
        with self.database.session() as db:
            changed = db.execute(
                update(ContentProduction)
                .where(
                    ContentProduction.id == production,
                    ContentProduction.digest == digest,
                    ContentProduction.status == "awaiting_approval",
                )
                .values(approved_digest=digest, status="queued", stage=3)
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "Aprovação desatualizada ou já utilizada")
            db.add(
                Event(
                    kind="content.approved",
                    resource_id=production,
                    actor="owner",
                    summary="Renderização autorizada para o digest: " + digest,
                )
            )
            db.commit()
        return self.get(project, production)

    def cancel(self, project, production):
        self.get(project, production)
        with self.database.session() as db:
            db.execute(
                update(ContentProduction)
                .where(ContentProduction.id == production, ContentProduction.status.in_(ACTIVE))
                .values(status="cancelled", lease_token="")
            )
            db.add(
                Event(
                    kind="content.cancelled",
                    resource_id=production,
                    actor="owner",
                    summary="Cancelamento solicitado pelo proprietário",
                )
            )
            db.commit()
        row = self.get(project, production)
        if row["status"] == "cancelled" and row["video_id"]:
            VideoStore(self.database).cancel(row["video_id"])
        return row

    def resume(self, project, production, media_ids):
        row = self.get(project, production)
        payload = {**row["request"], "media_ids": [str(i) for i in media_ids]}
        self.assets(project, payload)
        with self.database.session() as db:
            changed = db.execute(
                update(ContentProduction)
                .where(
                    ContentProduction.id == production, ContentProduction.status == "waiting_media"
                )
                .values(request=payload, stage=2, status="queued", error="")
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "Retomada disponível somente para mídia pendente")
            db.commit()
        return self.get(project, production)


def montage(request):
    """Four editable scenes; never claims generated or photographed product media."""
    prompt = request["prompt"]
    brand = re.search(r"\blogo\s+(?:do\s+|da\s+)?([\w-]+)", prompt, re.IGNORECASE)
    title = (brand.group(1) if brand else prompt[:90]).strip()
    red = "vermelh" in prompt.lower()
    colors = ["#000000", "#b51d2b" if red else "#243e52", "#000000", "#ffffff"]
    texts = [title, "Identidade em destaque", "Veja os detalhes", "Conheça nosso projeto"]
    if request["style"] == "tutorial":
        texts = [title, "Passo 1 · Prepare", "Passo 2 · Confira", "Revise o resultado"]
    q, remainder = divmod(request["duration"], 4)
    assets = request["media_ids"]
    document = StudioDocument(
        title=title,
        format=request["format"],
        scenes=[
            {
                "text": text,
                "duration": q + (index < remainder),
                "media_id": assets[index % len(assets)],
                "background": colors[index],
                "color": "#000000" if index == 3 else "#ffffff",
                "y": 78,
                "animation": "zoom",
                "transition": "fade",
                "text_animation": "fade",
            }
            for index, text in enumerate(texts)
        ],
        audio=(
            {"media_id": request["audio_id"], "volume": 0.35} if request.get("audio_id") else None
        ),
    )
    return document.model_dump(mode="json")


class GraphState(TypedDict):
    job: dict
    result: dict


class FactoryWorker:
    def __init__(self, store, output=None):
        from .video_render import artifact_root

        self.store, self.output = store, output or artifact_root()
        graph = StateGraph(GraphState)
        for index in range(6):
            graph.add_node(
                str(index), lambda state, i=index: {"result": self.execute(i, state["job"])}
            )
            graph.add_edge(str(index), END)
        graph.add_conditional_edges(
            START, lambda state: str(state["job"]["stage"]), {str(i): str(i) for i in range(6)}
        )
        self.graph = graph.compile()

    def once(self):
        now, token = int(time.time()), str(uuid4())
        with self.store.database.session() as db:
            db.execute(
                update(ContentProduction)
                .where(
                    ContentProduction.status == "running", ContentProduction.lease_expires_at < now
                )
                .values(status="queued", lease_token="")
            )
            candidates = list(
                db.scalars(
                    select(ContentProduction)
                    .where(ContentProduction.status.in_(("queued", "waiting_render")))
                    .order_by(ContentProduction.created_at)
                    .limit(20)
                )
            )
            claimed = None
            for row in candidates:
                if row.status == "waiting_render":
                    video = VideoStore(self.store.database).get(row.video_id)
                    if video["status"] not in ("completed", "failed", "cancelled", "blocked"):
                        continue
                changed = db.execute(
                    update(ContentProduction)
                    .where(ContentProduction.id == row.id, ContentProduction.status == row.status)
                    .values(status="running", lease_token=token, lease_expires_at=now + 90)
                )
                if changed.rowcount:
                    claimed = {
                        **view(row),
                        "lease_token": token,
                        "approved_digest": row.approved_digest,
                    }
                    break
            db.commit()
        if not claimed:
            return False
        try:
            result = self.graph.invoke({"job": claimed})["result"]
            state = result.pop("status", "queued")
            summary = result.pop("summary")
            step = {
                "agent": STAGES[claimed["stage"]],
                "stage": claimed["stage"],
                "created_at": time.time(),
                "summary": summary,
                "inference": False,
            }
            with self.store.database.session() as db:
                changed = db.execute(
                    update(ContentProduction)
                    .where(
                        ContentProduction.id == claimed["id"],
                        ContentProduction.status == "running",
                        ContentProduction.lease_token == token,
                    )
                    .values(
                        **result,
                        status=state,
                        stage=min(claimed["stage"] + 1, 5),
                        lease_token="",
                        steps=[*claimed["steps"], step][-30:],
                    )
                )
                if changed.rowcount:
                    db.add(
                        Event(
                            kind="content.checkpoint",
                            resource_id=claimed["id"],
                            actor=step["agent"],
                            summary=summary,
                        )
                    )
                db.commit()
        except Exception:
            with self.store.database.session() as db:
                db.execute(
                    update(ContentProduction)
                    .where(
                        ContentProduction.id == claimed["id"],
                        ContentProduction.lease_token == token,
                        ContentProduction.status == "running",
                    )
                    .values(
                        status="failed", lease_token="", error="Falha local; revise etapas e mídias"
                    )
                )
                db.commit()
        return True

    def execute(self, stage, job):
        if stage == 0:
            return {"summary": "CEO: requisitos registrados; processamento determinístico, sem IA"}
        if stage == 1:
            return {"summary": "PESQUISADOR: estrutura local de quatro cenas e duração definida"}
        if stage == 2:
            if not job["request"]["media_ids"]:
                return {
                    "status": "waiting_media",
                    "summary": "DESIGNER: forneça logo, foto ou vídeo próprio",
                }
            self.store.assets(job["project_id"], job["request"])
            document = montage(job["request"])
            return {
                "document": document,
                "digest": self.store.fingerprint(job["project_id"], document, job["revision"]),
                "status": "awaiting_approval",
                "summary": "DESIGNER: montagem pronta para revisão; somente mídias fornecidas",
            }
        if stage == 3:
            if job["approved_digest"] != self.store.fingerprint(
                job["project_id"], job["document"], job["revision"]
            ):
                raise ValueError("Aprovação inválida")
            videos = VideoStore(self.store.database)
            video = videos.create(
                VideoInput(
                    project_id=job["project_id"],
                    request_id=uuid5(UUID(job["id"]), f"render:{job['revision']}"),
                    consent=True,
                    **job["document"],
                )
            )
            with self.store.database.session() as db:
                linked = db.execute(
                    update(ContentProduction)
                    .where(
                        ContentProduction.id == job["id"],
                        ContentProduction.status == "running",
                        ContentProduction.lease_token == job["lease_token"],
                    )
                    .values(video_id=video["id"])
                )
                db.commit()
            if not linked.rowcount:
                videos.cancel(video["id"])
                raise InterruptedError
            if video["status"] == "pending_approval":
                videos.decide(video["id"], video["digest"], True, "content-worker")
            return {
                "video_id": video["id"],
                "status": "waiting_render",
                "summary": "DEV: montagem aprovada enviada à fila FFmpeg existente",
            }
        if stage == 4:
            from .content_factory_qa import inspect_mp4

            video = VideoStore(self.store.database).get(job["video_id"])
            if video["status"] != "completed":
                raise ValueError("Renderização não concluída")
            result = inspect_mp4(self.output / f"{job['video_id']}.mp4", job["document"])
            return {"summary": "QA: MP4 H.264 validado · " + result}
        return {
            "status": "completed",
            "summary": "CEO: MP4 validado disponível para download autenticado",
        }
