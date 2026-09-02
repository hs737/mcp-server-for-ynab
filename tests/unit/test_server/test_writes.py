"""Unit tests: batch assignment and moving money.

Both tools exist so that one decision is one history entry. The tests are
mostly about what happens when part of that decision fails, because that is the
case where "journaled as one entry" either saves the user or strands them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server_for_ynab.history import journal


@pytest.fixture(autouse=True)
def _isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_HISTORY_PATH", str(tmp_path / "history.jsonl"))


def _category(budgeted: int, *, name: str = "Groceries", balance: int = 0) -> MagicMock:
    response = MagicMock()
    response.data.category.budgeted = budgeted
    response.data.category.name = name
    response.data.category.balance = balance
    return response


@pytest.fixture
def ctx() -> MagicMock:
    context = MagicMock()
    context.settings.resolve_plan_id = lambda p: p or "plan-1"
    context.categories.get_for_month = AsyncMock(return_value=_category(10_000))
    context.categories.update_for_month = AsyncMock(side_effect=lambda *a, **k: _category(a[3].category.budgeted))
    return context


async def _call(ctx: MagicMock, name: str, **kwargs: Any) -> dict[str, Any]:
    import mcp_server_for_ynab.server.tools.writes as module

    with patch.object(module, "get_app_context", return_value=ctx):
        return await getattr(module, name)(**kwargs)


async def test_a_whole_month_is_applied_as_one_history_entry(ctx: MagicMock) -> None:
    result = await _call(
        ctx,
        "months_assign_many",
        month="2026-07",
        assignments=[
            {"category_id": "c1", "budgeted": 50_000},
            {"category_id": "c2", "budgeted": 25_000},
        ],
    )

    assert result["verification"]["applied_count"] == 2
    assert result["total_assigned"] == 75_000
    entries = journal.load()
    assert len(entries) == 1
    assert entries[0].operation == "category_month_budget_batch"
    assert len(entries[0].before) == 2


async def test_a_short_month_form_is_accepted(ctx: MagicMock) -> None:
    result = await _call(ctx, "months_assign_many", month="2026-07", assignments=[{"category_id": "c1", "budgeted": 1}])

    assert result["month"] == "2026-07-01"


async def test_one_failed_line_does_not_abandon_the_others(ctx: MagicMock) -> None:
    async def flaky(_plan: str, _month: str, category_id: str, payload: Any) -> MagicMock:
        if category_id == "bad":
            raise RuntimeError("YNAB said no")
        return _category(payload.category.budgeted)

    ctx.categories.update_for_month = AsyncMock(side_effect=flaky)

    result = await _call(
        ctx,
        "months_assign_many",
        month="2026-07",
        assignments=[
            {"category_id": "c1", "budgeted": 50_000},
            {"category_id": "bad", "budgeted": 25_000},
        ],
    )

    assert result["verification"]["applied_count"] == 1
    assert result["failed"][0]["category_id"] == "bad"
    assert result["verification"]["verified"] is False
    # The line that did land is still revertible.
    assert [state["id"] for state in journal.load()[0].before] == ["c1"]


async def test_a_repeated_category_is_refused_rather_than_guessed(ctx: MagicMock) -> None:
    result = await _call(
        ctx,
        "months_assign_many",
        month="2026-07",
        assignments=[
            {"category_id": "c1", "budgeted": 1_000},
            {"category_id": "c1", "budgeted": 2_000},
        ],
    )

    assert "repeats category_id" in result["error"]["message"]


async def test_a_dollar_amount_is_refused_because_it_would_be_a_thousandth(ctx: MagicMock) -> None:
    result = await _call(
        ctx,
        "months_assign_many",
        month="2026-07",
        assignments=[{"category_id": "c1", "budgeted": 50.0}],
    )

    assert "milliunits" in result["error"]["message"]


async def test_moving_money_adjusts_both_sides_from_their_current_amounts(ctx: MagicMock) -> None:
    result = await _call(
        ctx,
        "money_move",
        month="2026-07",
        amount=4_000,
        from_category_id="c1",
        to_category_id="c2",
    )

    sent = [call.args[3].category.budgeted for call in ctx.categories.update_for_month.await_args_list]
    assert sent == [6_000, 14_000]  # each starts at 10,000
    assert result["verification"]["verified"] is True
    assert len(journal.load()[0].before) == 2


async def test_taking_from_ready_to_assign_writes_one_side(ctx: MagicMock) -> None:
    result = await _call(ctx, "money_move", month="2026-07", amount=4_000, to_category_id="c2")

    assert result["verification"]["sides_written"] == 1
    assert ctx.categories.update_for_month.await_args.args[3].category.budgeted == 14_000


async def test_a_half_written_move_is_journaled_and_says_how_to_undo_it(ctx: MagicMock) -> None:
    """The money has left one category without arriving in the other. Raising
    here would throw away the before-state that is the only way back."""
    calls: list[str] = []

    async def fails_second(_plan: str, _month: str, category_id: str, payload: Any) -> MagicMock:
        calls.append(category_id)
        if len(calls) == 2:
            raise RuntimeError("YNAB said no")
        return _category(payload.category.budgeted)

    ctx.categories.update_for_month = AsyncMock(side_effect=fails_second)

    result = await _call(
        ctx,
        "money_move",
        month="2026-07",
        amount=4_000,
        from_category_id="c1",
        to_category_id="c2",
    )

    assert result["verification"]["verified"] is False
    assert result["verification"]["failed_side"]["side"] == "to"
    assert result["history_entry_id"] in result["verification"]["warning"]
    assert [state["id"] for state in journal.load()[0].before] == ["c1"]


async def test_a_negative_amount_explains_where_direction_comes_from(ctx: MagicMock) -> None:
    result = await _call(ctx, "money_move", month="2026-07", amount=-1_000, to_category_id="c2")

    assert "direction" in result["error"]["message"]


async def test_moving_money_to_and_from_nowhere_is_refused(ctx: MagicMock) -> None:
    result = await _call(ctx, "money_move", month="2026-07", amount=1_000)

    assert "nothing to move" in result["error"]["message"]
