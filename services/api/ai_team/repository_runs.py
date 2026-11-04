"""Leased, checkpointed execution. Models propose files; only worker applies them."""

import json
import time
from typing import TypedDict

from fastapi import HTTPException
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from .config import ROOT
from .models import Event, Project, RepositoryJob, Run, RunExecutor, Task
from .orchestration import BOUNDARIES, Draft
from .python_sandbox import PythonSandbox
from .repository_policy import RepositoryBundle, RepositoryFile, RepositoryPolicy, fingerprint
from .repository_workspace import TaskWorkspace

ROLES = ["CEO", "PESQUISADOR", "DEV", "DESIGNER", "QA", "CEO"]
INSTRUCTIONS = [
    "Planeje alterações pequenas nos arquivos autorizados. Delegue tarefas concretas.",
    "Pesquise o snapshot autorizado. Explique contratos, riscos e evidências presentes. "
    "Você não tem acesso à internet; não invente fontes ou arquivos.",
    "Implemente o pedido nos arquivos .py autorizados, sem test_*.py. Biblioteca padrão. "
    "Entregue conteúdo completo dos arquivos alterados, não patches.",
    "Crie documentação de uso em arquivos .md autorizados. Preserve código e testes. "
    "Entregue arquivos completos. Este perfil não permite alterar interfaces TSX.",
    "Escreva testes unittest independentes em test_*.py autorizados. Cubra comportamento "
    "esperado e erros. Não altere fonte DEV. Testes ainda não foram executados.",
    "Revise o diff e o test_result do executor. Consolide entrega, limitações e testes "
    "efetivamente confirmados. Nenhuma publicação ou merge foi executado.",
]


class ExecutionBundle(BaseModel):
    files: list[RepositoryFile] = Field(min_length=1, max_length=12)
    binding: str = Field(pattern=r"^[a-f0-9]{64}$")

    @property
    def digest(self):
        return fingerprint(self.model_dump())


class RepositorySandbox(PythonSandbox):
    def validate_bundle(self, bundle):
        result = ExecutionBundle.model_validate(bundle.model_dump())
        if len({f.path for f in result.files}) != len(result.files):
            raise ValueError("Arquivos duplicados")
        if sum(len(f.content.encode()) for f in result.files) > 49152:
            raise ValueError("Limite de 48 KiB")
        return result


def execution_bundle(state):
    bundle = RepositoryBundle.model_validate(state["bundle"])
    files = {**state["snapshot"], **{f.path: f.content for f in bundle.files}}
    return ExecutionBundle(
        binding=bundle.digest,
        files=[RepositoryFile(path=p, content=files[p]) for p in sorted(files)],
    )


