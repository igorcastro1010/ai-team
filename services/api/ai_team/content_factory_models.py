"""Additive, project-isolated deterministic production checkpoints."""

import time

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, new_id


class ContentProduction(Base):
    __tablename__ = "content_productions"
    __table_args__ = (
        Index("ix_content_request", "project_id", "request_id", unique=True),
        Index("ix_content_queue", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    request: Mapped[dict] = mapped_column(JSON)
    document: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    stage: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    digest: Mapped[str] = mapped_column(String(64), default="")
    approved_digest: Mapped[str] = mapped_column(String(64), default="")
    video_id: Mapped[str | None] = mapped_column(ForeignKey("video_jobs.id"), nullable=True)
    error: Mapped[str] = mapped_column(String(200), default="")
    lease_token: Mapped[str] = mapped_column(String(36), default="")
    lease_expires_at: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
