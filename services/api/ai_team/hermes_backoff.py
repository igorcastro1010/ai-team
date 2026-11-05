"""Conservative admission cooldown. No automatic retry or blocking sleep."""

import math
import time
from email.utils import parsedate_to_datetime


class HermesRateLimitError(RuntimeError):
    def __init__(self, message="Cota do provedor Hermes indisponível", *, retry_after=60):
        super().__init__(message)
        self.retry_after = retry_after
        self.recorded = False


def retry_delay(value=None, failures=1, now=None):
    now = time.time() if now is None else now
    fallback = min(60 * 2 ** min(max(failures - 1, 0), 6), 3600)
    try:
        if value is not None and str(value).isascii() and str(value).isdigit():
            seconds = int(value)
        else:
            date = parsedate_to_datetime(value or "")
            if date.tzinfo is None:
                raise ValueError("Retry-After sem fuso")
            seconds = date.timestamp() - now
        return max(fallback, math.ceil(seconds))
    except (ValueError, TypeError, OverflowError):
        return fallback


class HermesBackoff:
    def __init__(self):
        self.failures = 0
        self.until = 0

    def check(self):
        remaining = math.ceil(self.until - time.time())
        if remaining > 0:
            raise HermesRateLimitError(retry_after=remaining)

    def record(self, retry_after=None):
        self.failures += 1
        seconds = retry_delay(retry_after, self.failures)
        self.until = max(self.until, time.time() + seconds)
        return seconds
