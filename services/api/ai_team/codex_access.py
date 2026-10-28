"""Login próprio do executor; não lê nem copia a sessão do Codex Desktop."""

import argparse
import os
import shutil
import subprocess
from pathlib import Path


def executor_home() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    return base / "AI-Team" / "codex"


def child_environment(home: Path) -> dict[str, str]:
    allowed = {
        "PATH",
        "SYSTEMROOT",
        "WINDIR",
        "USERPROFILE",
        "HOME",
        "LOCALAPPDATA",
        "APPDATA",
        "TEMP",
        "TMP",
        "COMSPEC",
        "PATHEXT",
        "LANG",
        "LC_ALL",
    }
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env["CODEX_HOME"] = str(home)
    return env


def codex_command(binary: str, arguments: list[str]) -> list[str]:
    return [binary, "-c", 'cli_auth_credentials_store="keyring"', *arguments]


def main():
    parser = argparse.ArgumentParser(description="Credenciais isoladas do executor AI TEAM")
    parser.add_argument("command", choices=["login", "status"])
    args = parser.parse_args()
    binary = shutil.which("codex")
    if not binary or Path(binary).suffix.lower() in {".cmd", ".bat", ".ps1"}:
        parser.exit(
            1, "Codex nativo não encontrado. Instale o CLI oficial e adicione o EXE ao PATH.\n"
        )
    home = executor_home()
    # No token files in the OneDrive checkout. Credential storage is OS keyring, without fallback.
    home.mkdir(parents=True, exist_ok=True)
    arguments = ["login", "--device-auth"] if args.command == "login" else ["login", "status"]
    result = subprocess.run(
        codex_command(binary, arguments),
        env=child_environment(home),
        cwd=home,
        check=False,
    )
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
