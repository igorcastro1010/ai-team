"""Homologação real e opt-in, com projeto sintético e banco temporário exclusivo."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from ai_team.auth import create_owner
from ai_team.codex_provider import CodexProvider
from ai_team.config import ROOT, Settings
from ai_team.db import Database
from ai_team.main import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="Consente até 5 chamadas reais do Codex")
    args = parser.parse_args()
    if not args.real:
        parser.error("Use --real para autorizar consumo real da conta no teste sintético")
    if not CodexProvider().ready():
        parser.exit(1, "Login próprio do Codex indisponível.\n")
    data = ROOT / ".data"
    data.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="smoke-", dir=data) as temporary:
        settings = Settings(database_url=f"sqlite:///{Path(temporary) / 'smoke.db'}",
                            environment="test")
        database = Database(settings)
        database.initialize()
        password = secrets.token_urlsafe(24)
        with database.session() as session:
            create_owner(session, "smoke", password)
        environment = {**os.environ, "AI_TEAM_DATABASE_URL": settings.database_url,
                       "AI_TEAM_ENVIRONMENT": "test"}
        try:
            with TestClient(create_app(settings, database),
                            headers={"origin": settings.public_origin}) as client:
                assert client.post("/auth/login", json={"username": "smoke", "password": password}).status_code == 200
                project = client.post("/projects", json={"name": "Homologação sintética", "mode": "supervised"}).json()
                run = client.post("/runs", json={
                    "project_id": project["id"], "consent": True,
                    "prompt": "Proponha uma página fictícia para uma biblioteca comunitária. "
                    "Cada parecer deve ter no máximo 100 palavras. CEO: delegue só duas tarefas. "
                    "Não leia arquivos nem use ferramentas; gere apenas propostas e revisão textual.",
                }).json()
                for index in range(5):
                    result = subprocess.run(
                        [sys.executable, "-m", "ai_team.worker", "--once"], env=environment,
                        cwd=ROOT, capture_output=True, text=True, timeout=145,
                    )
                    assert result.returncode == 0, "Worker encerrou inesperadamente"
                    current = client.get(f"/runs/{run['id']}").json()
                    print(json.dumps({"stage": current["stage"], "status": current["status"],
                                      "calls": current["calls"], "tokens": current["input_tokens"] + current["output_tokens"]}), flush=True)
                    assert current["stage"] == index + 1, current.get("error", "Etapa incompleta")
                    if index == 0:
                        assert current["status"] == "awaiting_approval"
                        assert current["steps"][0]["deliverable"]
                        # Test-only consent against this disposable, synthetic run.
                        assert client.post(f"/runs/{run['id']}/decision", json={"stage": 1, "approve": True}).status_code == 200
                assert current["status"] == "completed"
                report = {"status": "passed", "run": current,
                          "note": "API autenticada + 5 processos worker reais + Codex próprio + aprovação sintética. Nenhum projeto existente foi acessado."}
                artifacts = ROOT / "artifacts"
                artifacts.mkdir(exist_ok=True)
                (artifacts / "codex-smoke.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                print("PASS: fluxo real completo, sem repositórios ou ferramentas externas.", flush=True)
        finally:
            database.engine.dispose()


if __name__ == "__main__":
    main()
