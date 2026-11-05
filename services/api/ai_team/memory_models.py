"""Additive private-schema knowledge tables; no changes to legacy records."""

import time

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, new_id


class MemoryEntry(Base):
    __tablename__ = "memory_entries"
    __table_args__ = (Index("ix_memory_project_digest", "project_id", "digest", "archived"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(240))
    version: Mapped[int] = mapped_column(Integer, default=1)
    digest: Mapped[str] = mapped_column(String(64))
    quarantined: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
    updated_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))


class MemoryRevision(Base):
    __tablename__ = "memory_revisions"
    memory_id: Mapped[str] = mapped_column(ForeignKey("memory_entries.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(240))
    digest: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))


class MemoryChunk(Base):
    __tablename__ = "memory_chunks"
    memory_id: Mapped[str] = mapped_column(ForeignKey("memory_entries.id"), primary_key=True)
    ordinal: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    terms: Mapped[str] = mapped_column(Text)
