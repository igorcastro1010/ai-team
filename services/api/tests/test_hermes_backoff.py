"""Retry-After gates future requests; it never retries an inference."""

from datetime import UTC, datetime
from email.utils import format_datetime

import httpx
import pytest

from ai_team.config import Settings
from ai_team.hermes import HermesClient, HermesRateLimitError
from ai_team.hermes_backoff import retry_delay


def test_retry_after_seconds_date_and_exponential_fallback():
    now = 1793877000
    date = format_datetime(datetime.fromtimestamp(now + 240, UTC), usegmt=True)
    assert retry_delay("120", 1, now) == 120
    assert retry_delay(date, 1, now) == 240
    assert retry_delay("invalid", 1, now) == 60
    assert retry_delay(None, 2, now) == 120
    assert retry_delay(None, 100, now) == 3600
    assert retry_delay("0", 1, now) == 60


@pytest.mark.parametrize("method,path", [("POST", "/v1/runs"), ("GET", "/v1/runs/run_test")])
def test_http_429_honors_retry_after_without_repeating_request(method, path):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(429, headers={"Retry-After": "120"}, text="private-provider-data")

    client = HermesClient(Settings(hermes_url="http://hermes:8642", hermes_key="x" * 40),
                          transport=httpx.MockTransport(handler))
    with pytest.raises(HermesRateLimitError) as error:
        client.request(method, path)
    assert error.value.retry_after >= 120
    assert "private-provider-data" not in str(error.value)
    with pytest.raises(HermesRateLimitError):
        client.request(method, path)
    assert calls == [path]