class RepositoryStore:
    def __init__(self, database, root=None):
        self.database = database
        self.root = root or ROOT / ".data" / "task-workspaces"

    def create(self, project_id, prompt, policy, actor, executor):
        policy = RepositoryPolicy.model_validate(policy.model_dump())
        if executor not in {"codex", "hermes"}:
            raise HTTPException(422, "Executor inválido")
        with self.database.session() as db:
            project = db.get(Project, project_id)
            if project is None:
                raise HTTPException(404, "Projeto não encontrado")
            run = Run(
                project_id=project_id, prompt=prompt, mode=project.mode, scope="repository_code"
            )
            run.executor_binding = RunExecutor(executor=executor)
            db.add(run)
            db.flush()
            db.add(RepositoryJob(run_id=run.id, state={"policy": policy.model_dump()}))
            db.add(
                Event(
                    kind="repository.authorized",
                    resource_id=run.id,
                    actor=actor,
                    summary="Leitura, escrita e sandbox autorizados nos caminhos explícitos",
                )
            )
            db.commit()
            return run

    def view(self, run_id):
        from .run_routes import RunView

        with self.database.session() as db:
            run, job = db.get(Run, run_id), db.get(RepositoryJob, run_id)
            if run is None or job is None:
                raise HTTPException(404, "Execução em repositório não encontrada")
            state = job.state
            digest = fingerprint(
                {"id": run.id, "stage": run.stage, "steps": run.steps, "state": state}
            )
            return {
                "run": RunView.model_validate(run).model_dump(),
                "state": state,
                "digest": digest,
            }

    def save(self, run, state, *, status="running", steps=None, stage=None, tokens=(0, 0)):
        with self.database.session() as db:
            values = {
                "status": status,
                "input_tokens": Run.input_tokens + tokens[0],
                "output_tokens": Run.output_tokens + tokens[1],
            }
            if status != "running":
                values.update(lease_token="", lease_expires_at=0)
            if steps is not None:
                values["steps"] = steps
            if stage is not None:
                values["stage"] = stage
            changed = db.execute(
                update(Run)
                .where(
                    Run.id == run.id,
                    Run.scope == "repository_code",
                    Run.status == "running",
                    Run.lease_token == run.lease_token,
                    Run.stage == run.stage,
                    Run.lease_expires_at > int(time.time()),
                )
                .values(**values)
            )
            if changed.rowcount != 1:
                raise InterruptedError("Lease cancelado ou expirado")
            db.execute(
                update(RepositoryJob).where(RepositoryJob.run_id == run.id).values(state=state)
            )
            db.add(
                Event(
                    kind="repository.checkpoint",
                    resource_id=run.id,
                    actor="worker",
                    summary=f"Checkpoint da etapa {stage or run.stage}: {status}",
                )
            )
            if steps and run.stage == 0:
                for task in steps[0]["tasks"]:
                    db.add(Task(project_id=run.project_id, **task))
            db.commit()

    def reserve(self, run):
        with self.database.session() as db:
            changed = db.execute(
                update(Run)
                .where(
                    Run.id == run.id,
                    Run.scope == "repository_code",
                    Run.status == "running",
                    Run.stage == run.stage,
                    Run.lease_token == run.lease_token,
                    Run.calls < 6,
                    Run.input_tokens + Run.output_tokens < 50000,
                )
                .values(calls=Run.calls + 1)
            )
            db.commit()
            if changed.rowcount != 1:
                raise RuntimeError("Limite de chamadas ou tokens")

    def recover(self, sandbox):
        with self.database.session() as db:
            jobs = list(
                db.scalars(
                    select(RepositoryJob)
                    .join(Run)
                    .where(Run.scope == "repository_code", Run.status.in_(["failed", "cancelled"]))
                )
            )
            for job in jobs:
                state = dict(job.state)
                if not state.get("execution_started") or state.get("cleanup_confirmed"):
                    continue
                try:
                    sandbox.cleanup(state["container_name"])
                except Exception:
                    return False
                state["cleanup_confirmed"] = True
                job.state = state
                db.add(
                    Event(
                        kind="repository.recovered",
                        resource_id=job.run_id,
                        actor="worker",
                        summary="Sandbox encerrado; testes não repetidos",
                    )
                )
            db.commit()
        return True

    def decide(self, run_id, digest, approve, actor):
        view = self.view(run_id)
        if view["digest"] != digest or view["run"]["status"] != "awaiting_approval":
            raise HTTPException(409, "Revise o checkpoint e seu digest atual")
        stage, state = view["run"]["stage"], dict(view["state"])
        status = "cancelled" if not approve else "completed" if stage == 6 else "queued"
        if approve and stage == 5:
            state["approved_execution"] = execution_bundle(state).digest
        if approve and stage == 6:
            if state.get("test_result", {}).get("status") != "passed":
                raise HTTPException(409, "Testes não passaram; entrega não pode ser aprovada")
            state["reviewed_digest"] = digest
        with self.database.session() as db:
            # Serializes competing decisions, cancellation and publication on the Run row.
            changed = db.execute(
                update(Run)
                .where(
                    Run.id == run_id,
                    Run.status == "awaiting_approval",
                    Run.stage == stage,
                )
                .values(status=status)
            )
            if changed.rowcount != 1:
                raise HTTPException(409, "Decisão já consumida")
            job = db.get(RepositoryJob, run_id)
            if job.state != view["state"]:
                db.rollback()
                raise HTTPException(409, "Checkpoint alterado")
            job.state = state
            db.add(
                Event(
                    kind="repository.decision",
                    resource_id=run_id,
                    actor=actor,
                    summary=f"Digest {digest}: {status}",
                )
            )
            db.commit()
        return self.view(run_id)


class AgentState(TypedDict):
    context: dict
    draft: dict


