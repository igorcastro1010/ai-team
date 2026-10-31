"""Docker control stays in the worker. No host mount, secrets or model commands."""

import json
import os
import re
import subprocess
import threading
import time
import uuid

IMAGE = "python@sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159"
OUTPUT_LIMIT = 32768
RUNNER = """
import json, os, sys, unittest
fd, nonce = int(sys.argv[1]), sys.argv[2]
suite = unittest.TestLoader().discover('/work', pattern='test_*.py')
if suite.countTestCases() == 0:
    print('Nenhum teste encontrado.', flush=True)
    sys.exit(3)
result = unittest.TextTestRunner(verbosity=2).run(suite)
os.write(fd, json.dumps({'nonce': nonce, 'tests': result.testsRun,
                        'successful': result.wasSuccessful()}).encode())
sys.exit(0 if result.wasSuccessful() else 1)
"""
HARNESS = """
import json, os, pathlib, secrets, subprocess, sys
payload = json.load(sys.stdin)
for entry in payload['files']:
    pathlib.Path('/work', entry['path']).write_text(entry['content'], encoding='utf-8')
read_fd, write_fd = os.pipe()
nonce = secrets.token_hex(32)
child = subprocess.Popen([sys.executable, '-I', '-B', '-c', RUNNER, str(write_fd), nonce],
                         pass_fds=(write_fd,))
os.close(write_fd)
try:
    child.wait(timeout=28)
except subprocess.TimeoutExpired:
    child.kill()
    child.wait()
    sys.exit(124)
os.set_blocking(read_fd, False)
try:
    report = json.loads(os.read(read_fd, 4096))
    valid = report['nonce'] == nonce and type(report['tests']) is int and report['tests'] > 0
    passed = valid and report['successful'] is True and child.returncode == 0
except Exception:
    print('Suite nao confirmou conclusao normal.', flush=True)
    sys.exit(3 if child.returncode == 3 else 4)
sys.exit(0 if passed else 1)
"""
HARNESS = "RUNNER = " + repr(RUNNER) + "\n" + HARNESS


def valid_name(name):
    return bool(re.fullmatch(r"ai-team-test-[a-f0-9]{32}", name))


def sandbox_command(name):
    return [
        "docker",
        "run",
        "--rm",
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
        "timeout",
        "--signal=KILL",
        "30s",
        "python",
        "-I",
        "-B",
        "-c",
        HARNESS,
    ]


class PythonSandbox:
    max_time = 30
    image = IMAGE

    def __init__(self, time_limit=30):
        self.time_limit = min(max(time_limit, 1), self.max_time)

    def command(self, name):
        return sandbox_command(name)

    def validate_bundle(self, bundle):
        from .code_artifacts import CodeBundle

        return CodeBundle.model_validate(bundle.model_dump())

    @staticmethod
    def new_name():
        return "ai-team-test-" + uuid.uuid4().hex

    @staticmethod
    def cleanup(name):
        if not valid_name(name):
            raise RuntimeError("Identificação de sandbox inválida")
        # Inspect only our exact name AND scope label; remove by immutable Docker ID.
        try:
            found = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-a",
                    "--filter",
                    f"name=^{name}$",
                    "--filter",
                    "label=ai-team.scope",
                    "--format",
                    '{{.ID}}|{{.Label "ai-team.scope"}}',
                ],
                capture_output=True,
                timeout=5,
                check=False,
            )
            records = [line.split("|") for line in found.stdout.decode("ascii").splitlines()]
            ids = [record[0] for record in records]
            if (
                found.returncode != 0
                or len(ids) > 1
                or any(not re.fullmatch(r"[a-f0-9]{12,64}", cid) for cid in ids)
                or any(len(r) != 2 or r[1] not in {"python-test", "next-test"} for r in records)
            ):
                raise RuntimeError("Inventário do sandbox indisponível")
            if ids:
                removed = subprocess.run(
                    ["docker", "rm", "-f", ids[0]],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    check=False,
                )
                if removed.returncode != 0:
                    remaining = subprocess.run(
                        [
                            "docker",
                            "ps",
                            "-aq",
                            "--filter",
                            f"name=^{name}$",
                            "--filter",
                            "label=ai-team.scope",
                        ],
                        capture_output=True,
                        timeout=5,
                        check=False,
                    )
                    if remaining.returncode != 0 or remaining.stdout.strip():
                        raise RuntimeError("Encerramento do sandbox não confirmado")
        except (OSError, subprocess.SubprocessError, UnicodeError):
            raise RuntimeError("Encerramento do sandbox não confirmado") from None

    def run(self, bundle, on_tick, *, name=None):
        # Revalidate even if called without the HTTP/schema boundary.
        bundle = self.validate_bundle(bundle)
        name = name or self.new_name()
        if not valid_name(name):
            raise RuntimeError("Identificação de sandbox inválida")
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
                self.command(name),
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
                status = (
                    "passed"
                    if process.returncode == 0
                    else "timeout"
                    if process.returncode in {124, 137}
                    else "failed"
                )
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
                "output": output.decode("utf-8", errors="replace")
                .encode("utf-8")[:OUTPUT_LIMIT]
                .decode("utf-8", errors="ignore"),
                "image": self.image,
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
                self.cleanup(name)
