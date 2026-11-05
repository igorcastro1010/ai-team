"""Persistent context estimates and conservative budget accounting."""

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base, new_id


class BudgetAccount(Base):
    __tablename__ = "optimizer_budgets"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), primary_key=True)
    scope_id: Mapped[str] = mapped_column(String(80), primary_key=True, default="")
    limit: Mapped[int] = mapped_column(Integer, default=500000)
    used: Mapped[int] = mapped_column(Integer, default=0)
    reserved: Mapped[int] = mapped_column(Integer, default=0)


class OptimizerAdmission(Base):
    __tablename__ = "optimizer_admissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    agent: Mapped[str] = mapped_column(String(20))
    task_id: Mapped[str] = mapped_column(String(80))
    reserved: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_flight")


class OptimizerRecord(Base):
    __tablename__ = "optimizer_records"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    result: Mapped[dict] = mapped_column(JSON)
