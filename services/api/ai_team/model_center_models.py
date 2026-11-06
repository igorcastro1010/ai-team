"""Additive private model policies, requests and routing journal."""

import time

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, new_id


class ModelPreference(Base):
    __tablename__ = "model_preferences"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    agent: Mapped[str] = mapped_column(String(20), primary_key=True)
    policy: Mapped[dict] = mapped_column(JSON, default=dict)
    authorized_until: Mapped[int] = mapped_column(Integer, default=0)


class ModelRequest(Base):
    __tablename__ = "model_requests"
    __table_args__ = (UniqueConstraint("project_id", "request_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(100))
    digest: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), unique=True)


class ModelProviderState(Base):
    __tablename__ = "model_provider_state"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    observation: Mapped[dict] = mapped_column(JSON, default=dict)
    locked_at: Mapped[int] = mapped_column(Integer, default=0)


class ModelCall(Base):
    __tablename__ = "model_calls"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    stage: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(20))
    model: Mapped[str] = mapped_column(String(80))
    cloud_project: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(240))
    admitted: Mapped[bool] = mapped_column(Boolean, default=False)
    reserved_tokens: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    retry_after: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
