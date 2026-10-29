"""Processo de agendamento separado; apenas insere solicitações na fila persistente."""

import argparse
import time

from .config import Settings
from .db import Database
from .schedules import ScheduleStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    settings = Settings()
    database = Database(settings)
    if settings.environment != "production":
        database.initialize()
    store = ScheduleStore(database)
    try:
        while True:
            try:
                count = store.tick()
                if count or args.once:
                    print(
                        f"Scheduler AI TEAM: {count} solicitação(ões) enfileirada(s).", flush=True
                    )
            except Exception:
                # Database exceptions can contain connection URLs or prompt content.
                print("Falha no scheduler; verifique o banco e a instalação.", flush=True)
                if args.once:
                    raise SystemExit(1) from None
            if args.once:
                return
            time.sleep(5)
    except KeyboardInterrupt:
        return
    finally:
        database.engine.dispose()


if __name__ == "__main__":
    main()
