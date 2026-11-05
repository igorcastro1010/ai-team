"""Project-scoped local issue associations; publication uses github_actions only."""

import time

from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, new_id


class IssueLink(Base):
    __tablename__ = "issue_links"
    __table_args__ = (
        UniqueConstraint("project_id", "request_id", name="uq_issue_request"),
        Index("ix_issue_project_filters", "project_id", "agent", "status", "priority"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(100))
    request_digest: Mapped[str] = mapped_column(String(64))
    action_id: Mapped[str] = mapped_column(ForeignKey("github_actions.id"), unique=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("tasks.id"), index=True)
    parent_issue_id: Mapped[str | None] = mapped_column(ForeignKey("issue_links.id"), index=True)
    agent: Mapped[str] = mapped_column(String(20), default="DEV")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(20), default="todo")
    branch: Mapped[str] = mapped_column(String(90), default="")
    commit_sha: Mapped[str] = mapped_column(String(40), default="")
    pull_request_number: Mapped[int | None] = mapped_column(Integer)
    remote_state: Mapped[str] = mapped_column(String(20), default="")
    synced_at: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()))
