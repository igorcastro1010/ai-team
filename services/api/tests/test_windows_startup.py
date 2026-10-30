import json
import shutil
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="PowerShell required for launcher checks")
HELPER = Path(__file__).resolve().parents[3] / "tools/start-helpers.ps1"


def invoke(script):
    helper_path = str(HELPER).replace(chr(39), chr(39) * 2)
    return subprocess.run(
        [
            POWERSHELL,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            f"$ErrorActionPreference='Stop'; . '{helper_path}'; {script}",
        ],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=30,
    )


@pytest.fixture
def health_server():
    state = {"status": "ok", "version": "0.5.0"}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(state).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    yield server.server_port, state
    server.shutdown()
    server.server_close()
    worker.join(timeout=5)


def test_wait_accepts_only_healthy_expected_api(health_server):
    port, state = health_server
    result = invoke(
        f"Wait-AiTeamApi -ProcessId $PID -HealthUrl 'http://127.0.0.1:{port}/health' "
        "-ExpectedVersion '0.5.0' -TimeoutSeconds 1"
    )
    assert result.returncode == 0, result.stderr
    state["version"] = "different-private-value"
    failed = invoke(
        f"Wait-AiTeamApi -ProcessId $PID -HealthUrl 'http://127.0.0.1:{port}/health' "
        "-ExpectedVersion '0.5.0' -TimeoutSeconds 1"
    )
    assert failed.returncode != 0
    assert "different-private-value" not in failed.stdout + failed.stderr


def test_dead_api_and_occupied_port_abort_startup(health_server):
    port, _ = health_server
    assert invoke(f"Assert-AiTeamPortAvailable -Port {port}").returncode != 0
    assert (
        invoke(
            "Wait-AiTeamApi -ProcessId 2147483647 -ExpectedVersion '0.5.0' -TimeoutSeconds 1"
        ).returncode
        != 0
    )


def test_unavailable_api_fails_before_frontend_can_start(health_server):
    port, state = health_server
    state["status"] = "private-error"
    result = invoke(
        f"Wait-AiTeamApi -ProcessId $PID -HealthUrl 'http://127.0.0.1:{port}/health' "
        "-ExpectedVersion '0.5.0' -TimeoutSeconds 1; Write-Output 'frontend-started'"
    )
    assert result.returncode != 0
    assert "frontend-started" not in result.stdout
    assert "private-error" not in result.stdout + result.stderr


def test_child_that_exits_after_readiness_is_rejected_before_frontend():
    window = "-WindowStyle Hidden " if sys.platform == "win32" else ""
    result = invoke(
        "$child = Start-Process -FilePath (Get-Process -Id $PID).Path "
        f"{window}-ArgumentList '-NoProfile', '-NonInteractive', '-Command', 'exit 0' "
        "-PassThru -Wait; "
        "Assert-AiTeamChildRunning -Process $child -Name 'API'; Write-Output 'frontend-started'"
    )
    assert result.returncode != 0
    assert "frontend-started" not in result.stdout
