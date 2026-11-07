"""Additive private studio metadata; paths are derived by the server only."""

import time

from sqlalchemy import JSON, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, new_id


class MediaAsset(Base):
    __tablename__ = "video_media"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(8))
    mime: Mapped[str] = mapped_column(String(32))
    extension: Mapped[str] = mapped_column(String(5))
    bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class VideoDraft(Base):
    __tablename__ = "video_drafts"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    document: Mapped[dict] = mapped_column(JSON)


class VideoTemplate(Base):
    __tablename__ = "video_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    document: Mapped[dict] = mapped_column(JSON)


class VideoProgress(Base):
    __tablename__ = "video_progress"
    job_id: Mapped[str] = mapped_column(ForeignKey("video_jobs.id"), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)
    phase: Mapped[str] = mapped_column(String(40), default="pending_approval")
