import time
import uuid

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class Owner(Base):
    __tablename__ = "owners"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)


class AuthSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("owners.id"))
    expires_at: Mapped[int] = mapped_column(Integer, index=True)


class LoginThrottle(Base):
    __tablename__ = "login_throttles"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    reset_at: Mapped[int] = mapped_column(Integer)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    mode: Mapped[str] = mapped_column(String(20), default="supervised")
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    agent: Mapped[str] = mapped_column(String(20), default="DEV")
    status: Mapped[str] = mapped_column(String(20), default="backlog", index=True)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)


class Event(Base):
    __tablename__ = "events"
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(36), unique=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(80), default="")
    summary: Mapped[str] = mapped_column(String(300))
    actor: Mapped[str] = mapped_column(String(80), default="owner")
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)


class GitHubAction(Base):
    __tablename__ = "github_actions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(String(300), default="")
    lease_token: Mapped[str] = mapped_column(String(36), default="")
    lease_expires_at: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)


class GitHubVerification(Base):
    __tablename__ = "github_verification"
    id: Mapped[str] = mapped_column(String(20), primary_key=True, default="github")
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ProviderObservation(Base):
    __tablename__ = "provider_observations"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class Run(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20))
    scope: Mapped[str] = mapped_column(String(30), default="draft_only")
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    stage: Mapped[int] = mapped_column(Integer, default=0)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(300), default="")
    lease_token: Mapped[str] = mapped_column(String(36), default="")
    lease_expires_at: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[int] = mapped_column(Integer, default=lambda: int(time.time()), index=True)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    last_seen: Mapped[int] = mapped_column(Integer, index=True)


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (Index("ix_schedules_due", "status", "next_run_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(20))
    interval_seconds: Mapped[int] = mapped_column(Integer)
    next_run_at: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[int] = mapped_column(Integer)
    max_runs: Mapped[int] = mapped_column(Integer)
    emitted: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[int] = mapped_column(Integer)


class ScheduleOccurrence(Base):
    __tablename__ = "schedule_occurrences"
    schedule_id: Mapped[str] = mapped_column(ForeignKey("schedules.id"), primary_key=True)
    number: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), unique=True)
    created_at: Mapped[int] = mapped_column(Integer)
