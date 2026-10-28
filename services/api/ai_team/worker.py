import argparse
import time

from .config import Settings
from .db import Database
from .models import new_id
from .orchestration import Draft, build_graph
from .workflow import WorkflowStore


class Worker:
    def __init__(self, database, settings, provider):
        self.store = WorkflowStore(database)
        self.settings, self.provider = settings, provider
        self.id = new_id()

    def once(self):
        self.store.heartbeat(self.id)
        run = self.store.claim()
        if run is None:
            return False
        try:
            if not self.provider.ready():
                self.store.finish_error(
                    run, "blocked", "Codex indisponível. Conclua o login próprio."
                )
                return True
            if not self.store.reserve_call(run):
                self.store.finish_error(
                    run, "failed", "Limite de execução atingido ou escopo inválido."
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
            state = build_graph(self.provider, tick).invoke(
                {"stage": run.stage, "prompt": run.prompt, "steps": run.steps},
                {"recursion_limit": 8},
            )
            self.store.save_step(run, Draft.model_validate(state["draft"]))
        except InterruptedError:
            self.store.finish_error(run, "cancelled", "Execução interrompida pelo proprietário.")
        except TimeoutError:
            self.store.finish_error(run, "failed", "Timeout do Codex. Chamada não repetida.")
        except KeyboardInterrupt:
            self.store.finish_error(run, "failed", "Worker encerrado. Chamada não repetida.")
            raise
        except Exception:
            # Provider errors can include credentials; do not log raw exception text.
            self.store.finish_error(
                run, "failed", "Falha no executor. Confira a configuração e os limites da conta."
            )
        return True


def main():
    from .codex_provider import CodexProvider

    parser = argparse.ArgumentParser(description="Worker separado do AI TEAM")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    database = Database(settings)
    if settings.environment != "production":
        database.initialize()
    worker = Worker(database, settings, CodexProvider())
    print("Worker AI TEAM ativo; somente elaboração textual autorizada.", flush=True)
    while True:
        processed = worker.once()
        if args.once:
            break
        if not processed:
            time.sleep(2)


if __name__ == "__main__":
    main()
