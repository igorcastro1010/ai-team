"""Versioned project knowledge and bounded lexical retrieval; no inference."""

import hashlib
import re
import time
import unicodedata

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, update

from .memory_models import MemoryChunk, MemoryEntry, MemoryRevision
from .memory_safety import INJECTION, validate_text
from .models import Event, Project


def text_digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalized(text):
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


def view(row):
    return {
        key: getattr(row, key)
        for key in (
            "id",
            "project_id",
            "title",
            "content",
            "source",
            "version",
            "digest",
            "quarantined",
            "archived",
            "created_at",
            "updated_at",
        )
    }


class MemoryStore:
    def __init__(self, database):
        self.database = database

    def _project(self, db, project_id):
        if not db.get(Project, project_id):
            raise HTTPException(404, "Projeto não encontrado")

    def put(
        self, project_id, title, content, source, actor, *, note_id=None, expected_version=None
    ):
        try:
            for text, maximum in ((title, 180), (content, 64000), (source, 240)):
                validate_text(text, maximum=maximum)
            if not title.strip() or not content.strip() or not source.strip():
                raise ValueError("Título, conteúdo e origem obrigatórios")
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        digest = text_digest(content)
        with self.database.session() as db:
            self._project(db, project_id)
            row = db.get(MemoryEntry, note_id) if note_id else None
            if note_id and (not row or row.project_id != project_id or row.archived):
                raise HTTPException(404, "Memória não encontrada neste projeto")
            if row and expected_version is not None and row.version != expected_version:
                raise HTTPException(409, "Memória alterada; revise a versão atual")
            if not note_id:
                duplicate = db.scalar(
                    select(MemoryEntry).where(
                        MemoryEntry.project_id == project_id,
                        MemoryEntry.digest == digest,
                        MemoryEntry.archived.is_(False),
                    )
                )
                if duplicate:
                    return view(duplicate)
            if row and row.digest == digest and row.title == title and row.source == source:
                return view(row)
            values = dict(
                title=title,
                content=content,
                source=source,
                digest=digest,
                quarantined=bool(INJECTION.search(title + "\n" + content)),
                updated_at=int(time.time()),
            )
            if row:
                old_version = row.version
                changed = db.execute(
                    update(MemoryEntry)
                    .where(
                        MemoryEntry.id == row.id,
                        MemoryEntry.version == old_version,
                        MemoryEntry.archived.is_(False),
                    )
                    .values(**values, version=old_version + 1)
                )
                if changed.rowcount != 1:
                    raise HTTPException(409, "Memória alterada por outra operação")
                db.refresh(row)
            else:
                row = MemoryEntry(project_id=project_id, **values)
                db.add(row)
                db.flush()
            db.execute(delete(MemoryChunk).where(MemoryChunk.memory_id == row.id))
            seen = set()
            for ordinal, offset in enumerate(range(0, len(content), 1400)):
                passage = content[offset : offset + 1600]
                key = text_digest(passage)
                if key in seen:
                    continue
                seen.add(key)
                db.add(
                    MemoryChunk(
                        memory_id=row.id,
                        ordinal=ordinal,
                        project_id=project_id,
                        content=passage,
                        terms=normalized(title + "\n" + passage),
                    )
                )
            db.add(
                MemoryRevision(
                    memory_id=row.id,
                    version=row.version,
                    title=title,
                    content=content,
                    source=source,
                    digest=digest,
                    actor=actor,
                )
            )
            db.add(
                Event(
                    kind="memory.updated",
                    resource_id=row.id,
                    summary=f"Memória v{row.version} salva no projeto {project_id}",
                    actor=actor,
                )
            )
            db.commit()
            return view(row)

    def snapshot(self, project_id):
        with self.database.session() as db:
            self._project(db, project_id)
            rows = db.scalars(
                select(MemoryEntry)
                .where(
                    MemoryEntry.project_id == project_id,
                    MemoryEntry.archived.is_(False),
                )
                .order_by(MemoryEntry.updated_at.desc(), MemoryEntry.id)
                .limit(201)
            ).all()
            return {"items": [view(row) for row in rows[:200]], "truncated": len(rows) > 200}

    def revision(self, project_id):
        with self.database.session() as db:
            self._project(db, project_id)
            rows = db.execute(
                select(
                    MemoryEntry.id,
                    MemoryEntry.version,
                    MemoryEntry.digest,
                    MemoryEntry.archived,
                    MemoryEntry.quarantined,
                )
                .where(MemoryEntry.project_id == project_id)
                .order_by(MemoryEntry.id)
            ).all()
            return text_digest(repr(rows))

    def search(self, project_id, query, limit=6):
        words = sorted(set(re.findall(r"\w{3,}", normalized(query))))[:24]
        if not words:
            return []
        with self.database.session() as db:
            self._project(db, project_id)
            rows = db.execute(
                select(MemoryEntry, MemoryChunk)
                .join(MemoryChunk, MemoryEntry.id == MemoryChunk.memory_id)
                .where(
                    MemoryEntry.project_id == project_id,
                    MemoryChunk.project_id == project_id,
                    MemoryEntry.archived.is_(False),
                    MemoryEntry.quarantined.is_(False),
                    or_(*(MemoryChunk.terms.contains(word, autoescape=True) for word in words)),
                )
                .order_by(MemoryEntry.updated_at.desc(), MemoryEntry.id)
                .limit(240)
            ).all()
            best = {}
            for row, chunk in rows:
                score = sum(word in chunk.terms for word in words)
                if score > best.get(row.id, (0, {}))[0]:
                    best[row.id] = (score, {**view(row), "content": chunk.content})
            matches = list(best.values())
            matches.sort(key=lambda item: (-item[0], item[1]["id"]))
            return [item[1] for item in matches[: max(0, min(limit, 12))]]

    def history(self, project_id, note_id):
        with self.database.session() as db:
            self._project(db, project_id)
            row = db.get(MemoryEntry, note_id)
            if not row or row.project_id != project_id:
                raise HTTPException(404, "Memória não encontrada neste projeto")
            revisions = db.scalars(
                select(MemoryRevision)
                .where(
                    MemoryRevision.memory_id == note_id,
                )
                .order_by(MemoryRevision.version.desc())
                .limit(100)
            ).all()
            return [
                {
                    key: getattr(item, key)
                    for key in (
                        "version",
                        "title",
                        "content",
                        "source",
                        "digest",
                        "actor",
                        "created_at",
                    )
                }
                for item in revisions
            ]

    def archive(self, project_id, note_id, actor):
        with self.database.session() as db:
            self._project(db, project_id)
            row = db.get(MemoryEntry, note_id)
            if not row or row.project_id != project_id:
                raise HTTPException(404, "Memória não encontrada neste projeto")
            row.archived = True
            db.add(
                Event(
                    kind="memory.archived",
                    resource_id=row.id,
                    summary="Memória arquivada; recuperação invalidada",
                    actor=actor,
                )
            )
            db.commit()