def generate(provider, run, state, tick):
    def node(current):
        instruction = INSTRUCTIONS[run.stage]
        if run.stage in {2, 3, 4}:
            instruction += (
                ' deliverable é STRING JSON {"files":[{"path":"nome",'
                '"content":"conteúdo completo"}]}. Sem markdown externo. '
                "Use apenas write_paths do policy. Até 12000 caracteres no total."
            )
        return {
            "draft": provider.generate(
                ROLES[run.stage], instruction + BOUNDARIES, current["context"], tick
            ).model_dump()
        }

    builder = StateGraph(AgentState)
    builder.add_node("specialist", node)
    builder.add_edge(START, "specialist")
    builder.add_edge("specialist", END)
    context = {
        "request": run.prompt,
        "policy": state["policy"],
        "snapshot": state["snapshot"],
        "previous_steps": run.steps,
        "test_result": state.get("test_result"),
        "diff": state.get("diff", ""),
    }
    return Draft.model_validate(
        builder.compile().invoke({"context": context}, {"recursion_limit": 4})["draft"]
    )


def execute_repository(store, run, provider, tick, sandbox=None, snapshot_reader=None):
    state = dict(store.view(run.id)["state"])
    policy = RepositoryPolicy.model_validate(state["policy"])
    tick()
    if "snapshot" not in state:
        if snapshot_reader is None:
            from .github_client import GitHubClient
            from .repository_snapshot import read_snapshot

            client = GitHubClient()
            client.tick = tick
            try:
                snapshot = read_snapshot(client, policy)
            finally:
                client.close()
        else:
            snapshot = snapshot_reader(policy)
        TaskWorkspace(store.root, run.id).initialize(snapshot)
        state["snapshot"] = snapshot
        store.save(run, state)
    if run.stage == 5 and "test_result" not in state:
        bundle = execution_bundle(state)
        if state.get("approved_execution") != bundle.digest or state.get("execution_started"):
            raise RuntimeError("Sandbox exige aprovação exata; execução incerta não se repete")
        runtime = sandbox or RepositorySandbox()
        name = runtime.new_name()
        state.update(execution_started=True, container_name=name, cleanup_confirmed=False)
        store.save(run, state)
        result = runtime.run(bundle, tick, name=name)
        tick()
        if result.get("artifact_digest") != bundle.digest:
            raise ValueError("Resultado de outros artefatos")
        state.update(test_result=result, cleanup_confirmed=True)
        store.save(run, state, status="queued")
        return
    store.reserve(run)
    draft = generate(provider, run, state, tick)
    tick()
    if run.input_tokens + run.output_tokens + draft.input_tokens + draft.output_tokens > 50000:
        store.save(run, state, status="failed", tokens=(draft.input_tokens, draft.output_tokens))
        return
    if run.stage in {2, 3, 4}:
        parsed = json.loads(draft.deliverable)
        part = RepositoryBundle(policy=policy, **parsed)
        for file in part.files:
            valid = (
                file.path.endswith(".md")
                if run.stage == 3
                else file.path.endswith(".py") and file.path.startswith("test_")
                if run.stage == 4
                else file.path.endswith(".py") and not file.path.startswith("test_")
            )
            if not valid:
                raise ValueError("Especialista não autorizado a alterar esse arquivo")
        previous = state.get("bundle", {}).get("files", [])
        bundle = RepositoryBundle(policy=policy, files=[*previous, *part.files])
        state["bundle"] = bundle.model_dump()
        if run.stage == 4:
            state["diff"] = TaskWorkspace(store.root, run.id).apply(bundle)
            if not state["diff"]:
                raise ValueError("Nenhuma alteração real proposta")
            execution_bundle(state)  # Validate combined snapshot before approval.
    step = {
        "agent": ROLES[run.stage],
        "stage": run.stage,
        "created_at": int(time.time()),
        **draft.model_dump(),
    }
    stage = run.stage + 1
    status = (
        "awaiting_approval"
        if (stage in {5, 6} or run.mode == "manual" or (run.mode == "supervised" and stage == 1))
        else "queued"
    )
    if stage == 6:
        state["proposal"] = {
            "repository": policy.repository,
            "base_sha": policy.base_sha,
            "branch": "codex/ai-team/task-" + run.id,
            "title": "feat: " + run.prompt[:100].replace("\n", " "),
            "files": [
                {"path": policy.directory + "/" + f["path"], "content": f["content"]}
                for f in state["bundle"]["files"]
            ],
            "tests": state["test_result"],
            "published": False,
        }
    store.save(
        run,
        state,
        status=status,
        steps=[*run.steps, step],
        stage=stage,
        tokens=(draft.input_tokens, draft.output_tokens),
    )
