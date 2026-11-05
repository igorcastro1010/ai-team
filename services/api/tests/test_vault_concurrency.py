import hashlib
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from ai_team.memory_vault import Vault, VaultError


def test_concurrent_exports_cannot_both_replace_one_reviewed_digest(tmp_path, monkeypatch):
    import ai_team.memory_vault as module

    vault = Vault(tmp_path)
    digest = vault.write("project", "note.md", "Original")
    entered, release = Event(), Event()
    original = module.tempfile.NamedTemporaryFile
    calls = 0

    def hold_first(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(module.tempfile, "NamedTemporaryFile", hold_first)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(vault.write, "project", "note.md", "First", expected_digest=digest)
        assert entered.wait(5)
        try:
            second = pool.submit(
                vault.write, "project", "note.md", "Second", expected_digest=digest
            )
            with pytest.raises(VaultError):
                second.result(timeout=5)
        finally:
            release.set()
        assert first.result(timeout=5) == hashlib.sha256(b"First").hexdigest()
    assert vault.read("project", "note.md") == "First"


def test_export_lock_is_exclusive_and_released_after_failure(tmp_path, monkeypatch):
    import ai_team.memory_vault as module

    vault = Vault(tmp_path)
    digest = vault.write("project", "note.md", "Original")
    lock = tmp_path / "project" / ".note.md.lock"
    lock.write_text("stale", encoding="utf-8")
    with pytest.raises(VaultError):
        vault.write("project", "note.md", "New", expected_digest=digest)
    assert lock.read_text(encoding="utf-8") == "stale"
    lock.unlink()
    with monkeypatch.context() as scoped:
        scoped.setattr(module.os, "replace", lambda *args: (_ for _ in ()).throw(OSError("test")))
        with pytest.raises(OSError):
            vault.write("project", "note.md", "New", expected_digest=digest)
    assert not lock.exists()
    assert vault.write("project", "note.md", "New", expected_digest=digest)


def test_another_process_cannot_write_while_export_lock_is_held(tmp_path):
    from ai_team.memory_vault import export_lock

    vault = Vault(tmp_path)
    digest = vault.write("project", "note.md", "Original")
    script = (
        "import sys; from ai_team.memory_vault import Vault,VaultError; "
        "v=Vault(sys.argv[1]);\n"
        "try: v.write('project','note.md','Other process',expected_digest=sys.argv[2])\n"
        "except VaultError: sys.exit(17)\n"
    )
    with export_lock(tmp_path / "project" / "note.md"):
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path), digest],
            capture_output=True,
            timeout=15,
            check=False,
        )
    assert result.returncode == 17, result.stderr
    assert vault.read("project", "note.md") == "Original"
