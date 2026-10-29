"""Homologação opt-in. Cria branch/documento/issue/PR somente no ai-team, sem merge."""

import argparse
import json
import os
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

from ai_team.auth import create_owner
from ai_team.config import Settings
from ai_team.db import Database
from ai_team.main import create_app
from fastapi.testclient import TestClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real", action="store_true", help="Autoriza quatro propostas sintéticas"
    )
    args = parser.parse_args()
    if not args.real:
        parser.exit(1, "Use --real para criar recursos reais no repositório ai-team.\n")
    root = Path(__file__).resolve().parents[1]
    marker = secrets.token_hex(5)
    branch = f"codex/ai-team/smoke-{marker}"
    evidence = {"kind": "real-github-app-smoke", "actions": []}
    with tempfile.TemporaryDirectory(prefix="ai-team-github-") as folder:
        settings = Settings(
            database_url=f"sqlite:///{Path(folder) / 'smoke.db'}", environment="test"
        )
        database = Database(settings)
        database.initialize()
        password = secrets.token_urlsafe(24)
        with database.session() as db:
            create_owner(db, "synthetic", password)
        try:
            with TestClient(
                create_app(settings, database),
                headers={"origin": settings.public_origin},
            ) as client:
                assert (
                    client.post(
                        "/auth/login",
                        json={"username": "synthetic", "password": password},
                    ).status_code
                    == 200
                )
                response = client.post("/github/verify")
                if response.status_code != 200:
                    raise RuntimeError("Homologação de leitura falhou")
                connection = response.json()
                evidence["connection"] = connection
                project = client.post(
                    "/projects", json={"name": "Homologação GitHub sintética"}
                ).json()
                plan = [
                    {
                        "operation": "branch",
                        "title": "Branch de homologação AI TEAM",
                        "branch": branch,
                        "expected_sha": connection["head_sha"],
                    },
                    {
                        "operation": "commit",
                        "title": "docs: validate supervised GitHub integration",
                        "branch": branch,
                        "expected_sha": connection["head_sha"],
                        "path": f"docs/agent-output/github-smoke-{marker}.md",
                        "content": "# Homologação AI TEAM\n\nDocumento sintético aprovado pelo fluxo "
                        "API → fila → worker → GitHub App. Sem merge ou deploy.\n",
                    },
                    {
                        "operation": "issue",
                        "title": f"[AI TEAM smoke] Integração {marker}",
                        "body": "Registro sintético da homologação supervisionada da GitHub App. "
                        "Somente ai-team. Não solicita alterações em outros projetos.",
                    },
                    {
                        "operation": "pull_request",
                        "title": f"docs: GitHub App smoke {marker}",
                        "branch": branch,
                        "draft": False,
                        "body": "Homologação sintética de branch, commit e PR pelo executor próprio. "
                        "Somente um documento de evidência. Nenhum merge ou deploy autorizado.",
                    },
                ]
                for item in plan:
                    if item["operation"] == "pull_request":
                        item["expected_sha"] = evidence["actions"][1]["result"]["sha"]
                    response = client.post(
                        "/github/proposals", json={"project_id": project["id"], **item}
                    )
                    assert response.status_code == 201, (
                        "Proposta recusada pela política"
                    )
                    action = response.json()
                    approved = client.post(
                        f"/github/proposals/{action['id']}/decision",
                        json={"digest": action["digest"], "approve": True},
                    )
                    assert approved.status_code == 200
                    environment = {
                        **os.environ,
                        "AI_TEAM_DATABASE_URL": settings.database_url,
                        "AI_TEAM_ENVIRONMENT": "test",
                    }
                    subprocess.run(
                        [sys.executable, "-m", "ai_team.worker", "--once"],
                        cwd=root,
                        env=environment,
                        timeout=240,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    current = next(
                        row
                        for row in client.get("/github").json()["actions"]
                        if row["id"] == action["id"]
                    )
                    evidence["actions"].append(
                        {
                            key: current[key]
                            for key in ["id", "status", "result", "error"]
                        }
                    )
                    output = root / "artifacts" / "github-smoke.json"
                    output.parent.mkdir(exist_ok=True)
                    output.write_text(
                        json.dumps(evidence, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    if current["status"] != "succeeded":
                        raise RuntimeError(
                            "Ação não concluída. Consulte evidência; não repita automaticamente"
                        )
                    print(item["operation"] + ": succeeded", flush=True)
        finally:
            database.engine.dispose()


if __name__ == "__main__":
    main()
