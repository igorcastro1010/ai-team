"""Adapter restrito do CLI oficial; sem shell, plugins ou credenciais no contexto do modelo."""

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .codex_access import child_environment, executor_home
from .orchestration import Draft, DraftContent


def execution_command(command: list[str], directory: Path) -> list[str]:
    options = [
        'cli_auth_credentials_store="keyring"',
        'default_permissions="ai-team"',
        'permissions.ai-team.filesystem={":root"="deny",":minimal"="read",'
        '":workspace_roots"="read"}',
        "permissions.ai-team.network.enabled=false",
        'approval_policy="never"',
        'web_search="disabled"',
        "skills.bundled.enabled=false",
        "skills.include_instructions=false",
        "project_doc_max_bytes=0",
        "features.shell_tool=false",
        "features.unified_exec=false",
        "features.multi_agent=false",
        "features.multi_agent_v2=false",
        "features.apps=false",
        "features.plugins=false",
        "features.code_mode=false",
        "features.code_mode_host=false",
    ]
    argv = [
        *command,
        "exec",
        "--strict-config",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--skip-git-repo-check",
        "--json",
        "--color",
        "never",
        "--cd",
        str(directory),
        "--output-schema",
        str(directory / "schema.json"),
        "-o",
        str(directory / "result.json"),
    ]
    for option in options:
        argv.extend(["-c", option])
    return [*argv, "-"]


def stop_process(process):
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill.exe", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                check=False,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=8)


class CodexProvider:
    def __init__(self, command=None, home=None, time_limit=120):
        binary = shutil.which("codex")
        if (
            command is None
            and binary
            and Path(binary).suffix.lower() not in {".cmd", ".bat", ".ps1"}
        ):
            command = [binary]
        self.command = command
        self.home = home or executor_home()
        self.time_limit = min(time_limit, 120)

    def ready(self):
        if not self.command:
            return False
        self.home.mkdir(parents=True, exist_ok=True)
        try:
            result = subprocess.run(
                [*self.command, "-c", 'cli_auth_credentials_store="keyring"', "login", "status"],
                env=child_environment(self.home),
                cwd=self.home,
                timeout=10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def generate(self, role, instructions, context, on_tick):
        if not self.command:
            raise RuntimeError("Codex não encontrado")
        jobs = self.home.parent / "jobs"
        jobs.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="draft-", dir=jobs) as temporary:
            directory = Path(temporary)
            (directory / "schema.json").write_text(
                json.dumps(DraftContent.model_json_schema()), encoding="utf-8"
            )
            prompt = json.dumps(
                {
                    "role": role,
                    "instructions": instructions,
                    "context": context,
                    "response_size": "Entregável objetivo, até 600 palavras.",
                },
                ensure_ascii=False,
            )
            stdout_path, stderr_path = directory / "events.jsonl", directory / "stderr.txt"
            stdin_path = directory / "request.json"
            stdin_path.write_text(prompt, encoding="utf-8")
            with (
                stdout_path.open("wb") as stdout,
                stderr_path.open("wb") as stderr,
                stdin_path.open("rb") as stdin,
            ):
                process = subprocess.Popen(
                    execution_command(self.command, directory),
                    env=child_environment(self.home),
                    cwd=directory,
                    stdin=stdin,
                    stdout=stdout,
                    stderr=stderr,
                    start_new_session=os.name != "nt",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                try:
                    deadline = time.monotonic() + self.time_limit
                    while process.poll() is None:
                        on_tick()
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Tempo máximo da chamada excedido")
                        if stdout_path.stat().st_size + stderr_path.stat().st_size > 2_000_000:
                            raise RuntimeError("Saída do executor excedeu o limite")
                        time.sleep(0.2)
                    if process.returncode:
                        raise RuntimeError(
                            "Codex encerrou com erro; detalhes privados não propagados"
                        )
                finally:
                    stop_process(process)
            result_path = directory / "result.json"
            if not result_path.exists() or result_path.stat().st_size > 100_000:
                raise RuntimeError("Resposta ausente ou muito grande")
            content = DraftContent.model_validate_json(result_path.read_text(encoding="utf-8"))
            inputs, outputs, completed = 0, 0, False
            for line in stdout_path.read_text(encoding="utf-8").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") in {"turn.failed", "error"}:
                    raise RuntimeError("Falha reportada pelo Codex")
                if event.get("type") == "turn.completed":
                    completed = True
                    usage = event.get("usage") or {}
                    inputs += max(0, int(usage.get("input_tokens", 0)))
                    outputs += max(0, int(usage.get("output_tokens", 0)))
            if not completed:
                raise RuntimeError("Codex não confirmou a conclusão")
            return Draft(**content.model_dump(), input_tokens=inputs, output_tokens=outputs)
