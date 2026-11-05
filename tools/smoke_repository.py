"""Opt-in live repository homologation: own executor + App + Git + Docker; no publication."""

import argparse
import json
import secrets
import subprocess
import uuid

from ai_team.auth import create_owner
from ai_team.codex_provider import CodexProvider
from ai_team.config import ROOT, Settings
from ai_team.db import Database
from ai_team.hermes import HermesClient, HermesProvider
from ai_team.main import create_app
from ai_team.worker import Worker
from fastapi.testclient import TestClient


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--real", action="store_true", help="Autoriza até seis chamadas reais"
    )
    parser.add_argument("--max-tokens", type=int, default=50000)
    parser.add_argument("--executor", choices=["codex", "hermes"], default="codex")
    args = parser.parse_args(argv)
    if not args.real:
        parser.error("Use --real para autorizar consumo de até seis chamadas próprias")
    if not 16000 <= args.max_tokens <= 100000:
        parser.error("O orçamento deve ficar entre 16000 e 100000 tokens")
    return args


def provider_for(executor, settings):
    return HermesProvider(HermesClient(settings)) if executor == "hermes" else CodexProvider()


def main():
    args = parse_args()
    base = Settings()
    provider = provider_for(args.executor, base)
    if not provider.ready():
        raise SystemExit(f"Executor próprio {args.executor} indisponível.")
    base_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip()
    db_path = ROOT / ".data" / f"v06-{args.executor}-smoke-{uuid.uuid4()}.db"
    settings = base.model_copy(update={"database_url": f"sqlite:///{db_path}", "environment": "test"})
    database = Database(settings)
    database.initialize()
    password = secrets.token_urlsafe(24)
    with database.session() as db:
        create_owner(db, "smoke", password)
    with TestClient(
        create_app(settings, database), headers={"origin": settings.public_origin}
    ) as client:
        assert client.post(
            "/auth/login", json={"username": "smoke", "password": password}
        ).is_success
        project = client.post(
            "/projects", json={"name": "V06 real budget", "mode": "automatic"}
        ).json()
        request = {
            "project_id": project["id"],
            "executor": args.executor,
            "consent": True,
            "prompt": (
                "Melhore execution_limits.py preservando remaining_tokens, MAX_CALLS e MAX_TOKENS. "
                "Adicione summarize_usage(input_tokens, output_tokens, limit=MAX_TOKENS) que retorna "
                "dict com used (soma), remaining (nunca negativo) e exhausted (used>=limit). "
                "Rejeite bool, valores não inteiros, negativos e limite menor que 1 com ValueError. "
                "DEV altera somente execution_limits.py; DESIGNER cria execution_guide.md em "
                "português com exemplos. QA cria test_execution_limits.py com unittest cobrindo "
                "comportamento, limites e erros. Fonte é módulo isolado import execution_limits, "
                "não import ai_team. Nenhuma dependência externa, rede ou mudança em outros arquivos."
            ),
            "policy": {
                "base_sha": base_sha,
                "max_tokens": args.max_tokens,
                "base_branch": branch,
                "directory": "services/api/ai_team",
                "read_paths": ["execution_limits.py"],
                "write_paths": [
                    "execution_limits.py",
                    "test_execution_limits.py",
                    "execution_guide.md",
                ],
            },
        }
        response = client.post("/repository-runs", json=request)
        assert response.status_code == 201, "Criação não autorizada"
        run_id = response.json()["run"]["id"]
        worker = Worker(database, settings, provider)
        for _ in range(8):
            view = client.get(f"/repository-runs/{run_id}").json()
            run = view["run"]
            print(
                json.dumps(
                    {
                        "run_id": run_id,
                        "stage": run["stage"],
                        "status": run["status"],
                        "calls": run["calls"],
                        "tokens": run["input_tokens"] + run["output_tokens"],
                    }
                ),
                flush=True,
            )
            if run["status"] == "awaiting_approval":
                # Explicit test-only approval, bound to this generated task's exact checkpoint.
                if run["stage"] == 6:
                    break
                assert (
                    client.post(
                        f"/repository-runs/{run_id}/decision",
                        json={
                            "digest": view["digest"],
                            "approve": True,
                        },
                    ).status_code
                    == 200
                )
            assert worker.once(), "Worker não admitiu tarefa"
            current = client.get(f"/repository-runs/{run_id}").json()
            if current["run"]["status"] in {"failed", "blocked", "cancelled"}:
                raise RuntimeError(
                    "Homologação interrompida: " + current["run"]["error"]
                )
        view = client.get(f"/repository-runs/{run_id}").json()
        state = view["state"]
        assert view["run"]["stage"] == 6 and view["run"]["calls"] == 6
        assert state["test_result"]["status"] == "passed", "Testes reais não passaram"
        assert (
            "summarize_usage" in state["diff"]
            and state["proposal"]["published"] is False
        )
        assert client.get(f"/repository-runs/{run_id}/artifacts").status_code == 200
        artifact = ROOT / "artifacts" / f"v06-repository-{args.executor}-smoke.json"
        artifact.parent.mkdir(exist_ok=True)
        artifact.write_text(
            json.dumps(
                {
                    "kind": f"live-{args.executor}-github-read-docker",
                    "view": view,
                    "database": str(db_path),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": "passed",
                    "run_id": run_id,
                    "test_result": state["test_result"]["status"],
                    "published": False,
                    "evidence": str(artifact),
                }
            ),
            flush=True,
        )
    database.engine.dispose()


if __name__ == "__main__":
    main()
