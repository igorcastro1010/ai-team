import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("hermes_policy", ROOT / "infra/hermes/healthcheck.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


def test_runtime_config_disables_external_login_adoption():
    import yaml

    config = yaml.safe_load((ROOT / "infra/hermes/config.yaml").read_text(encoding="utf-8"))
    assert config["auth"]["adopt_external_logins"] is False


def test_effective_policy_includes_mcp_and_non_configurable_toolsets():
    config = {"platform_toolsets": {"api_server": [], "cron": []}, "mcp_servers": {}}
    assert policy.validate_policy(config, set(), set())
    assert not policy.validate_policy(config, {"mcp_hidden_server"}, set())
    assert not policy.validate_policy(config, {"non_configurable_plugin"}, set())
    assert not policy.validate_policy(config, set(), {"cron_hidden_mcp"})
    assert not policy.validate_policy({**config, "mcp_servers": {"hidden": {}}}, set(), set())
    assert not policy.validate_policy({}, set(), set())
    assert not policy.validate_policy({"platform_toolsets": {"api_server": []}}, set(), set())


def test_health_fails_before_network_when_runtime_resolves_hidden_tools(monkeypatch, capsys):
    config_module = types.ModuleType("hermes_cli.config")
    config_module.load_config = lambda: {"platform_toolsets": {"api_server": [], "cron": []}}
    tools_module = types.ModuleType("hermes_cli.tools_config")
    calls = []

    def resolve(config, platform, *, include_default_mcp_servers):
        calls.append((platform, include_default_mcp_servers))
        return {"hidden_mcp"}

    tools_module._get_platform_tools = resolve
    monkeypatch.setitem(sys.modules, "hermes_cli", types.ModuleType("hermes_cli"))
    monkeypatch.setitem(sys.modules, "hermes_cli.config", config_module)
    monkeypatch.setitem(sys.modules, "hermes_cli.tools_config", tools_module)
    assert policy.main() == 1
    assert calls == [("api_server", True), ("cron", True)]
    assert capsys.readouterr().err == "Hermes health/policy check failed\n"
