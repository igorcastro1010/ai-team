"""Private text-only Gemini REST client; no billing activation or paid fallback."""

import json
import math
import os
import re
import time
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx

from .orchestration import BOUNDARIES, Draft, DraftContent

MODEL = "gemini-2.5-flash-lite"
PRICING_URL = "https://aistudio.google.com/docs/pricing"
REVIEW_START = datetime(2026, 11, 6, tzinfo=UTC)
REVIEW_END = datetime(2026, 11, 14, tzinfo=UTC)
MAX_RESPONSE = 200_000


def now():
    return datetime.now(UTC)


class GeminiBlocked(RuntimeError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


class GeminiUncertain(GeminiBlocked):
    """Request may have been processed; automatic replay is forbidden."""


class GeminiRateLimited(GeminiBlocked):
    def __init__(self, retry_after=60):
        self.retry_after = retry_after
        super().__init__("gemini_rate_limited")


class GeminiClient:
    def __init__(self, config=None, client=None):
        self.config = (
            dict(config)
            if config is not None
            else {
                "api_key": os.getenv("AI_TEAM_GEMINI_API_KEY", ""),
                "read_token": os.getenv("AI_TEAM_GOOGLE_READ_TOKEN", ""),
                "project_id": os.getenv("AI_TEAM_GEMINI_PROJECT_ID", ""),
                "project_number": os.getenv("AI_TEAM_GEMINI_PROJECT_NUMBER", ""),
            }
        )
        # Injected clients are for trusted application wiring/tests, never model input.
        self.client = client or httpx.Client(
            trust_env=False, follow_redirects=False, timeout=httpx.Timeout(30, connect=5)
        )

    def close(self):
        self.client.close()

    def _request(self, method, url, **kwargs):
        sent = method == "POST"
        deadline = time.monotonic() + (30 if sent else 10)
        try:
            with self.client.stream(
                method,
                url,
                follow_redirects=False,
                timeout=httpx.Timeout(30 if sent else 10, connect=5),
                **kwargs,
            ) as response:
                if response.status_code == 429:
                    raw = response.headers.get("retry-after", "60")
                    try:
                        if raw.isdigit():
                            seconds = max(int(raw), 1)
                        else:
                            retry_at = parsedate_to_datetime(raw)
                            seconds = max(math.ceil((retry_at - now()).total_seconds()), 1)
                    except (ValueError, TypeError, OverflowError):
                        seconds = 60
                    raise GeminiRateLimited(seconds)
                if sent and response.status_code >= 500:
                    raise GeminiUncertain("gemini_generation_uncertain")
                if response.status_code != 200:
                    raise GeminiBlocked("gemini_http_rejected")
                data = bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if time.monotonic() > deadline:
                        error = GeminiUncertain if sent else GeminiBlocked
                        raise error("gemini_deadline_exceeded")
                    if len(data) > MAX_RESPONSE:
                        raise GeminiBlocked("gemini_response_too_large")
                return bytes(data)
        except httpx.HTTPError:
            error = GeminiUncertain if sent else GeminiBlocked
            reason = "gemini_network_uncertain" if sent else "gemini_check_unavailable"
            raise error(reason) from None

    def _json(self, method, url, **kwargs):
        try:
            value = json.loads(self._request(method, url, **kwargs))
            if not isinstance(value, dict):
                raise ValueError
            return value
        except (ValueError, UnicodeError):
            raise GeminiBlocked("gemini_invalid_response") from None

    def check(self, model=MODEL):
        instant = now()
        if model != MODEL or not REVIEW_START <= instant < REVIEW_END:
            raise GeminiBlocked("gemini_model_not_reviewed")
        cfg = self.config
        if not all(
            isinstance(cfg.get(k), str) and cfg[k]
            for k in ("api_key", "read_token", "project_id", "project_number")
        ):
            raise GeminiBlocked("gemini_not_configured")
        if not re.fullmatch(r"[a-z][a-z0-9-]{4,61}[a-z0-9]", cfg["project_id"]) or not (
            re.fullmatch(r"[1-9][0-9]{0,29}", cfg["project_number"])
        ):
            raise GeminiBlocked("gemini_invalid_project")
        auth = {"Authorization": "Bearer " + cfg["read_token"]}
        parent = "projects/" + cfg["project_number"] + "/locations/global"
        key = self._json(
            "GET",
            "https://apikeys.googleapis.com/v2/keys:lookupKey",
            headers=auth,
            params={"keyString": cfg["api_key"]},
        )
        if (
            key.get("parent") != parent
            or not isinstance(key.get("name"), str)
            or not (key["name"].startswith(parent + "/keys/") and key["name"][len(parent) + 6 :])
        ):
            raise GeminiBlocked("gemini_key_project_unverified")
        project = self._json(
            "GET",
            "https://cloudresourcemanager.googleapis.com/v3/projects/" + cfg["project_number"],
            headers=auth,
        )
        if (
            project.get("name") != "projects/" + cfg["project_number"]
            or project.get("projectId") != cfg["project_id"]
        ):
            raise GeminiBlocked("gemini_project_identity_unverified")
        billing = self._json(
            "GET",
            "https://cloudbilling.googleapis.com/v1/projects/" + cfg["project_id"] + "/billingInfo",
            headers=auth,
        )
        if (
            billing.get("projectId") != cfg["project_id"]
            or billing.get("billingEnabled") is not False
        ):
            raise GeminiBlocked("gemini_billing_not_disabled")
        metadata = self._json(
            "GET",
            "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL,
            headers={"x-goog-api-key": cfg["api_key"]},
        )
        methods = metadata.get("supportedGenerationMethods")
        if (
            metadata.get("name") != "models/" + MODEL
            or not isinstance(methods, list)
            or "generateContent" not in methods
        ):
            raise GeminiBlocked("gemini_model_unavailable")
        pricing = self._request("GET", PRICING_URL).decode("utf-8", errors="replace")
        section = re.search(r"^## Gemini 2\.5 Flash-Lite\b(.*?)(?=^## |\Z)", pricing, re.S | re.M)
        standard = re.search(
            r'{% tab title="Standard" %}(.*?){% /tab %}', section[1] if section else "", re.S
        )
        text = standard[1] if standard else ""
        for feature in (
            "Input price (text, image, video)",
            "Output price (including thinking tokens)",
        ):
            if not re.search(re.escape(feature) + r"\s*\n\s*\* Free of charge\s*\n", text):
                raise GeminiBlocked("gemini_free_price_unverified")
        return {
            "status": "verified",
            "project_key": cfg["project_number"],
            "model": MODEL,
            "verified_at": instant.isoformat(),
            "expires_at": min(instant + timedelta(minutes=5), REVIEW_END).isoformat(),
        }

    def generate(self, role, instructions, context, on_tick, *, authorized=False):
        if authorized is not True:
            raise GeminiBlocked("gemini_authorization_required")
        if role not in {"CEO", "DEV", "DESIGNER", "QA", "PESQUISADOR"} or not (
            isinstance(instructions, str) and isinstance(context, str)
        ):
            raise GeminiBlocked("gemini_invalid_input")
        if len(instructions) > 16000 or len(context) > 64000:
            raise GeminiBlocked("gemini_input_too_large")
        body = {
            "systemInstruction": {"parts": [{"text": instructions + BOUNDARIES}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": json.dumps(
                                {"role": role, "untrusted_context": context}, ensure_ascii=False
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": DraftContent.model_json_schema(),
                "maxOutputTokens": 4096,
                "candidateCount": 1,
            },
        }
        on_tick()
        self.check()
        on_tick()
        response = self._json(
            "POST",
            "https://generativelanguage.googleapis.com/v1beta/models/" + MODEL + ":generateContent",
            headers={"x-goog-api-key": self.config["api_key"]},
            json=body,
        )
        try:
            candidates = response["candidates"]
            if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
                raise ValueError
            parts = candidates[0]["content"]["parts"]
            if any(set(part) != {"text"} for part in parts):
                raise ValueError
            draft = DraftContent.model_validate_json("".join(p["text"] for p in parts))
            usage = response.get("usageMetadata", {})
            return Draft(
                **draft.model_dump(),
                input_tokens=usage.get("promptTokenCount", 0),
                output_tokens=(
                    usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
                ),
            )
        except (KeyError, TypeError, ValueError):
            raise GeminiBlocked("gemini_invalid_draft") from None
