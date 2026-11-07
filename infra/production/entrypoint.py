"""Read a fixed secret allowlist and exec a fixed service command, without a shell."""

import os
import stat
import sys
from pathlib import Path

SECRET_NAMES = (
    "database_url", "gemini_api_key", "google_read_token", "gemini_project_id",
    "gemini_project_number",
)
COMMANDS = {
    ("python", "-m", "uvicorn", "ai_team.main:app", "--host", "0.0.0.0", "--port", "8000"),
    ("python", "-m", "ai_team.worker"),
    ("python", "-m", "ai_team.scheduler"),
    ("python", "-m", "ai_team.video_worker"),
    ("python", "-m", "ai_team.cli", "init-db"),
    ("python", "-m", "ai_team.cli", "create-owner"),
}


def validate_command(command):
    if tuple(command) not in COMMANDS:
        raise ValueError("Unsupported service command")


def load_secrets(directory=Path("/run/secrets"), environment=None):
    environment = dict(os.environ if environment is None else environment)
    for name in SECRET_NAMES:
        path = directory / name
        if not path.exists() and not path.is_symlink():
            if name == "database_url":
                raise ValueError("Required database secret missing")
            continue
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1 or details.st_size > 16384:
            raise ValueError("Invalid secret file")
        value = path.read_text(encoding="utf-8").strip()
        if not value or "\x00" in value or "\n" in value or "\r" in value:
            raise ValueError("Invalid secret value")
        environment[f"AI_TEAM_{name.upper()}"] = value
    return environment


def main():
    try:
        command = sys.argv[1:]
        validate_command(command)
        environment = load_secrets()
    except (OSError, UnicodeError, ValueError):
        print("Production configuration rejected.", file=sys.stderr)
        return 1
    os.execvpe(command[0], command, environment)


if __name__ == "__main__":
    raise SystemExit(main())
