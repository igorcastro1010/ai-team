"""Owner-granted repository boundaries, independent from model output."""

import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .code_artifacts import CodeFile


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def filename(path):
    if re.fullmatch(r"[a-z][a-z0-9_]{0,50}\.md", path):
        if path[:-3] in {"con", "prn", "aux", "nul"}:
            raise ValueError("Nome reservado")
        return path
    CodeFile(path=path, content="validated")
    return path


class RepositoryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository: Literal["igorcastro1010/ai-team"] = "igorcastro1010/ai-team"
    profile: Literal["python_stdlib"] = "python_stdlib"
    base_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    max_tokens: int = Field(default=50000, ge=16000, le=100000, strict=True)
    base_branch: str = Field(default="main", pattern=r"^(?:main|codex/[a-z0-9][a-z0-9/_-]{0,100})$")
    directory: str = Field(min_length=1, max_length=160)
    read_paths: list[str] = Field(min_length=1, max_length=12)
    write_paths: list[str] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def boundaries(self):
        parts = self.directory.split("/")
        if any(not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,63}", p) for p in parts):
            raise ValueError("Pasta relativa explícita obrigatória")
        if any(p.lower() in {"secrets", "credentials", "node_modules"} for p in parts):
            raise ValueError("Pasta sensível ou de dependências proibida")
        for paths in (self.read_paths, self.write_paths):
            if len(set(paths)) != len(paths):
                raise ValueError("Caminhos duplicados")
            for path in paths:
                filename(path)
        if len(set(self.read_paths + self.write_paths)) > 12:
            raise ValueError("Máximo de 12 arquivos por tarefa")
        return self


class RepositoryFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(max_length=64)
    content: str = Field(min_length=1, max_length=16000)

    @model_validator(mode="after")
    def safe_name(self):
        filename(self.path)
        if "\x00" in self.content:
            raise ValueError("Arquivo binário proibido")
        return self


class RepositoryBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: RepositoryPolicy
    files: list[RepositoryFile] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def bounded_files(self):
        if len({f.path for f in self.files}) != len(self.files):
            raise ValueError("Arquivos duplicados")
        if any(f.path not in self.policy.write_paths for f in self.files):
            raise ValueError("Escrita fora da autorização")
        if sum(len(f.content.encode()) for f in self.files) > 49152:
            raise ValueError("Limite de 48 KiB")
        return self

    @property
    def digest(self):
        data = self.model_dump()
        data["files"] = sorted(data["files"], key=lambda f: f["path"])
        return fingerprint(data)
