"""Idempotent local checkpoint indexing. Never writes to a remote service."""

from fastapi import HTTPException
from sqlalchemy import select

from .issue_store import IssueStore
from .knowledge_automation_models import DelegatedTask
from .memory_models import MemoryEntry
from .memory_store import MemoryStore
from .models import Event, Run


def audit(database, resource_id, kind):
    with database.session() as db:
        db.add(
            Event(
                kind=kind,
                resource_id=resource_id,
                actor="worker",
                summary="Indexação local recusou conteúdo; nenhuma ação remota executada",
            )
        )
        db.commit()


def refresh_vault(database, project_id):
    root = getattr(getattr(database, "settings", None), "memory_vault", "")
    if not root:
        return
    from .memory_routes import sync_vault
    from .memory_vault import Vault, VaultError

    try:
        result = sync_vault(database, project_id, Vault(root))
        if result["rejected"]:
            audit(database, project_id, "memory.vault_rejected")
    except (VaultError, HTTPException):
        audit(database, project_id, "memory.vault_rejected")


def index_run(database, run_id):
    store = MemoryStore(database)
    with database.session() as db:
        run = db.get(Run, run_id)
        if run is None:
            return
        project_id, steps = run.project_id, list(run.steps)
        bindings = db.scalars(
            select(DelegatedTask).where(
                DelegatedTask.run_id == run_id,
                DelegatedTask.project_id == project_id,
            )
        ).all()
        task_ids = [binding.task_id for binding in bindings]
    for step in steps[:6]:
        if not isinstance(step, dict) or not isinstance(step.get("summary"), str):
            continue
        stage = step.get("stage", 0)
        source = f"run:{run_id}:stage:{stage}"
        role = str(step.get("agent", "agente"))[:20]
        content = f"Execução {run_id}, etapa {stage}, {role}.\n" + step["summary"][:1000]
        with database.session() as db:
            old = db.scalar(
                select(MemoryEntry).where(
                    MemoryEntry.project_id == project_id,
                    MemoryEntry.source == source,
                    MemoryEntry.archived.is_(False),
                )
            )
            note_id, version = (old.id, old.version) if old else (None, None)
        try:
            store.put(
                project_id,
                f"Checkpoint {role} · etapa {stage}",
                content,
                source,
                "worker",
                note_id=note_id,
                expected_version=version,
            )
        except HTTPException:
            audit(database, run_id, "memory.checkpoint_rejected")
    for task_id in task_ids:
        try:
            IssueStore(database).prepare_task(task_id, f"ceo:{run_id}:{task_id}")
        except HTTPException:
            audit(database, run_id, "issue.delegation_rejected")
