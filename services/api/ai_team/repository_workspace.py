"""Private Git snapshots. Generated code is never imported or run here."""

import os
import subprocess
import uuid
from pathlib import Path

from .repository_policy import RepositoryBundle, RepositoryFile


class TaskWorkspace:
    def __init__(self, root, task_id):
        if str(uuid.UUID(task_id)) != task_id:
            raise ValueError("Identidade de tarefa inválida")
        self.root = Path(root).resolve()
        self.path = self.root / task_id

    def git(self, *args):
        environment = {k: v for k, v in os.environ.items()
                       if k.upper() in {"PATH", "SYSTEMROOT", "TEMP", "TMP", "WINDIR"}}
        environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                           GIT_TERMINAL_PROMPT="0")
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=" + str(self.path / ".empty-hooks"),
             "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false",
             "-c", "user.name=AI TEAM Executor", "-c", "user.email=executor@ai-team.local",
             *args], cwd=self.path, env=environment, capture_output=True, timeout=10,
            check=False, encoding="utf-8", errors="replace",
        )
        if result.returncode:
            raise RuntimeError("Git local falhou; nenhuma operação remota")
        return result.stdout

    def initialize(self, files):
        entries = [RepositoryFile(path=p, content=c) for p, c in files.items()]
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("Workspace não pode ser link")
        self.path.mkdir(exist_ok=False)
        (self.path / ".empty-hooks").mkdir()
        self.git("init", "--template=" + str(self.path / ".empty-hooks"),
                 "--initial-branch=codex/ai-team/task-" + self.path.name)
        for entry in entries:
            (self.path / entry.path).write_text(entry.content, encoding="utf-8", newline="")
        if entries:
            self.git("add", "--", *[entry.path for entry in entries])
        self.git("commit", "--allow-empty", "-m", "chore(snapshot): authorized source")

    def apply(self, bundle):
        bundle = RepositoryBundle.model_validate(bundle.model_dump())
        if self.path.is_symlink() or self.path.resolve().parent != self.root:
            raise ValueError("Workspace alterado")
        for entry in bundle.files:
            path = self.path / entry.path
            if path.is_symlink():
                raise ValueError("Links não autorizados")
            path.write_text(entry.content, encoding="utf-8", newline="")
        self.git("add", "--", *[entry.path for entry in bundle.files])
        diff = self.git("diff", "--cached", "--no-ext-diff", "--no-textconv", "--binary")
        if len(diff.encode()) > 131072:
            raise ValueError("Diff excede limite")
        return diff
