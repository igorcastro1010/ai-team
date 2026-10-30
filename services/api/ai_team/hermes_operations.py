"""Resource-bound reconciliation and cancellation through the official Runs API."""

from fastapi import HTTPException

from .hermes_journal import REMOTE_ID, TERMINAL, HermesJournal


class HermesOperations:
    def __init__(self, database, client):
        self.journal = HermesJournal(database)
        self.client = client

    def reference(self, attempt_id):
        attempt = self.journal.get(attempt_id)
        if not attempt.remote_id or not REMOTE_ID.fullmatch(attempt.remote_id):
            raise HTTPException(
                409, "Admissão incerta ou sem ID remoto. Não readmitir automaticamente."
            )
        return attempt

    def refresh(self, attempt_id):
        attempt = self.reference(attempt_id)
        try:
            response = self.client.request("GET", f"/v1/runs/{attempt.remote_id}")
            self.journal.observe(attempt_id, response)
        except Exception:
            raise HTTPException(
                502, "Consulta Hermes indisponível. Estado anterior preservado."
            ) from None
        return self.journal.view(self.journal.get(attempt_id))

    def stop(self, attempt_id):
        attempt = self.reference(attempt_id)
        if attempt.remote_status in TERMINAL:
            return self.journal.view(attempt)
        if attempt.run.status not in {"cancelled", "failed"}:
            raise HTTPException(
                409, "Cancele primeiro a execução local antes de interromper no Hermes."
            )
        self.journal.mark_stop(attempt_id, "requested")
        try:
            self.client.request("POST", f"/v1/runs/{attempt.remote_id}/stop", body={})
            response = self.client.request("GET", f"/v1/runs/{attempt.remote_id}")
            self.journal.observe(attempt_id, response)
        except Exception:
            self.journal.mark_stop(attempt_id, "uncertain")
            raise HTTPException(
                502, "Interrupção Hermes não confirmada. Consulte novamente."
            ) from None
        return self.journal.view(self.journal.get(attempt_id))
