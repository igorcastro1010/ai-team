"""Private probes: no external inference, command output or connection strings."""

import sys
import time
from pathlib import Path


def fresh_heartbeat(last_seen, *, now=None):
    now = time.time() if now is None else now
    return last_seen is not None and 0 <= now - last_seen <= 120


def process_running(module):
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            args = (entry / "cmdline").read_bytes().split(b"\x00")
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
        if b"-m" in args and module.encode() in args:
            return True
    return False


def check(service):
    from ai_team.config import Settings
    from ai_team.db import Database
    from ai_team.models import WorkerHeartbeat
    from sqlalchemy import func, select, text

    # Healthcheck processes don't inherit variables loaded by the service entrypoint.
    secret_path = Path("/run/secrets/database_url")
    if secret_path.is_symlink() or not secret_path.is_file():
        return False
    database = Database(Settings(database_url=secret_path.read_text(encoding="utf-8").strip()))
    try:
        with database.session() as session:
            session.execute(text("SELECT 1"))
            if service == "worker":
                if not process_running("ai_team.worker"):
                    return False
                return fresh_heartbeat(session.scalar(select(func.max(WorkerHeartbeat.last_seen))))
            if service in {"scheduler", "video_worker"}:
                return process_running(f"ai_team.{service}")
            if service == "api":
                import urllib.request

                with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as reply:
                    return reply.status == 200
            return False
    finally:
        database.engine.dispose()


def main(arguments=None):
    arguments = sys.argv[1:] if arguments is None else arguments
    try:
        return 0 if len(arguments) == 1 and check(arguments[0]) else 1
    except Exception:  # noqa: BLE001 - probes must never print database URLs or driver errors
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
