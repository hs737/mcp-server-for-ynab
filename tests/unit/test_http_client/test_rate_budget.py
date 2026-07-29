"""Unit tests: the client-side request budget."""

from __future__ import annotations

import pytest

from mcp_server_for_ynab.http_client.rate_budget import (
    WINDOW_SECONDS,
    YNAB_HOURLY_LIMIT,
    RateBudget,
)


def test_default_budget_sits_below_ynabs_limit() -> None:
    """Ours must run out first, where the error is local and clear."""
    budget = RateBudget()
    assert budget.limit < YNAB_HOURLY_LIMIT


def test_requests_count_against_the_budget() -> None:
    budget = RateBudget(limit=10)
    for i in range(3):
        budget.record(now=i)

    assert budget.used(now=3) == 3
    assert budget.remaining(now=3) == 7


def test_requests_leave_the_rolling_window() -> None:
    budget = RateBudget(limit=10)
    budget.record(now=0)
    budget.record(now=10)

    assert budget.used(now=WINDOW_SECONDS + 5) == 1  # the first has aged out
    assert budget.remaining(now=WINDOW_SECONDS + 5) == 9


def test_budget_reports_when_it_is_running_low() -> None:
    budget = RateBudget(limit=10, warn_threshold=3)
    for i in range(7):
        budget.record(now=i)

    assert budget.is_low(now=7) is True
    assert "3 of 10 requests left" in str(budget.status(now=7)["warning"])


def test_no_warning_while_there_is_headroom() -> None:
    budget = RateBudget(limit=10, warn_threshold=3)
    budget.record(now=0)

    assert budget.is_low(now=1) is False
    assert "warning" not in budget.status(now=1)


def test_exhausted_budget_says_when_a_slot_frees_up() -> None:
    budget = RateBudget(limit=2, warn_threshold=1)
    budget.record(now=0)
    budget.record(now=1)

    status = budget.status(now=2)
    assert status["remaining"] == 0
    assert "exhausted" in str(status["warning"])
    assert budget.seconds_until_next_slot(now=2) == pytest.approx(WINDOW_SECONDS - 2 + 1, abs=1)


def test_remaining_never_goes_negative() -> None:
    budget = RateBudget(limit=2)
    for i in range(5):
        budget.record(now=i)

    assert budget.remaining(now=5) == 0


def test_limit_can_be_configured_by_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_RATE_LIMIT_PER_HOUR", "42")
    assert RateBudget().limit == 42


@pytest.mark.parametrize("value", ["nonsense", "0", "-5", ""])
def test_a_bad_limit_falls_back_to_the_default(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("YNAB_RATE_LIMIT_PER_HOUR", value)
    assert RateBudget().limit == RateBudget(limit=None).limit > 0
