"""Docker control stays in the worker. No host mount, secrets or model commands."""

import json
import os
import subprocess
import threading
import time
import uuid

IMAGE = "python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159"
OUTPUT_LIMIT = 32768
HARNESS = """
import json, pathlib, subprocess, sys
payload = json.load(sys.stdin)
for entry in payload['files']:
    pathlib.Path('/work', entry['path']).write_text(entry['content'], encoding='utf-8')
import unittest
suite = unittest.TestLoader().discover('/work', pattern='test_*.py')
if suite.countTestCases() == 0:
    print('Nenhum teste encontrado.', flush=True)
    sys.exit(3)
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
"""


def sandbox_command(name):
    return [
        "docker",
        "run",
        "--name",
        name,
        "--label",
        "ai-team.scope=python-test",
        "--pull",
        "never",
        "--network",
        "none",
        "--user",
        "65532:65532",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--read-only",
        "--cpus",
        "1",
        "--memory",
        "256m",
        "--memory-swap",
        "256m",
        "--pids-limit",
        "64",
        "--ulimit",
        "nofile=128:128",
        "--init",
        "--log-driver",
        "none",
        "--tmpfs",
        "/work:rw,noexec,nosuid,size=16m,mode=1777",
        "--workdir",
        "/work",
        "-i",
        IMAGE,
        "python",
        "-I",
        "-B",
        "-c",
        HARNESS,
    ]


class PythonSandbox:
    def __init__(self, time_limit=30):
        self.time_limit = min(max(time_limit, 1), 30)

    def run(self, bundle, on_tick):
        # Revalidate even if called without the HTTP/schema boundary.
        from .code_artifacts import CodeBundle

        bundle = CodeBundle.model_validate(bundle.model_dump())
        name = "ai-team-test-" + uuid.uuid4().hex
        output = bytearray()
        exceeded = threading.Event()
        process = None
        status = "failed"
        # Do not pass provider credentials to the Docker CLI either.
        environment = {
            k: v
            for k, v in os.environ.items()
            if not k.startswith(
                ("AI_TEAM_", "OPENAI_", "CODEX_", "GH_", "GITHUB_", "VERCEL_", "SUPABASE_")
            )
        }
        try:
            on_tick()
            process = subprocess.Popen(
                sandbox_command(name),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=environment,
            )

            def drain():
                while chunk := os.read(process.stdout.fileno(), 4096):
                    room = OUTPUT_LIMIT - len(output)
                    output.extend(chunk[:room])
                    if len(chunk) > room:
                        exceeded.set()

            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            deadline = time.monotonic() + self.time_limit

            def feed():
                try:
                    process.stdin.write(json.dumps(bundle.model_dump()).encode("utf-8"))
                    process.stdin.close()
                except OSError:
                    pass  # Broken pipe is diagnosed by the process exit code.

            writer = threading.Thread(target=feed, daemon=True)
            writer.start()
            while process.poll() is None:
                on_tick()
                if exceeded.is_set() or time.monotonic() >= deadline:
                    status = "output_limit" if exceeded.is_set() else "timeout"
                    break
                time.sleep(0.1)
            else:
                status = "passed" if process.returncode == 0 else "failed"
            if status in {"timeout", "output_limit"}:
                process.kill()
            process.wait(timeout=5)
            reader.join(timeout=2)
            if exceeded.is_set():
                status = "output_limit"
            if process.returncode in {125, 126, 127}:
                raise RuntimeError("Sandbox indisponível; confira Docker e imagem fixada")
            return {
                "status": status,
                "exit_code": process.returncode,
                "output": output.decode("utf-8", errors="replace"),
                "image": IMAGE,
                "artifact_digest": bundle.digest,
            }
        except InterruptedError:
            raise
        except (OSError, subprocess.SubprocessError):
            raise RuntimeError("Falha de isolamento; nenhuma execução no host") from None
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                try:
                    removed = subprocess.run(
                        ["docker", "rm", "-f", name],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=8,
                        env=environment,
                        check=False,
                    )
                    if removed.returncode != 0:
                        remaining = subprocess.run(
                            ["docker", "ps", "-aq", "--filter", f"name=^{name}$"],
                            capture_output=True,
                            timeout=5,
                            env=environment,
                            check=False,
                        )
                        if remaining.returncode != 0 or remaining.stdout.strip():
                            raise RuntimeError("Encerramento do sandbox não confirmado")
                except (OSError, subprocess.SubprocessError):
                    raise RuntimeError(
                        "Não foi possível confirmar encerramento do sandbox"
                    ) from None
