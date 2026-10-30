"""Opt-in live gateway validation; disposable database, no existing project access."""

import argparse
import json
import secrets
import tempfile
from pathlib import Path

from ai_team.auth import create_owner
from ai_team.config import ROOT, Settings
from ai_team.db import Database
from ai_team.hermes import HermesClient, HermesProvider
from ai_team.main import create_app
from ai_team.worker import Worker
from fastapi.testclient import TestClient


def main():
    parser = argparse.ArgumentParser(
        description="Homologar Hermes real em projeto sintético"
    )
    parser.add_argument(
        "--real", action="store_true", help="Autoriza até 5 chamadas ao provedor"
    )
    args = parser.parse_args()
    if not args.real:
        parser.error("Use --real para autorizar consumo da sua conta Hermes")
    base = Settings()
    provider = HermesProvider(HermesClient(base))
    if not provider.ready():
        parser.exit(
            2, "Hermes não alcançável ou política de ferramentas incompatível.\n"
        )
    data = ROOT / ".data"
    data.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hermes-smoke-", dir=data) as temporary:
        settings = base.model_copy(
            update={
                "database_url": f"sqlite:///{Path(temporary) / 'smoke.db'}",
                "environment": "test",
            }
        )
        database = Database(settings)
        database.initialize()
        password = secrets.token_urlsafe(24)
        with database.session() as session:
            create_owner(session, "hermes-smoke", password)
        try:
            with TestClient(
                create_app(settings, database),
                headers={
                    "origin": settings.public_origin,
                },
            ) as client:
                assert (
                    client.post(
                        "/auth/login",
                        json={
                            "username": "hermes-smoke",
                            "password": password,
                        },
                    ).status_code
                    == 200
                )
                project = client.post(
                    "/projects",
                    json={
                        "name": "Homologação Hermes sintética",
                        "mode": "supervised",
                    },
                ).json()
                run = client.post(
                    "/runs",
                    json={
                        "project_id": project["id"],
                        "executor": "hermes",
                        "consent": True,
                        "prompt": "Proponha uma biblioteca comunitária fictícia. Até 80 palavras "
                        "por parecer. CEO: delegue duas tarefas. Não use ferramentas.",
                    },
                ).json()
                for index in range(5):
                    # A fresh worker per checkpoint tests SQL persistence across instances.
                    Worker(database, settings, provider).once()
                    current = client.get(f"/runs/{run['id']}").json()
                    assert current["stage"] == index + 1, "Etapa Hermes não concluída"
                    if index == 0:
                        assert current["status"] == "awaiting_approval"
                        assert (
                            client.post(
                                f"/runs/{run['id']}/decision",
                                json={
                                    "stage": 1,
                                    "approve": True,
                                },
                            ).status_code
                            == 200
                        )
                assert current["status"] == "completed"
                assert current["executor"] == "hermes"
                report = {
                    "status": "passed",
                    "executor": "hermes",
                    "calls": current["calls"],
                    "input_tokens": current["input_tokens"],
                    "output_tokens": current["output_tokens"],
                    "stages": [step["agent"] for step in current["steps"]],
                    "note": "Fluxo textual real via API autenticada e cinco workers. "
                    "Não comprova Bot Mode, subagentes nativos, Telegram ou Docker restart.",
                }
                artifacts = ROOT / "artifacts"
                artifacts.mkdir(exist_ok=True)
                (artifacts / "hermes-smoke.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                print(
                    "PASS: Hermes real; cinco etapas textuais e aprovação persistida."
                )
        except Exception:  # noqa: BLE001 - never print provider errors containing credentials
            parser.exit(
                1, "Homologação não concluída. Confira runtime, política e provedor.\n"
            )
        finally:
            database.engine.dispose()


if __name__ == "__main__":
    main()
