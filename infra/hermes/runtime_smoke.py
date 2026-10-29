"""Container-only official Hermes runtime probe; never submits a model run."""

import argparse
import contextlib
import io
import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:8642"
MAX_BODY = 2_000_000
PROBE_CONTENT = "AI TEAM CI synthetic persistence probe; no model inference."


class SmokeFailure(RuntimeError):
    """Contains only labels authored in this file, never upstream exception text."""


@contextlib.contextmanager
def checking(label):
    try:
        yield
    except SmokeFailure:
        raise
    except Exception as error:  # noqa: BLE001 - upstream error text must remain private
        # Fixed categories aid diagnosis without exposing messages, module names,
        # paths, tokens, config values or arbitrary upstream exception classes.
        categories = {
            ModuleNotFoundError: "missing module",
            ImportError: "import error",
            PermissionError: "permission denied",
            FileNotFoundError: "missing file",
            TypeError: "type error",
            AttributeError: "attribute error",
        }
        category = categories.get(type(error), "runtime error")
        raise SmokeFailure(f"{label} ({category})") from None


def require(condition, label):
    if not condition:
        raise SmokeFailure(label)


def request(path, key=None):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    req = urllib.request.Request(BASE_URL + path, headers=headers, method="GET")
    # Loopback must never use an inherited proxy or follow a remote redirect.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(req, timeout=10)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        raw = response.read(MAX_BODY + 1)
        require(len(raw) <= MAX_BODY, "response body limit")
        return response.code, json.loads(raw)


def check_http(key):
    status, _ = request("/health")
    require(status == 200, "health")
    for endpoint in ("/v1/capabilities", "/v1/toolsets"):
        for credential in (None, "ai-team-ci-deliberately-invalid"):
            status, _ = request(endpoint, credential)
            require(status == 401, "unauthorized request must return 401")
    status, capabilities = request("/v1/capabilities", key)
    require(status == 200, "authenticated capabilities")
    require(capabilities.get("object") == "hermes.api_server.capabilities", "capabilities object")
    require(capabilities.get("platform") == "hermes-agent", "capabilities platform")
    require(capabilities.get("auth") == {"type": "bearer", "required": True}, "bearer required")
    require(capabilities.get("runtime", {}).get("mode") == "server_agent", "runtime mode")
    require(capabilities.get("features", {}).get("run_submission") is True, "run capability")
    require(
        capabilities.get("endpoints", {}).get("toolsets")
        == {"method": "GET", "path": "/v1/toolsets"},
        "toolsets endpoint contract",
    )
    status, inventory = request("/v1/toolsets", key)
    require(status == 200, "authenticated toolsets")
    require(inventory.get("object") == "list", "toolsets object")
    require(inventory.get("platform") == "api_server", "toolsets platform")
    entries = inventory.get("data")
    require(isinstance(entries, list) and bool(entries), "nonempty tool inventory")
    for item in entries:
        require(isinstance(item, dict), "tool inventory entry")
        require(isinstance(item.get("name"), str), "toolset name")
        require(item.get("enabled") is False, "all REST toolsets disabled")
        require(isinstance(item.get("tools"), list), "concrete tools contract")


def check_policy():
    from healthcheck import validate_policy
    from hermes_cli.config import load_config
    from hermes_cli.tools_config import _get_platform_tools

    config = load_config()
    effective = _get_platform_tools(config, "api_server", include_default_mcp_servers=True)
    require(validate_policy(config, effective), "effective policy including MCP")


def check_profiles(home, write):
    with checking("profiles: official YAML import"):
        from hermes_yaml import safe_load
    with checking("profiles: official discovery import"):
        from hermes_cli.profiles import list_profiles
    with checking("profiles: mounted provisioner import"):
        from hermes_profiles import POLICY, definitions, provision

    manifest = Path("/opt/ai-team/team.yaml")
    with checking("profiles: manifest validation"):
        expected = definitions(manifest)
    if write:
        with checking("profiles: initial provisioning"):
            require(set(provision(home, manifest)) == set(expected), "seven fresh profiles")
    with checking("profiles: idempotence"):
        require(provision(home, manifest) == [], "profile provisioning idempotence")
    with checking("profiles: official discovery call"):
        names = {item.name for item in list_profiles(lazy_skill_count=True)}
    require(set(expected) <= names, "official profile discovery")
    for name, entry in expected.items():
        profile = home / "profiles" / name
        with checking("profiles: persisted config read"):
            actual = safe_load((profile / "config.yaml").read_text(encoding="utf-8"))
            require(actual == POLICY, "persisted profile tool policy")
        with checking("profiles: persisted instructions read"):
            require(entry["instructions"] in (profile / "SOUL.md").read_text(encoding="utf-8"),
                    "persisted profile instructions")


def check_persistence(home, probe_id, write):
    from hermes_state import SessionDB

    # Never open or mutate the gateway's state.db. This file belongs only to this CI run.
    path = home / f"ai-team-ci-{probe_id}.sqlite3"
    require(not path.is_symlink(), "CI database must not be a symlink")
    require(path.exists() != write, "fresh write or existing check database required")
    database = SessionDB(db_path=path)
    try:
        if write:
            database.create_session(probe_id, source="ai_team_ci")
            database.append_message(probe_id, role="user", content=PROBE_CONTENT)
        session = database.get_session(probe_id)
        messages = database.get_messages(probe_id)
        require(session is not None and session["source"] == "ai_team_ci", "persisted session")
        require(len(messages) == 1 and messages[0]["role"] == "user"
                and messages[0]["content"] == PROBE_CONTENT, "persisted synthetic message")
    finally:
        database.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    phase = parser.add_mutually_exclusive_group(required=True)
    phase.add_argument("--write", action="store_true")
    phase.add_argument("--check", action="store_true")
    parser.add_argument("--probe-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9]+-[0-9]+", args.probe_id):
        parser.error("probe-id must contain only run ID and attempt")

    # Imports from the installed image, plus the explicitly mounted local scripts.
    sys.path.insert(0, "/opt/hermes")
    sys.path.insert(0, "/opt/ai-team")
    logging.disable(logging.CRITICAL)
    label = "preconditions"
    try:
        key = os.environ.get("API_SERVER_KEY", "")
        require(len(key) >= 32, "ephemeral key required")
        require(os.environ.get("HERMES_HOME") == "/opt/data", "container home")
        require(os.geteuid() != 0, "probe must use the unprivileged hermes user")
        home = Path("/opt/data")
        # Upstream imports may print provider/config diagnostics. Never publish raw output.
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            label = "HTTP authentication and official capability/toolset contracts"
            check_http(key)
            label = "effective tool policy including default MCP"
            check_policy()
            label = "official native profile discovery and persistence"
            check_profiles(home, args.write)
            label = "official SessionDB synthetic persistence"
            check_persistence(home, args.probe_id, args.write)
    except SmokeFailure as error:
        print(f"Hermes runtime smoke failed: {error}", file=sys.stderr)
        return 1
    except Exception:  # noqa: BLE001 - never print raw errors, config, key or provider state
        print(f"Hermes runtime smoke failed: {label}", file=sys.stderr)
        return 1
    print(f"Hermes runtime smoke {'write' if args.write else 'check'} passed: "
          "auth, capabilities, text-only policy, seven profiles, synthetic SessionDB.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
