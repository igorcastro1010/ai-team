"""Private, bounded adapter for the official Hermes Runs API.

Phase 1 is text-only. Native tools/delegation require a separately reviewed policy.
Never expose this client as a general-purpose URL or path proxy.
"""

import json
import re
import time
import uuid

import httpx

from .orchestration import Draft, DraftContent

MAX_RESPONSE = 200_000
RUN_ID = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")


class HermesClient:
    def __init__(self, settings, *, transport=None):
        self.settings = settings
        self.transport = transport

    @property
    def configured(self):
        return bool(self.settings.hermes_url and self.settings.hermes_key.get_secret_value())

    def request(self, method, path, *, body=None, key=None):
        if not self.configured:
            raise RuntimeError("Hermes não configurado")
        headers = {"Authorization": "Bearer " + self.settings.hermes_key.get_secret_value()}
        if key:
            headers["Idempotency-Key"] = key
        # No ambient HTTP proxy, redirect, automatic retry or credentials in URL.
        with httpx.Client(
            base_url=self.settings.hermes_url, headers=headers, transport=self.transport,
            trust_env=False, follow_redirects=False, timeout=httpx.Timeout(5, connect=2),
        ) as client:
            with client.stream(method, path, json=body) as response:
                if not 200 <= response.status_code < 300:
                    raise RuntimeError("Hermes recusou a solicitação")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > MAX_RESPONSE:
                        raise RuntimeError("Resposta Hermes excedeu limite")
                try:
                    value = json.loads(data)
                except (ValueError, UnicodeError):
                    raise RuntimeError("Resposta Hermes inválida") from None
                if not isinstance(value, (dict, list)):
                    raise RuntimeError("Contrato Hermes inválido")
                return value

    def inspect(self):
        result = {"status": "not_configured", "checked_at": None,
                  "inference_verified": False, "text_only": True}
        if not self.configured:
            return result
        result["checked_at"] = int(time.time())
        try:
            capabilities = self.request("GET", "/v1/capabilities")
            if capabilities.get("object") != "hermes.api_server.capabilities":
                raise RuntimeError("API incompatível")
            tools = self.request("GET", "/v1/toolsets")
            if not isinstance(tools, list) or any(
                not isinstance(item, dict) or not isinstance(item.get("enabled"), bool)
                for item in tools
            ):
                raise RuntimeError("Inventário de ferramentas inválido")
            if any(item["enabled"] for item in tools):
                result["status"] = "unsafe_configuration"
            else:
                result["status"] = "reachable"
        except (httpx.HTTPError, RuntimeError, AttributeError):
            result["status"] = "unavailable"
        return result


class HermesProvider:
    def __init__(self, client, *, time_limit=120, poll_interval=0.5):
        self.client = client
        self.time_limit = min(max(time_limit, 0), 120)
        self.poll_interval = poll_interval

    def ready(self):
        return self.client.inspect()["status"] == "reachable"

    def generate(self, role, instructions, context, on_tick):
        if not self.ready():
            raise RuntimeError("Hermes indisponível ou ferramentas habilitadas")
        on_tick()
        identity = "ai-team-" + uuid.uuid4().hex
        prompt = json.dumps({"role": role, "context": context,
                             "response_schema": DraftContent.model_json_schema()},
                            ensure_ascii=False)
        run_id = None
        deadline = time.monotonic() + self.time_limit
        try:
            admitted = self.client.request("POST", "/v1/runs", key=identity, body={
                "input": prompt, "instructions": instructions +
                " Retorne somente um objeto JSON conforme response_schema, sem markdown.",
                "session_id": identity,
            })
            run_id = admitted.get("run_id")
            if not isinstance(run_id, str) or not RUN_ID.fullmatch(run_id):
                run_id = None
                raise RuntimeError("Identificador de execução inválido; não repetir chamada")
            while True:
                on_tick()
                if time.monotonic() >= deadline:
                    raise TimeoutError("Tempo Hermes excedido")
                result = self.client.request("GET", f"/v1/runs/{run_id}")
                status = result.get("status")
                if status == "completed":
                    content = DraftContent.model_validate_json(result.get("output", ""))
                    usage = result.get("usage") or {}
                    tokens = [usage.get("input_tokens"), usage.get("output_tokens")]
                    if any(type(value) is not int or value < 0 for value in tokens):
                        raise RuntimeError("Uso de tokens não informado pelo Hermes")
                    return Draft(**content.model_dump(),
                                 input_tokens=tokens[0], output_tokens=tokens[1])
                if status not in {"started", "queued", "running"}:
                    raise RuntimeError("Hermes não confirmou conclusão; não repetir chamada")
                time.sleep(self.poll_interval)
        except BaseException:
            # Stop is best effort: network failure can leave remote execution uncertain.
            # No automatic readmission under a new key.
            if run_id:
                try:
                    self.client.request("POST", f"/v1/runs/{run_id}/stop", body={})
                except Exception:
                    pass
            raise
