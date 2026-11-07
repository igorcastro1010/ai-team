"""Private, additive video job records. No credentials or remote asset locations."""

import time

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, new_id


class VideoJob(Base):
    __tablename__ = "video_jobs"
    __table_args__ = (
        Index("ix_video_request", "project_id", "request_id", unique=True),
        Index("ix_video_queue", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    approved_digest: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(24), default="pending_approval")
    error: Mapped[str] = mapped_column(String(200), default="")
    lease_token: Mapped[str] = mapped_column(String(36), default="")
    lease_expires_at: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
