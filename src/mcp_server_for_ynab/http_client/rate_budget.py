"""Client-side request budget for the YNAB API.

YNAB allows 200 requests per hour per token, in a rolling window. Retrying after
a 429 is recovery; this is avoidance. It matters because a single enriched tool
can spend five or six requests, so an agent working through a budget review can
exhaust the hour without anything obviously going wrong — the failures arrive
later, in the middle of something else.

The budget is deliberately set below YNAB's limit so the first thing to run out
is ours, where the error is clear and local, rather than theirs.
"""

from __future__ import annotations

import os
import time
from collections import deque

YNAB_HOURLY_LIMIT = 200
DEFAULT_BUDGET = 190
DEFAULT_WARN_THRESHOLD = 50
WINDOW_SECONDS = 3600


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class RateBudget:
    """Tracks requests in a rolling hour and reports what is left."""

    def __init__(self, limit: int | None = None, warn_threshold: int | None = None) -> None:
        self.limit = limit if limit is not None else _int_env("YNAB_RATE_LIMIT_PER_HOUR", DEFAULT_BUDGET)
        self.warn_threshold = (
            warn_threshold
            if warn_threshold is not None
            else _int_env("YNAB_RATE_WARN_THRESHOLD", DEFAULT_WARN_THRESHOLD)
        )
        self._timestamps: deque[float] = deque()

    def _prune(self, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    def record(self, now: float | None = None) -> None:
        """Count one request against the budget."""
        moment = time.monotonic() if now is None else now
        self._prune(moment)
        self._timestamps.append(moment)

    def used(self, now: float | None = None) -> int:
        moment = time.monotonic() if now is None else now
        self._prune(moment)
        return len(self._timestamps)

    def remaining(self, now: float | None = None) -> int:
        return max(0, self.limit - self.used(now))

    def is_low(self, now: float | None = None) -> bool:
        return self.remaining(now) <= self.warn_threshold

    def seconds_until_next_slot(self, now: float | None = None) -> int:
        """How long until the oldest request leaves the rolling window."""
        moment = time.monotonic() if now is None else now
        self._prune(moment)
        if not self._timestamps:
            return 0
        return max(0, int(WINDOW_SECONDS - (moment - self._timestamps[0])) + 1)

    def status(self, now: float | None = None) -> dict[str, object]:
        moment = time.monotonic() if now is None else now
        remaining = self.remaining(moment)
        status: dict[str, object] = {
            "limit": self.limit,
            "used": self.used(moment),
            "remaining": remaining,
            "window_seconds": WINDOW_SECONDS,
            "ynab_hourly_limit": YNAB_HOURLY_LIMIT,
        }
        if remaining == 0:
            status["warning"] = (
                f"Local request budget exhausted. The oldest request leaves the rolling hour in "
                f"{self.seconds_until_next_slot(moment)}s. Pause before continuing."
            )
        elif self.is_low(moment):
            status["warning"] = (
                f"{remaining} of {self.limit} requests left this hour. "
                "Prefer enriched tools over many raw calls, and pass since_date to narrow reads."
            )
        return status
