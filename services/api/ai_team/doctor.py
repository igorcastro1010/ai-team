"""Diagnóstico local somente leitura; não acessa cofres, .env ou sessões."""

import argparse
import importlib.util
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def windows_restart_pending():
    try:
        import winreg

        paths = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired",
        )
        for path in paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path):
                    return True
            except FileNotFoundError:
                continue
        return False
    except (ImportError, OSError):
        return None


def diagnose(
    root=ROOT,
    *,
    runner=subprocess.run,
    which=shutil.which,
    system=None,
    dependencies_ready=None,
    restart_pending=None,
):
    checks = []

    def add(name, ready, message):
        checks.append({"id": name, "status": "ready" if ready else "blocked", "message": message})
        return ready

    def command(name, *arguments):
        executable = which(name)
        if not executable:
            return None
        try:
            result = runner(
                [executable, *arguments],
                capture_output=True,
                timeout=5,
                shell=False,
                text=True,
                errors="replace",
            )
            return result.stdout.replace("\x00", "").strip() if result.returncode == 0 else None
        except Exception:
            # Never serialize subprocess exceptions, stdout/stderr, command paths or environment.
            return None

    python = add("python", sys.version_info[:2] == (3, 12), "Python 3.12 requerido.")
    if dependencies_ready is None:
        dependencies_ready = all(
            importlib.util.find_spec(name) is not None
            for name in (
                "fastapi",
                "sqlalchemy",
                "langgraph",
                "keyring",
                "httpx",
                "jwt",
            )
        )
    dependencies = add(
        "dependencies",
        dependencies_ready,
        "Dependências Python: execute tools/setup.ps1 se indisponíveis.",
    )
    node_version = command("node", "--version")
    match = re.fullmatch(r"v(\d+)\.\d+\.\d+", node_version or "")
    node = add("node", bool(match and int(match[1]) in (22, 24)), "Node.js 22 ou 24 requerido.")
    web = add(
        "web_dependencies",
        (Path(root) / "node_modules/next/package.json").is_file(),
        "Dependências do painel: npm ci se indisponíveis.",
    )
    base_ready = python and dependencies and node and web

    windows = (system or platform.system()) == "Windows"
    wsl = True
    restart_ready = True
    if windows:
        if restart_pending is None:
            restart_pending = windows_restart_pending()
        restart_ready = add(
            "restart",
            restart_pending is False,
            "Sem reinício pendente detectado."
            if restart_pending is False
            else "Reinício do Windows pendente ou estado não confirmado. Reinicie quando puder.",
        )
        version = command("wsl", "--version")
        match = re.search(r"(\d+)\.(\d+)\.(\d+)", version or "")
        modern = bool(match and tuple(map(int, match.groups())) >= (2, 1, 5))
        wsl = add(
            "wsl",
            modern and command("wsl", "--status") is not None,
            "CLI WSL 2.1.5+ requerido; a engine Docker Linux confirma a execução real.",
        )
    docker = add(
        "docker",
        command("docker", "info", "--format", "{{.OSType}}") == "linux",
        "Docker: instale/abra Docker Desktop e aguarde a engine Linux iniciar.",
    )
    compose_output = command("docker", "compose", "version", "--short")
    compose = add(
        "compose",
        bool(re.fullmatch(r"v?\d+\.\d+\.\d+(?:[-+][\w.-]+)?", compose_output or "")),
        "Docker Compose plugin requerido.",
    )
    return {
        "base_ready": bool(base_ready),
        "hermes_ready": bool(base_ready and restart_ready and wsl and docker and compose),
        "checks": checks,
        "note": "Pré-requisitos apenas: não comprova login, inferência, Telegram ou produção.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-hermes", action="store_true")
    args = parser.parse_args()
    report = diagnose()
    if args.json:
        print(json.dumps(report, ensure_ascii=True))
    else:
        for check in report["checks"]:
            print(f"{check['id']}: {check['status']} - {check['message']}")
        print(report["note"])
    ready = report["hermes_ready"] if args.require_hermes else report["base_ready"]
    raise SystemExit(0 if ready else 2)


if __name__ == "__main__":
    main()
