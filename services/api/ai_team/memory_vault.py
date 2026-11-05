"""Bounded Markdown-only access inside a server-configured, service-owned vault."""

import hashlib
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .memory_safety import validate_text


class VaultError(ValueError):
    pass


@contextmanager
def export_lock(target):
    # O_EXCL is shared by processes, not just threads. Never remove someone else's lock.
    lock = target.with_name("." + target.name + ".lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError:
        raise VaultError(
            "Exportação bloqueada; outra escrita ou lock pendente exige revisão"
        ) from None
    try:
        yield
    finally:
        os.close(descriptor)
        lock.unlink()


def linked(path):
    details = path.lstat()
    return (
        stat.S_ISLNK(details.st_mode)
        or bool(getattr(details, "st_file_attributes", 0) & 0x400)
        or (path.is_file() and details.st_nlink != 1)
    )


class Vault:
    def __init__(self, root):
        self.root = Path(root).absolute()
        if str(self.root).startswith("\\\\"):
            raise VaultError("Vault deve estar em disco local")
        for part in [*reversed(self.root.parents), self.root]:
            if part.exists() and linked(part):
                raise VaultError("Vault não aceita links ou pontos de redirecionamento")

    def _path(self, project_id, relative_path):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", project_id):
            raise VaultError("Identificador de projeto inválido")
        # Flat project namespaces avoid nested paths, hidden config and Windows ADS/devices.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.md", relative_path):
            raise VaultError("Somente nomes Markdown simples dentro do projeto")
        stem = relative_path.split(".", 1)[0].upper()
        if stem in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(10)),
            *(f"LPT{i}" for i in range(10)),
        }:
            raise VaultError("Nome reservado pelo Windows")
        target = self.root / project_id / relative_path
        for path in (*reversed(self.root.parents), self.root, target.parent, target):
            if path.exists() or path.is_symlink():
                if linked(path):
                    raise VaultError("Links não são permitidos no vault")
        if not target.resolve().is_relative_to(self.root.resolve()):
            raise VaultError("Caminho fora do vault")
        return target

    def read(self, project_id, relative_path):
        target = self._path(project_id, relative_path)
        try:
            # Bound the actual read, not just the stat, to handle file growth safely.
            with target.open("rb") as stream:
                data = stream.read(64001)
            text = data.decode("utf-8")
            validate_text(text)
            self._path(project_id, relative_path)
            return text
        except (OSError, UnicodeError, ValueError):
            raise VaultError("Markdown indisponível, inválido ou contém credenciais") from None

    def write(self, project_id, relative_path, content, *, expected_digest=None):
        try:
            validate_text(content)
        except ValueError as error:
            raise VaultError(str(error)) from None
        target = self._path(project_id, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        self._path(project_id, relative_path)
        with export_lock(target):
            return self._write_locked(project_id, relative_path, content, expected_digest)

    def _reviewed_target(self, project_id, relative_path, expected_digest):
        target = self._path(project_id, relative_path)
        if target.exists():
            current = self.read(project_id, relative_path)
            actual = hashlib.sha256(current.encode()).hexdigest()
            if expected_digest is None or actual != expected_digest:
                raise VaultError("Arquivo já existe ou mudou; revise o digest antes de substituir")
        elif expected_digest:
            raise VaultError("Arquivo removido; revise antes de substituir")
        return target

    def _write_locked(self, project_id, relative_path, content, expected_digest):
        target = self._reviewed_target(project_id, relative_path, expected_digest)
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=target.parent, suffix=".tmp", delete=False
            ) as stream:
                temp_name = stream.name
                stream.write(content.encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            # Editors outside this lock can change the file while the temporary is written.
            # Recheck the approved digest/absence and path immediately before replacement;
            # this is not an atomic compare-and-swap against uncooperative external editors.
            target = self._reviewed_target(project_id, relative_path, expected_digest)
            self._path(project_id, relative_path)
            os.replace(temp_name, target)
        finally:
            if temp_name and Path(temp_name).exists():
                Path(temp_name).unlink()
        return hashlib.sha256(content.encode()).hexdigest()

    def files(self, project_id):
        folder = self._path(project_id, "probe.md").parent
        if not folder.exists():
            return []
        result = []
        for index, path in enumerate(folder.iterdir()):
            if index >= 1000:
                raise VaultError("Limite de 1000 arquivos por projeto atingido")
            if path.suffix == ".md":
                self._path(project_id, path.name)
                result.append(path.name)
        return sorted(result)
