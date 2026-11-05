"""Owner-only knowledge management. Vault root is server configuration, never request data."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from .auth import require_owner
from .memory_models import MemoryEntry
from .memory_store import MemoryStore, view
from .memory_vault import Vault, VaultError

router = APIRouter(prefix="/memory/{project_id}")
Owner = Annotated[str, Depends(require_owner)]


class NoteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=180)
    content: str = Field(min_length=1, max_length=64000)
    expected_version: int | None = Field(default=None, ge=1)


class ExportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_digest: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")


def vault_for(request):
    root = request.app.state.settings.memory_vault
    if not root:
        raise HTTPException(
            409, "Configure AI_TEAM_MEMORY_VAULT no servidor para integrar Obsidian"
        )
    try:
        return Vault(root)
    except VaultError as error:
        raise HTTPException(409, str(error)) from None


def sync_vault(database, project_id, vault):
    store = MemoryStore(database)
    store.snapshot(project_id)
    imported, rejected = 0, 0
    for name in vault.files(project_id):
        try:
            content = vault.read(project_id, name)
            source = "obsidian:" + name
            with database.session() as db:
                existing = db.scalar(
                    select(MemoryEntry).where(
                        MemoryEntry.project_id == project_id,
                        MemoryEntry.source == source,
                        MemoryEntry.archived.is_(False),
                    )
                )
                old_id = existing.id if existing else None
                old_version = existing.version if existing else None
                if existing and existing.content == content:
                    continue
                # Exported own notes already exist and must not create duplicates.
                own = db.get(MemoryEntry, name.removesuffix(".md"))
                if own and own.project_id == project_id and content == own.content:
                    continue
            result = store.put(
                project_id,
                name.removesuffix(".md"),
                content,
                source,
                "vault",
                note_id=old_id,
                expected_version=old_version,
            )
            if old_id or result["source"] == source:
                imported += 1
        except (VaultError, HTTPException):
            rejected += 1
    return {"imported": imported, "rejected": rejected, "inference_calls": 0}


@router.get("")
def snapshot(project_id: str, request: Request, owner: Owner):
    result = MemoryStore(request.app.state.database).snapshot(project_id)
    return {**result, "vault_configured": bool(request.app.state.settings.memory_vault)}


@router.get("/search")
def search(project_id: str, request: Request, owner: Owner, q: str = Query(max_length=1000)):
    return {"items": MemoryStore(request.app.state.database).search(project_id, q)}


@router.post("", status_code=201)
def create(project_id: str, data: NoteInput, request: Request, owner: Owner):
    return MemoryStore(request.app.state.database).put(
        project_id, data.title, data.content, "owner", owner
    )


@router.put("/{note_id}")
def revise(project_id: str, note_id: str, data: NoteInput, request: Request, owner: Owner):
    if data.expected_version is None:
        raise HTTPException(422, "Informe a versão revisada")
    return MemoryStore(request.app.state.database).put(
        project_id,
        data.title,
        data.content,
        "owner",
        owner,
        note_id=note_id,
        expected_version=data.expected_version,
    )


@router.get("/{note_id}/history")
def history(project_id: str, note_id: str, request: Request, owner: Owner):
    return {"items": MemoryStore(request.app.state.database).history(project_id, note_id)}


@router.get("/{note_id}")
def get_note(project_id: str, note_id: str, request: Request, owner: Owner):
    with request.app.state.database.session() as db:
        note = db.get(MemoryEntry, note_id)
        if not note or note.project_id != project_id or note.archived:
            raise HTTPException(404, "Memória não encontrada neste projeto")
        return view(note)


@router.post("/sync")
def sync(project_id: str, request: Request, owner: Owner):
    try:
        return sync_vault(request.app.state.database, project_id, vault_for(request))
    except VaultError as error:
        raise HTTPException(409, str(error)) from None


@router.post("/{note_id}/export")
def export(project_id: str, note_id: str, data: ExportInput, request: Request, owner: Owner):
    store = MemoryStore(request.app.state.database)
    store.history(project_id, note_id)  # Verify the project binding before reading content.
    with store.database.session() as db:
        note = db.get(MemoryEntry, note_id)
        if note.archived or note.quarantined:
            raise HTTPException(409, "Memória arquivada ou em quarentena")
        try:
            digest = vault_for(request).write(
                project_id, note_id + ".md", note.content, expected_digest=data.expected_digest
            )
        except VaultError as error:
            raise HTTPException(409, str(error)) from None
    return {"filename": note_id + ".md", "digest": digest}
