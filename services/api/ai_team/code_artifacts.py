"""Bounded generated source, never interpreted as host paths or commands."""

import hashlib
import json
import re
import sys

from pydantic import BaseModel, ConfigDict, Field, model_validator

CODE_SCOPES = frozenset({"python_code", "nextjs_code"})


class CodeFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(max_length=64)
    content: str = Field(min_length=1, max_length=16000)

    @model_validator(mode="after")
    def validate_path(self):
        stem = self.path.removesuffix(".py")
        if (
            not re.fullmatch(r"[a-z][a-z0-9_]{0,60}\.py", self.path)
            or stem in sys.stdlib_module_names
            or stem in {"con", "prn", "aux", "nul", "sitecustomize", "usercustomize"}
            or re.fullmatch(r"(com|lpt)[0-9]", stem)
        ):
            raise ValueError("Nome Python simples e distinto da biblioteca padrão obrigatório")
        return self


class CodeBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: list[CodeFile] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_bundle(self):
        if len({f.path for f in self.files}) != len(self.files):
            raise ValueError("Arquivos duplicados")
        if sum(len(f.content.encode("utf-8")) for f in self.files) > 49152:
            raise ValueError("Artefatos excedem 48 KiB")
        return self

    @property
    def digest(self):
        canonical = sorted((f.path, f.content) for f in self.files)
        return hashlib.sha256(json.dumps(canonical, ensure_ascii=True).encode()).hexdigest()


def bundle_for_steps(steps):
    source, tests = [], []
    for step in steps:
        if step["agent"] in {"DEV", "QA"}:
            parsed = CodeBundle.model_validate_json(step["deliverable"])
            destination = tests if step["agent"] == "QA" else source
            destination.extend(parsed.files)
    if not source or not tests:
        raise ValueError("Fonte DEV e testes QA obrigatórios")
    if any(f.path.startswith("test_") for f in source):
        raise ValueError("DEV não pode fornecer testes QA")
    if any(not f.path.startswith("test_") for f in tests):
        raise ValueError("QA somente pode fornecer test_*.py")
    return CodeBundle(files=[*source, *tests])


def bundle_for_scope(scope, steps):
    if scope == "python_code":
        return bundle_for_steps(steps)
    if scope == "nextjs_code":
        from .next_artifacts import project_for_steps

        return project_for_steps(steps)
    raise ValueError("Escopo sem artefatos executáveis")
