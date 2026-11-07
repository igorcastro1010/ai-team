"""Production probes must fail closed without printing database secrets."""

import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def load(name):
    path = ROOT / "infra" / "production" / f"{name}.py"
    assert path.is_file(), f"Missing production helper {name}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_secrets_are_optional_except_database_and_cannot_override_unrelated_env(tmp_path):
    entry = load("entrypoint")
    (tmp_path / "database_url").write_text("postgresql+psycopg://private/db\n")
    (tmp_path / "gemini_api_key").write_text("synthetic-key")
    (tmp_path / "PATH").write_text("/untrusted")
    env = entry.load_secrets(tmp_path, {"PATH": "/safe"})
    assert env["AI_TEAM_DATABASE_URL"] == "postgresql+psycopg://private/db"
    assert env["AI_TEAM_GEMINI_API_KEY"] == "synthetic-key"
    assert env["PATH"] == "/safe"
    assert "AI_TEAM_GOOGLE_READ_TOKEN" not in env


def test_entrypoint_rejects_secret_links_and_arbitrary_commands(tmp_path):
    entry = load("entrypoint")
    with pytest.raises(ValueError):
        entry.validate_command(["sh", "-c", "echo unsafe"])
    entry.validate_command(["python", "-m", "ai_team.worker"])
    with pytest.raises(ValueError):
        entry.load_secrets(tmp_path, {})


@pytest.mark.parametrize(
    "last_seen,healthy", [(1000, True), (0, False), (None, False), (2000, False)]
)
def test_worker_heartbeat_rejects_absent_stale_and_future_values(last_seen, healthy):
    probe = load("healthcheck")
    assert probe.fresh_heartbeat(last_seen, now=1005) is healthy


def test_probe_errors_are_sanitized(capsys, monkeypatch):
    probe = load("healthcheck")

    def failed(_):
        raise RuntimeError("postgresql://secret:password@private/db")

    monkeypatch.setattr(probe, "check", failed)
    assert probe.main(["worker"]) == 1
    output = capsys.readouterr()
    assert "secret" not in output.out + output.err


def test_compose_render_preserves_private_ports_limits_and_readonly_secrets(tmp_path):
    docker = shutil.which("docker")
    if not docker:
        pytest.skip("Docker Compose CLI unavailable")
    private_env = tmp_path / "runtime.env"
    private_env.write_text("", encoding="utf-8")
    interpolation = tmp_path / "compose.env"
    interpolation.write_text(
        f"AI_TEAM_PRODUCTION_ENV_FILE={private_env.as_posix()}\n"
        f"AI_TEAM_SECRETS_DIRECTORY={tmp_path.as_posix()}\n"
        "AI_TEAM_PUBLIC_ORIGIN=https://synthetic.example.invalid\n",
        encoding="utf-8",
    )
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("AI_TEAM_")
    }
    result = subprocess.run(
        [docker, "compose", "--env-file", str(interpolation), "-f",
         str(ROOT / "compose.production.yaml"), "--profile", "*", "config", "--format", "json"],
        env=environment, capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, "Synthetic Compose configuration rejected"
    services = json.loads(result.stdout)["services"]
    assert services["api"]["ports"][0]["host_ip"] == "127.0.0.1"
    for name, service in services.items():
        assert service["read_only"] is True
        assert service["cap_drop"] == ["ALL"]
        assert service["pids_limit"] <= 128
        assert int(service["mem_limit"]) > 0
        assert float(service["cpus"]) > 0
        if name != "api":
            assert not service.get("ports")
        for mount in service.get("volumes", []):
            assert "docker.sock" not in mount["target"]
            if mount["target"] == "/run/secrets":
                assert mount["read_only"] is True
                assert mount["bind"]["create_host_path"] is False
    assert services["video-worker"]["command"] == ["python", "-m", "ai_team.video_worker"]
    assert services["init-db"]["restart"] == "no"
