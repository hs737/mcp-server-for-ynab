"""Client-side request budget for the YNAB API.

YNAB allows 200 requests per hour per token, in a rolling window. Retrying after
a 429 is recovery; this is avoidance. It matters because a single enriched tool
can spend five or six requests, so an agent working through a budget review can
exhaust the hour without anything obviously going wrong — the failures arrive
later, in the middle of something else.

The budget is deliberately set below YNAB's limit so the first thing to run out
is ours, where the error is clear and local, rather than theirs.

Two things follow from the window belonging to YNAB rather than to us. The count
here is what *this server* spent, while the user's own YNAB apps draw on the same
per-token quota — so the real remaining figure can be lower than the one reported,
never higher, which is the direction that matters. And a caller can only pace
itself against a number it can see, which is why `trailer()` rides along on every
tool response instead of waiting to be asked for.
"""

from __future__ import annotations

import os
import time
from collections import deque

from mcp_server_for_ynab.models.errors import retry_at

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

    def trailer(self, now: float | None = None) -> dict[str, object]:
        """The two numbers a caller needs to pace itself, small enough to ride along.

        The tool boundary attaches this to every response, the way an HTTP API
        returns X-RateLimit-Remaining: an agent throttles itself if it can see
        the number, and cannot if seeing it costs another call.
        """
        moment = time.monotonic() if now is None else now
        trailer: dict[str, object] = {
            "requests_used_this_hour": self.used(moment),
            "requests_remaining": self.remaining(moment),
        }
        if self.is_low(moment):
            trailer["requests_warning"] = str(self.status(moment).get("warning"))
        return trailer

    def status(self, now: float | None = None) -> dict[str, object]:
        moment = time.monotonic() if now is None else now
        remaining = self.remaining(moment)
        status: dict[str, object] = {
            "limit": self.limit,
            "used": self.used(moment),
            "remaining": remaining,
            "window_seconds": WINDOW_SECONDS,
            "ynab_hourly_limit": YNAB_HOURLY_LIMIT,
            "shared_quota_note": (
                "This counts what this server spent. YNAB's limit is per access token and the same "
                "token is used by your own YNAB apps, so the real remaining figure can be lower."
            ),
        }
        if remaining == 0:
            wait = self.seconds_until_next_slot(moment)
            status["warning"] = (
                f"Local request budget exhausted. The oldest request leaves the rolling hour in "
                f"{wait}s. Pause before continuing."
            )
            status["retry_at"] = retry_at(wait)
        elif self.is_low(moment):
            status["warning"] = (
                f"{remaining} of {self.limit} requests left this hour. "
                "Prefer enriched tools over many raw calls, and pass since_date to narrow reads."
            )
        return status
