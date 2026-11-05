"""Exact persisted delegation bindings; never infer task ownership from a title."""

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class DelegatedTask(Base):
    __tablename__ = "delegated_tasks"
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    binding_version: Mapped[str] = mapped_column(String(8), default="v1")
