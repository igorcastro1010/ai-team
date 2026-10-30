import json
import subprocess
import sys
from types import SimpleNamespace


def host(tmp_path, *, responses=None, missing=(), restart_pending=False):
    from ai_team.doctor import diagnose

    web = tmp_path / "node_modules/next/package.json"
    web.parent.mkdir(parents=True, exist_ok=True)
    web.write_text("{}")
    answers = {
        ("node", "--version"): "v24.16.0",
        ("wsl", "--version"): "WSL version: 2.6.1",
        ("wsl", "--status"): "",
        ("docker", "info", "--format", "{{.OSType}}"): "linux",
        ("docker", "compose", "version", "--short"): "2.40.0",
        **(responses or {}),
    }

    def runner(command, **kwargs):
        assert kwargs["timeout"] <= 5 and kwargs.get("shell", False) is False
        answer = answers[tuple(command)]
        if isinstance(answer, Exception):
            raise answer
        return SimpleNamespace(returncode=1 if answer is None else 0, stdout=answer or "")

    return diagnose(
        tmp_path,
        runner=runner,
        which=lambda name: None if name in missing else name,
        system="Windows",
        dependencies_ready=True,
        restart_pending=restart_pending,
    )


def test_native_ready_does_not_claim_missing_docker_is_ready(tmp_path):
    report = host(tmp_path, missing=("docker",))
    assert report["base_ready"] is True and report["hermes_ready"] is False
    assert any(item["id"] == "docker" and item["status"] == "blocked" for item in report["checks"])


def test_hermes_requires_modern_wsl_linux_engine_and_compose(tmp_path):
    assert host(tmp_path)["hermes_ready"] is True
    for changed in [
        {("wsl", "--version"): "WSL version: 1.0.0"},
        {("wsl", "--status"): None},
        {("docker", "info", "--format", "{{.OSType}}"): None},
        {("docker", "info", "--format", "{{.OSType}}"): "windows"},
        {("docker", "compose", "version", "--short"): None},
    ]:
        assert host(tmp_path, responses=changed)["hermes_ready"] is False


def test_tool_errors_and_timeout_are_sanitized(tmp_path):
    report = host(
        tmp_path,
        responses={
            ("docker", "info", "--format", "{{.OSType}}"): subprocess.TimeoutExpired(
                "secret-command", timeout=3, output="private-token"
            ),
            ("node", "--version"): RuntimeError("private-token"),
        },
    )
    assert report["base_ready"] is False and report["hermes_ready"] is False
    assert "private-token" not in json.dumps(report)
    assert "secret-command" not in json.dumps(report)


def test_incompatible_node_prevents_native_ready(tmp_path):
    assert host(tmp_path, responses={("node", "--version"): "v20.0.0"})["base_ready"] is False


def test_windows_restart_pending_blocks_hermes_even_when_commands_succeed(tmp_path):
    report = host(tmp_path, restart_pending=True)
    assert report["base_ready"] is True and report["hermes_ready"] is False
    check = next(row for row in report["checks"] if row["id"] == "restart")
    assert check["status"] == "blocked"


def test_restart_check_includes_windows_update_without_cbs(monkeypatch):
    from ai_team.doctor import windows_restart_pending

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def open_key(root, path):
        if path.endswith(r"WindowsUpdate\Auto Update\RebootRequired"):
            return Key()
        raise FileNotFoundError

    monkeypatch.setitem(
        sys.modules,
        "winreg",
        SimpleNamespace(
            HKEY_LOCAL_MACHINE=0,
            OpenKey=open_key,
        ),
    )
    assert windows_restart_pending() is True
