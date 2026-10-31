"""Next.js sources and declarative QA; models cannot change the scaffold."""

import hashlib
import json
import re
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .config import ROOT

RUNTIME = ROOT / "infra" / "next-sandbox"
SCAFFOLD = (
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "next-env.d.ts",
    "next.config.mjs",
    "app/layout.tsx",
)
SOURCE = re.compile(
    r"(?:app/page\.tsx|app/globals\.css|components/[a-z][a-z0-9-]{0,50}\.tsx|tests/acceptance\.json)\Z"
)


@lru_cache(maxsize=1)
def scaffold():
    return {path: (RUNTIME / "scaffold" / path).read_text(encoding="utf-8") for path in SCAFFOLD}


def runtime_sources():
    return {
        **{"scaffold/" + p: c for p, c in scaffold().items()},
        **{
            name: (RUNTIME / name).read_text(encoding="utf-8")
            for name in ("Dockerfile", "run.mjs", "read-html.mjs")
        },
        **{
            name: (RUNTIME / name).read_text(encoding="utf-8")
            for name in ("browser-checks.mjs", "browser/package.json", "browser/package-lock.json")
        },
    }


def runtime_fingerprint(files=None):
    return hashlib.sha256(
        json.dumps(runtime_sources() if files is None else files, sort_keys=True).encode()
    ).hexdigest()


class ProjectFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(max_length=100)
    content: str = Field(min_length=1, max_length=200000)

    @model_validator(mode="after")
    def validate_path(self):
        if self.path not in SCAFFOLD and not SOURCE.fullmatch(self.path):
            raise ValueError("Caminho Next.js não autorizado")
        return self


class GeneratedFile(ProjectFile):
    content: str = Field(min_length=1, max_length=16000)

    @model_validator(mode="after")
    def generated_only(self):
        if not SOURCE.fullmatch(self.path):
            raise ValueError("Configuração é exclusiva do servidor")
        return self


class NextPart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: list[GeneratedFile] = Field(min_length=1, max_length=6)


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    contains: str = Field(min_length=1, max_length=1000)
    not_contains: str = Field(default="", max_length=1000)
    status: int = Field(default=200, ge=100, le=599)


class ClickAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["click"]
    role: Literal["button", "link", "checkbox"]
    name: str = Field(min_length=1, max_length=200)


class FillAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["fill"]
    label: str = Field(min_length=1, max_length=200)
    value: str = Field(max_length=500)


class BrowserCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)
    actions: list[Annotated[ClickAction | FillAction, Field(discriminator="action")]] = Field(
        min_length=1, max_length=6
    )
    expect_text: str = Field(min_length=1, max_length=1000)


class Acceptance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    checks: list[Check] = Field(min_length=1, max_length=12)
    browser_checks: list[BrowserCheck] = Field(default_factory=list, max_length=6)


class NextSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: list[ProjectFile] = Field(min_length=9, max_length=18)
    runtime_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_project(self):
        entries = {f.path: f.content for f in self.files}
        if (
            len(entries) != len(self.files)
            or sum(len(v.encode()) for v in entries.values()) > 262144
        ):
            raise ValueError("Arquivos duplicados ou projeto excede 256 KiB")
        if (
            not {*SCAFFOLD, "app/page.tsx", "app/globals.css", "tests/acceptance.json"}
            <= entries.keys()
        ):
            raise ValueError("Página, CSS e critérios QA obrigatórios")
        Acceptance.model_validate_json(entries["tests/acceptance.json"])
        return self

    @property
    def digest(self):
        canonical = sorted((f.path, f.content) for f in self.files)
        payload = [self.runtime_hash, canonical]
        return hashlib.sha256(json.dumps(payload, ensure_ascii=True).encode()).hexdigest()


class NextProject(NextSnapshot):
    runtime_hash: str = Field(default_factory=runtime_fingerprint, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def current_runtime_only(self):
        entries = {f.path: f.content for f in self.files}
        if self.runtime_hash != runtime_fingerprint():
            raise ValueError("Runtime aprovado mudou; gere uma nova execução")
        if any(entries.get(path) != content for path, content in scaffold().items()):
            raise ValueError("Scaffold revisado não pode ser alterado")
        return self


def validate_part(role, deliverable):
    part = NextPart.model_validate_json(deliverable)
    allowed = {
        "DEV": lambda p: p == "app/page.tsx" or p.startswith("components/"),
        "DESIGNER": lambda p: p == "app/globals.css",
        "QA": lambda p: p == "tests/acceptance.json",
    }
    if role not in allowed or any(not allowed[role](f.path) for f in part.files):
        raise ValueError("Artefato não autorizado para este agente")
    if role == "DEV" and not any(f.path == "app/page.tsx" for f in part.files):
        raise ValueError("DEV deve gerar a página principal")
    if role == "QA":
        Acceptance.model_validate_json(part.files[0].content)
    return part


def project_for_steps(steps):
    generated = []
    for step in steps:
        if step["agent"] in {"DEV", "DESIGNER", "QA"}:
            generated.extend(validate_part(step["agent"], step["deliverable"]).files)
    snapshots = [step["project_snapshot"] for step in steps if "project_snapshot" in step]
    if snapshots:
        if len(snapshots) != 1:
            raise ValueError("Snapshot único obrigatório")
        snapshot = NextSnapshot.model_validate(snapshots[0])
        expected = sorted((f.path, f.content) for f in generated)
        actual = sorted((f.path, f.content) for f in snapshot.files if f.path not in SCAFFOLD)
        if expected != actual:
            raise ValueError("Fontes divergentes do snapshot aprovado")
        return snapshot
    files = [*generated, *[ProjectFile(path=p, content=c) for p, c in scaffold().items()]]
    return NextProject(files=files)
