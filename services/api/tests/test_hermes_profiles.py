import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("hermes_profiles", ROOT / "tools/hermes_profiles.py")
profiles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profiles)


def test_generates_native_profiles_without_tokens_or_execution(tmp_path):
    home = tmp_path / "home"
    created = profiles.provision(home, ROOT / "infra/hermes/team.yaml")
    assert len(created) == 7
    for name in created:
        directory = home / "profiles" / name
        config = yaml.safe_load((directory / "config.yaml").read_text())
        assert config["platform_toolsets"]["api_server"] == []
        assert config["platform_toolsets"]["cron"] == []
        assert config["mcp_servers"] == {}
        assert config["auth"]["adopt_external_logins"] is False
        assert not (directory / ".env").exists()
        assert "aprovação" in (directory / "SOUL.md").read_text(encoding="utf-8")


def test_rerun_preserves_existing_profile_and_credentials(tmp_path):
    home = tmp_path / "home"
    profiles.provision(home, ROOT / "infra/hermes/team.yaml")
    secret = home / "profiles/ceo/.env"
    secret.write_text("existing-private-state")
    soul = home / "profiles/ceo/SOUL.md"
    soul.write_text("custom persona")
    assert profiles.provision(home, ROOT / "infra/hermes/team.yaml") == []
    assert secret.read_text() == "existing-private-state"
    assert soul.read_text() == "custom persona"


def test_refuses_invalid_profile_manifest(tmp_path):
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text('profiles:\n  ../escape:\n    title: unsafe\n')
    with pytest.raises(ValueError):
        profiles.provision(tmp_path / "home", manifest)


def test_refuses_linked_profile_destination(tmp_path, monkeypatch):
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p.name == "profiles" or original(p))
    with pytest.raises(ValueError):
        profiles.provision(tmp_path / "home", ROOT / "infra/hermes/team.yaml")
