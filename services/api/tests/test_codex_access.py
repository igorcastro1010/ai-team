import os
from pathlib import Path

from ai_team.codex_access import child_environment, codex_command, executor_home


def test_codex_context_is_separate_and_does_not_inherit_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-not-for-executor")
    monkeypatch.setenv("GITHUB_TOKEN", "secret-not-for-executor")
    monkeypatch.setenv("CODEX_HOME", "C:/existing/session")
    home = executor_home()
    assert home != Path(os.environ["CODEX_HOME"])
    env = child_environment(home)
    assert env["CODEX_HOME"] == str(home)
    assert "OPENAI_API_KEY" not in env and "GITHUB_TOKEN" not in env
    assert "AI_TEAM_DATABASE_URL" not in env


def test_login_enforces_os_keyring_without_plaintext_fallback():
    command = codex_command("codex.exe", ["login", "--device-auth"])
    assert command == [
        "codex.exe",
        "-c",
        'cli_auth_credentials_store="keyring"',
        "login",
        "--device-auth",
    ]
