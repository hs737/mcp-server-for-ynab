"""Unit tests: months_get parameter handling.

The month forms and the hidden-category default are the two things a caller can
get wrong silently, so both are pinned here rather than left to the description.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.unit.test_enriched.builders import category, month, month_summary, months_list_response


@pytest.fixture
def ctx() -> MagicMock:
    context = MagicMock()
    context.settings.resolve_plan_id = lambda p: p or "plan-1"
    context.months.get = AsyncMock()
    return context


async def _get(ctx: MagicMock, **kwargs: Any) -> dict[str, Any]:
    import mcp_server_for_ynab.server.tools.raw.months as module

    with patch.object(module, "get_app_context", return_value=ctx):
        return await module.months_get(**kwargs)


async def test_a_short_month_is_normalized_before_it_reaches_ynab(ctx: MagicMock) -> None:
    """YNAB answers a bare '2026-07' with a 404 that says only 'Resource not
    found', so the normalisation has to happen on this side."""
    ctx.months.get.return_value = month(month="2026-07-01")

    await _get(ctx, month="2026-07")

    assert ctx.months.get.await_args.args[1] == "2026-07-01"


async def test_hidden_categories_are_omitted_but_counted(ctx: MagicMock) -> None:
    ctx.months.get.return_value = month(categories=[category(id="c1"), category(id="cc", name="Visa", hidden=True)])

    result = await _get(ctx, month="2026-07-01", compact=True)

    assert result["category_count"] == 1
    assert result["omitted_category_count"] == 1


async def test_the_full_form_keeps_every_field_of_the_categories_it_returns(ctx: MagicMock) -> None:
    ctx.months.get.return_value = month(categories=[category(id="c1", goal_under_funded=5_000)])

    result = await _get(ctx, month="2026-07-01")

    stored = result["data"]["month"]["categories"][0]
    assert stored["goal_under_funded"] == 5_000
    assert stored["note"] is None


async def _list(ctx: MagicMock, **kwargs: Any) -> dict[str, Any]:
    import mcp_server_for_ynab.server.tools.raw.months as module

    with patch.object(module, "get_app_context", return_value=ctx):
        return await module.months_list(**kwargs)


def _summary(month_stamp: str, *, income: int = 0, budgeted: int = 0, activity: int = 0) -> Any:
    summary = month_summary(month=month_stamp, budgeted=budgeted)
    summary.income = income
    summary.activity = activity
    return summary


async def test_months_before_the_plan_began_are_left_out(ctx: MagicMock) -> None:
    """YNAB keeps records for months the app's own picker hides, sometimes with a
    stray assignment, and a review that starts there starts before the budget did."""
    ctx.months.list = AsyncMock(
        return_value=months_list_response(
            _summary("2024-08-01", budgeted=500_000),
            _summary("2026-07-01", income=400_000, activity=-350_000),
        )
    )

    result = await _list(ctx)

    assert [m["month"] for m in result["data"]["months"]] == ["2026-07-01"]
    assert result["omitted_month_count"] == 1


async def test_include_empty_returns_them_again(ctx: MagicMock) -> None:
    ctx.months.list = AsyncMock(
        return_value=months_list_response(
            _summary("2024-08-01", budgeted=500_000),
            _summary("2026-07-01", income=400_000),
        )
    )

    result = await _list(ctx, include_empty=True)

    assert len(result["data"]["months"]) == 2


async def test_a_month_with_activity_but_no_income_is_kept(ctx: MagicMock) -> None:
    ctx.months.list = AsyncMock(return_value=months_list_response(_summary("2026-07-01", activity=-1_000)))

    result = await _list(ctx)

    assert len(result["data"]["months"]) == 1
