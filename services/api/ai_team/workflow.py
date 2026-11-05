import time

from fastapi import HTTPException
from sqlalchemy import func, select, update

from .code_artifacts import CODE_SCOPES, bundle_for_scope
from .models import Event, Project, Run, RunExecutor, Task, WorkerHeartbeat, new_id
from .orchestration import STAGES, Draft


class WorkflowStore:
    def __init__(self, database):
        self.database = database

    def get(self, run_id):
        with self.database.session() as db:
            run = db.get(Run, run_id)
            if run is None:
                raise HTTPException(404, "Execução não encontrada")
            return run

    def all(self):
        with self.database.session() as db:
            return list(db.scalars(select(Run).order_by(Run.created_at.desc(), Run.id).limit(200)))

    def pending(self):
        with self.database.session() as db:
            return list(
                db.scalars(
                    select(Run)
                    .where(Run.status == "awaiting_approval")
                    .order_by(Run.created_at, Run.id)
                    .limit(200)
                )
            )

    def create(self, project_id, prompt, actor, executor="codex", scope="draft_only"):
        if scope not in {"draft_only", *CODE_SCOPES}:
            raise HTTPException(422, "Escopo inválido")
        if executor not in {"codex", "hermes"}:
            raise HTTPException(422, "Executor inválido")
        with self.database.session() as db:
            project = db.get(Project, project_id)
            if not project:
                raise HTTPException(404, "Projeto não encontrado")
            run = Run(project_id=project_id, prompt=prompt, mode=project.mode, scope=scope)
            run.executor_binding = RunExecutor(executor=executor)
            db.add(run)
            db.flush()
            db.add(
                Event(
                    kind="run.requested",
                    resource_id=run.id,
                    actor=actor,
                    summary=f"Solicitação autorizada ({executor}): {scope}",
                )
            )
            db.commit()
            return run

    def decide(self, run_id, stage, approve, actor, artifact_digest=""):
        run = self.get(run_id)
        if run.scope == "repository_code":
            raise HTTPException(409, "Use a decisão vinculada ao checkpoint do repositório")
        values = {"status": "queued" if approve else "cancelled"}
        if run.scope in CODE_SCOPES and stage == 4 and approve:
            expected = bundle_for_scope(run.scope, run.steps).digest
            if artifact_digest != expected:
                raise HTTPException(409, "Revise e aprove o hash exato dos artefatos")
            values["steps"] = [
                *run.steps[:-1],
                {
                    **run.steps[-1],
                    "approved_digest": expected,
                },
            ]
        with self.database.session() as db:
            changed = db.execute(
                update(Run)
                .where(
                    Run.id == run_id,
                    Run.status == "awaiting_approval",
                    Run.stage == stage,
                )
                .values(**values)
            )
            if changed.rowcount != 1:
                raise HTTPException(
                    409, "Decisão já aplicada ou etapa alterada. Atualize o painel."
                )
            db.add(
                Event(
                    kind="run.approved" if approve else "run.rejected",
                    resource_id=run_id,
                    actor=actor,
                    summary=f"Etapa {stage + 1}: "
                    + (
                        (
                            f"artefatos {artifact_digest} autorizados"
                            if artifact_digest
                            else "elaboração autorizada"
                        )
                        if approve
                        else "execução rejeitada"
                    ),
                )
            )
            db.commit()
        return self.get(run_id)

    def cancel(self, run_id, actor):
        self.get(run_id)
        with self.database.session() as db:
            result = db.execute(
                update(Run)
                .where(
                    Run.id == run_id,
                    Run.status.in_(
                        [
                            "queued",
                            "running",
                            "awaiting_approval",
                            "blocked",
                        ]
                    ),
                )
                .values(status="cancelled", lease_token="", lease_expires_at=0)
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Execução já encerrada")
            db.add(
                Event(
                    kind="run.cancelled",
                    resource_id=run_id,
                    actor=actor,
                    summary="Execução cancelada pelo proprietário",
                )
            )
            db.commit()
        return self.get(run_id)

    def unblock(self, run_id, actor):
        self.get(run_id)
        with self.database.session() as db:
            result = db.execute(
                update(Run)
                .where(Run.id == run_id, Run.status == "blocked")
                .values(status="queued", error="")
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Somente execuções bloqueadas podem ser retomadas")
            db.add(
                Event(
                    kind="run.resumed",
                    resource_id=run_id,
                    actor=actor,
                    summary="Nova tentativa após configurar o executor",
                )
            )
            db.commit()
        return self.get(run_id)

    def claim(self, *, allow_code=True):
        now = int(time.time())
        with self.database.session() as db:
            stale = list(
                db.scalars(
                    select(Run).where(
                        Run.status == "running",
                        Run.lease_expires_at < now,
                    )
                )
            )
            for run in stale:
                changed = db.execute(
                    update(Run)
                    .where(
                        Run.id == run.id,
                        Run.status == "running",
                        Run.lease_token == run.lease_token,
                        Run.lease_expires_at < now,
                    )
                    .values(
                        status="failed",
                        error="Worker interrompido. Chamada não repetida.",
                        lease_token="",
                        lease_expires_at=0,
                    )
                )
                if changed.rowcount:
                    db.add(
                        Event(
                            kind="run.failed",
                            resource_id=run.id,
                            actor="worker",
                            summary="Worker interrompido; etapa incerta exige revisão",
                        )
                    )
            db.commit()
            run_id = db.scalar(
                select(Run.id)
                .where(Run.status == "queued", True if allow_code else
                       ~Run.scope.in_([*CODE_SCOPES, "repository_code"]))
                .order_by(Run.created_at, Run.id)
                .limit(1)
            )
            if run_id is None:
                return None
            token = new_id()
            claimed = db.execute(
                update(Run)
                .where(Run.id == run_id, Run.status == "queued")
                .values(status="running", lease_token=token, lease_expires_at=now + 180)
            )
            db.commit()
            return self.get(run_id) if claimed.rowcount == 1 else None

    def reserve_call(self, run):
        with self.database.session() as db:
            changed = db.execute(
                update(Run)
                .where(
                    Run.id == run.id,
                    Run.status == "running",
                    Run.lease_token == run.lease_token,
                    Run.calls < 5,
                    Run.input_tokens + Run.output_tokens < 50000,
                    Run.scope.in_(["draft_only", *CODE_SCOPES]),
                )
                .values(calls=Run.calls + 1)
            )
            db.commit()
            return changed.rowcount == 1

    def save_step(self, run, draft: Draft):
        step = {
            "stage": run.stage,
            "agent": STAGES[run.stage],
            "created_at": int(time.time()),
            **draft.model_dump(),
        }
        stage = run.stage + 1
        status = "completed" if stage == 5 else "queued"
        if stage < 5 and (run.mode == "manual" or (run.mode == "supervised" and stage == 1)):
            status = "awaiting_approval"
        if run.scope == "python_code":
            from .code_artifacts import CodeBundle, bundle_for_steps

            if run.stage == 1:
                files = CodeBundle.model_validate_json(draft.deliverable).files
                if any(file.path.startswith("test_") for file in files):
                    raise ValueError("DEV não pode fornecer testes QA")
            if stage == 4:
                bundle_for_steps([*run.steps, step])
                status = "awaiting_approval"
        if run.scope == "nextjs_code":
            from .next_artifacts import validate_part

            if run.stage in {1, 2, 3}:
                validate_part(STAGES[run.stage], draft.deliverable)
            if stage == 4:
                project = bundle_for_scope(run.scope, [*run.steps, step])
                step["project_snapshot"] = project.model_dump()
                status = "awaiting_approval"
        with self.database.session() as db:
            changed = db.execute(
                update(Run)
                .where(
                    Run.id == run.id,
                    Run.status == "running",
                    Run.lease_token == run.lease_token,
                    Run.stage == run.stage,
                )
                .values(
                    steps=[*run.steps, step],
                    stage=stage,
                    status=status,
                    error="",
                    input_tokens=Run.input_tokens + draft.input_tokens,
                    output_tokens=Run.output_tokens + draft.output_tokens,
                    lease_token="",
                    lease_expires_at=0,
                )
            )
            if changed.rowcount != 1:
                db.rollback()
                return False
            if run.stage == 0:
                for task in draft.tasks:
                    db.add(Task(project_id=run.project_id, **task.model_dump()))
                if draft.tasks:
                    db.add(
                        Event(
                            kind="run.delegated",
                            resource_id=run.id,
                            actor="CEO",
                            summary=f"CEO criou {len(draft.tasks)} tarefas propostas",
                        )
                    )
            db.add(
                Event(
                    kind="run.step_completed",
                    resource_id=run.id,
                    actor=STAGES[run.stage],
                    summary=f"Etapa {stage}/5 concluída: artefato textual gerado",
                )
            )
            db.commit()
            return True

    def record_sandbox(self, run, *, result=None, container_name="", release=False):
        from .python_sandbox import valid_name

        bundle = bundle_for_scope(run.scope, run.steps)
        qa = run.steps[3]
        if qa.get("approved_digest") != bundle.digest:
            raise RuntimeError("Execução sem aprovação exata dos artefatos")
        if result is None and qa.get("execution_started"):
            raise RuntimeError("Sandbox já admitido; não repetir execução incerta")
        if result is None and not valid_name(container_name):
            raise RuntimeError("Identificação de sandbox inválida")
        if result is not None and result.get("artifact_digest") != bundle.digest:
            raise RuntimeError("Resultado não corresponde aos artefatos aprovados")
        qa = {
            **qa,
            **(
                {"test_result": result}
                if result is not None
                else {
                    "execution_started": True,
                    "container_name": container_name,
                }
            ),
        }
        values = {"steps": [*run.steps[:3], qa]}
        if release:
            if result is None:
                raise RuntimeError("Somente resultado confirmado libera a lease")
            values.update(status="queued", lease_token="", lease_expires_at=0)
        with self.database.session() as db:
            changed = db.execute(
                update(Run)
                .where(
                    Run.id == run.id,
                    Run.status == "running",
                    Run.stage == 4,
                    Run.lease_token == run.lease_token,
                )
                .values(**values)
            )
            if changed.rowcount != 1:
                raise InterruptedError("Lease alterada; execução interrompida")
            db.add(
                Event(
                    kind="run.sandbox_finished" if result is not None else "run.sandbox_started",
                    resource_id=run.id,
                    actor="QA",
                    summary="Resultado dos testes persistido"
                    if result is not None
                    else "Testes isolados autorizados por hash",
                )
            )
            db.commit()
        return self.get(run.id)

    def recover_sandboxes(self, sandbox):
        """Reconcile only persisted containers of cancelled/expired executions."""
        from sqlalchemy import or_

        cursor = ""
        now = int(time.time())
        while True:
            with self.database.session() as db:
                runs = list(
                    db.scalars(
                        select(Run)
                        .where(
                            Run.id > cursor,
                            Run.scope.in_(CODE_SCOPES),
                            Run.stage == 4,
                            Run.status.in_(["running", "cancelled", "failed"]),
                            or_(Run.status != "running", Run.lease_expires_at < now),
                        )
                        .order_by(Run.id)
                        .limit(50)
                    )
                )
            if not runs:
                return True
            for current in runs:
                cursor = current.id
                qa = current.steps[3] if len(current.steps) == 4 else {}
                if not qa.get("execution_started") or qa.get("cleanup_confirmed"):
                    continue
                confirmed = True
                try:
                    sandbox.cleanup(qa.get("container_name", ""))
                except (RuntimeError, OSError):
                    confirmed = False
                state = "confirmed" if confirmed else "uncertain"
                with self.database.session() as db:
                    changed = db.execute(
                        update(Run)
                        .where(
                            Run.id == current.id,
                            Run.lease_token == current.lease_token,
                            or_(Run.status != "running", Run.lease_expires_at < now),
                        )
                        .values(
                            steps=[
                                *current.steps[:3],
                                {
                                    **qa,
                                    "cleanup_confirmed": confirmed,
                                    "cleanup_state": state,
                                },
                            ]
                        )
                    )
                    if changed.rowcount and qa.get("cleanup_state") != state:
                        db.add(
                            Event(
                                kind="run.sandbox_reconciled"
                                if confirmed
                                else "run.sandbox_uncertain",
                                resource_id=current.id,
                                actor="worker",
                                summary=(
                                    "Sandbox anterior encerrado; sem repetição"
                                    if confirmed
                                    else "Encerramento incerto; novas execuções Python aguardam"
                                ),
                            )
                        )
                    db.commit()
                if not confirmed:
                    return False

    def finish_error(self, run, status, message):
        with self.database.session() as db:
            changed = db.execute(
                update(Run)
                .where(
                    Run.id == run.id,
                    Run.status == "running",
                    Run.lease_token == run.lease_token,
                )
                .values(status=status, error=message, lease_token="", lease_expires_at=0)
            )
            if changed.rowcount:
                db.add(
                    Event(kind=f"run.{status}", resource_id=run.id, actor="worker", summary=message)
                )
            db.commit()

    def heartbeat(self, worker_id):
        with self.database.session() as db:
            db.merge(WorkerHeartbeat(id=worker_id, last_seen=int(time.time())))
            db.commit()

    def usage(self):
        with self.database.session() as db:
            calls, inputs, outputs = db.execute(
                select(
                    func.coalesce(func.sum(Run.calls), 0),
                    func.coalesce(func.sum(Run.input_tokens), 0),
                    func.coalesce(func.sum(Run.output_tokens), 0),
                )
            ).one()
            last = db.scalar(select(func.max(WorkerHeartbeat.last_seen)))
        return {
            "requests": calls,
            "tokens": inputs + outputs,
            "cost_usd": None,
            "worker_online": bool(last and last >= int(time.time()) - 20),
        }
