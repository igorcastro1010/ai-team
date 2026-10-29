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
            for step in run.steps:
                if step["agent"] == agent_id:
                    history.append({**step, "run_id": run.id, "executor": run.executor,
                                    "created_at": run.created_at})
            if run.stage >= len(STAGES):
                continue
            owner = STAGES[run.stage]
            if run.status == "awaiting_approval" and run.steps:
                owner = run.steps[-1]["agent"]
            if owner == agent_id:
                candidates.append(run)
        active = [r for r in candidates if r.status in {
            "running", "awaiting_approval", "queued", "blocked"}]
        selected = next(iter(active or candidates), None)
        state = "available"
        if selected:
            state = {"running": "working", "awaiting_approval": "awaiting_approval",
                     "failed": "error", "blocked": "error"}.get(selected.status, "available")
        if state == "available" and history and not active:
            state = "completed"
        result.append({
            "id": agent_id, "name": definition["name"], "role": definition["role"],
            "enabled": definition in AGENTS, "status": state,
            "animate": bool(state == "working" and worker_online
                            and selected.lease_expires_at > now),
            "run_id": selected.id if selected else None,
            "executor": selected.executor if selected else None,
            "run_status": selected.status if selected else None,
            "error": selected.error if selected else "",
            "history": history[:10],
        })
    return result
