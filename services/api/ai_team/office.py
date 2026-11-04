"""Read-only office projection from existing persisted runs. No simulated events."""

import time

from .agents import AGENTS
from .orchestration import STAGES

PREPARED = [
    {"id": "PESQUISADOR", "name": "PESQUISADOR", "role": "Pesquisa e fontes"},
    {"id": "MARKETING", "name": "MARKETING", "role": "Conteúdo e comunicação"},
    {"id": "ANALISTA", "name": "ANALISTA", "role": "Análise e relatórios"},
]


def office_snapshot(runs, *, worker_online):
    now = int(time.time())
    result = []
    for definition in [*AGENTS, *PREPARED]:
        agent_id = definition["id"]
        history = []
        candidates = []
        for run in runs:
            repository = getattr(run, "scope", "") == "repository_code"
            stages = (
                ["CEO", "PESQUISADOR", "DEV", "DESIGNER", "QA", "CEO"] if repository else STAGES
            )
            for step in run.steps:
                if step["agent"] == agent_id:
                    history.append(
                        {
                            **step,
                            "run_id": run.id,
                            "executor": run.executor,
                            "created_at": step.get("created_at", run.created_at),
                        }
                    )
            if run.stage >= len(stages) and not (repository and run.status == "awaiting_approval"):
                continue
            owner = stages[min(run.stage, len(stages) - 1)]
            if (
                repository
                and run.stage == 5
                and run.steps
                and run.steps[-1].get("execution_started")
                and not run.steps[-1].get("test_result")
            ):
                owner = "QA"
            if (
                getattr(run, "scope", "draft_only") in {"python_code", "nextjs_code"}
                and run.stage == 4
                and len(run.steps) == 4
                and run.steps[3].get("execution_started")
                and not run.steps[3].get("test_result")
            ):
                owner = "QA"
            if run.status == "awaiting_approval" and run.steps:
                owner = run.steps[-1]["agent"]
            if owner == agent_id:
                candidates.append(run)
        active = [
            r
            for r in candidates
            if r.status in {"running", "awaiting_approval", "queued", "blocked"}
        ]
        priority = {"running": 0, "awaiting_approval": 1, "queued": 2, "blocked": 3}
        selected = (
            min(active, key=lambda r: priority[r.status])
            if active
            else next(iter(candidates), None)
        )
        state = "available"
        if selected:
            state = {
                "running": "working",
                "awaiting_approval": "awaiting_approval",
                "failed": "error",
                "blocked": "error",
            }.get(selected.status, "available")
        if state == "available" and history and not active:
            state = "completed"
        result.append(
            {
                "id": agent_id,
                "name": definition["name"],
                "role": definition["role"],
                "enabled": definition in AGENTS
                or (
                    agent_id == "PESQUISADOR"
                    and any(getattr(r, "scope", "") == "repository_code" for r in runs)
                ),
                "activity": {
                    "CEO": "Planejando" if selected and selected.stage == 0 else "Revisando",
                    "DEV": "Programando",
                    "DESIGNER": "Documentando",
                    "QA": "Testando" if selected and selected.stage == 5 else "Revisando",
                    "PESQUISADOR": "Pesquisando",
                }.get(agent_id, "Disponível"),
                "status": state,
                "animate": bool(
                    state == "working" and worker_online and selected.lease_expires_at > now
                ),
                "run_id": selected.id if selected else None,
                "executor": selected.executor if selected else None,
                "run_status": selected.status if selected else None,
                "error": selected.error if selected else "",
                "history": history[:10],
            }
        )
    return result
