import argparse
import time

from .config import Settings
from .db import Database
from .github_actions import GitHubWorker
from .models import new_id
from .orchestration import Draft, build_graph
from .workflow import WorkflowStore


class Worker:
    def __init__(self, database, settings, provider, *, providers=None, sandbox=None):
        self.store = WorkflowStore(database)
        self.settings, self.provider = settings, provider
        self.providers = providers
        self.sandbox = sandbox
        self.id = new_id()

    def once(self):
        self.store.heartbeat(self.id)
        from .python_sandbox import PythonSandbox

        sandbox = self.sandbox or PythonSandbox()
        code_ready = self.store.recover_sandboxes(sandbox)
        run = self.store.claim(allow_code=code_ready)
        if run is None:
            return False
        try:
            provider = self.providers[run.executor] if self.providers else self.provider
            if hasattr(provider, "for_run"):
                provider = provider.for_run(self.store.database, run)
            if not provider.ready():
                self.store.finish_error(
                    run, "blocked", "Executor indisponível. Confira a configuração própria."
                )
                return True
            last_heartbeat = 0

            def tick():
                nonlocal last_heartbeat
                current = self.store.get(run.id)
                if current.status != "running" or current.lease_token != run.lease_token:
                    raise InterruptedError("Execução cancelada")
                if time.monotonic() - last_heartbeat >= 5:
                    self.store.heartbeat(self.id)
                    last_heartbeat = time.monotonic()

            tick()
            if run.scope in {"python_code", "nextjs_code"} and run.stage == 4:
                from .code_artifacts import bundle_for_scope

                bundle = bundle_for_scope(run.scope, run.steps)
                qa = run.steps[3]
                if qa.get("approved_digest") != bundle.digest:
                    raise RuntimeError("Artefatos não correspondem à aprovação")
                existing = qa.get("test_result")
                if existing is not None:
                    if existing.get("artifact_digest") != bundle.digest:
                        raise RuntimeError("Resultado não corresponde aos artefatos")
                else:
                    runtime = sandbox
                    if run.scope == "nextjs_code" and self.sandbox is None:
                        from .next_sandbox import NextSandbox

                        runtime = NextSandbox()
                    name = PythonSandbox.new_name()
                    run = self.store.record_sandbox(run, container_name=name)
                    result = runtime.run(bundle, tick, name=name)
                    tick()
                    release = run.scope == "nextjs_code"
                    run = self.store.record_sandbox(run, result=result, release=release)
                    if release:
                        return True
            if not self.store.reserve_call(run):
                self.store.finish_error(
                    run, "failed", "Limite de execução atingido ou escopo inválido."
                )
                return True
            state = build_graph(provider, tick).invoke(
                {"stage": run.stage, "prompt": run.prompt, "steps": run.steps, "scope": run.scope},
                {"recursion_limit": 8},
            )
            self.store.save_step(run, Draft.model_validate(state["draft"]))
        except InterruptedError:
            self.store.finish_error(run, "cancelled", "Execução interrompida pelo proprietário.")
        except TimeoutError:
            self.store.finish_error(run, "failed", "Timeout do executor. Chamada não repetida.")
        except KeyboardInterrupt:
            self.store.finish_error(run, "failed", "Worker encerrado. Chamada não repetida.")
            raise
        except Exception:
            # Provider errors can include credentials; do not log raw exception text.
            self.store.finish_error(
                run, "failed", "Falha no executor. Confira a configuração e os limites da conta."
            )
        return True


def process_cycle(worker, github_worker):
    processed = worker.once()
    github_processed = github_worker.once()
    return processed or github_processed


def main():
    from .codex_provider import CodexProvider
    from .hermes import HermesClient, HermesProvider

    parser = argparse.ArgumentParser(description="Worker separado do AI TEAM")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    database = Database(settings)
    if settings.environment != "production":
        database.initialize()
    codex = CodexProvider()
    worker = Worker(
        database,
        settings,
        codex,
        providers={
            "codex": codex,
            "hermes": HermesProvider(HermesClient(settings)),
        },
    )
    github_worker = GitHubWorker(database, tick=lambda: worker.store.heartbeat(worker.id))
    print("Worker AI TEAM: elaboração textual e propostas GitHub aprovadas.", flush=True)
    while True:
        processed = process_cycle(worker, github_worker)
        if args.once:
            break
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
