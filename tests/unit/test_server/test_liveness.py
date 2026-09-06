"""Unit tests: ping, and the request-budget trailer on every response.

Both exist for the same moment: an agent that has been rate limited, has
scheduled itself to come back, and needs to know whether the server is still
there — without spending the quota it is waiting on to find out.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server_for_ynab.http_client.rate_budget import RateBudget
from tests.unit.test_enriched.builders import account_response


def _ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.settings.resolve_plan_id = lambda p: p or "plan-1"
    ctx.http.budget = RateBudget(limit=100)
    ctx.accounts.get = AsyncMock(return_value=account_response())
    return ctx


async def _ping(ctx: MagicMock) -> dict[str, Any]:
    import mcp_server_for_ynab.server.tools.enriched as module

    with patch.object(module, "get_app_context", return_value=ctx):
        return await module.ping()


async def test_ping_answers_without_touching_ynab() -> None:
    ctx = _ctx()

    result = await _ping(ctx)

    assert result["ok"] is True
    assert result["ynab_requests_spent_by_this_call"] == 0
    assert ctx.http.budget.used() == 0


async def test_ping_reports_the_version_and_whether_writes_are_registered() -> None:
    result = await _ping(_ctx())

    assert result["version"]
    assert result["writes_enabled"] in (True, False)


async def test_ping_still_answers_when_no_ynab_context_is_bound() -> None:
    """A server with no credentials bound is still a server that is up."""
    import mcp_server_for_ynab.server.tools.enriched as module

    with patch.object(module, "get_app_context", side_effect=RuntimeError("not initialized")):
        result = await module.ping()

    assert result["ok"] is True
    assert "requests_note" in result


async def test_every_tool_response_carries_what_is_left_of_the_hour() -> None:
    from mcp_server_for_ynab.server.tools.boundary import tool_handler

    ctx = _ctx()
    ctx.http.budget.record()

    @tool_handler
    async def some_tool() -> dict[str, Any]:
        return {"scope": "anything"}

    with patch("mcp_server_for_ynab.server.context.get_app_context", return_value=ctx):
        result = await some_tool()

    assert result["requests_used_this_hour"] == 1
    assert result["requests_remaining"] == 99


async def test_a_failure_carries_the_budget_too() -> None:
    """The call that just failed is exactly when the remaining count matters."""
    from mcp_server_for_ynab.models.errors import YnabMcpError, YnabMcpException
    from mcp_server_for_ynab.server.tools.boundary import tool_handler

    ctx = _ctx()

    @tool_handler
    async def failing_tool() -> dict[str, Any]:
        raise YnabMcpException(YnabMcpError.rate_limited(retry_after=658))

    with patch("mcp_server_for_ynab.server.context.get_app_context", return_value=ctx):
        result = await failing_tool()

    assert result["error"]["retry_at"] is not None
    assert result["requests_remaining"] == 100


@pytest.mark.parametrize("adjust_by,expected", [(45_000, 55_000), (-4_000, 6_000)])
async def test_a_single_category_can_be_adjusted_by_a_delta(adjust_by: int, expected: int) -> None:
    """The caller is spared a read; the write itself is still read-modify-write."""
    import mcp_server_for_ynab.server.tools.raw.categories as module

    ctx = _ctx()
    current = MagicMock()
    current.data.category.id = "c1"
    current.data.category.budgeted = 10_000
    ctx.categories.get_for_month = AsyncMock(return_value=current)

    written = MagicMock()
    written.data.category.budgeted = expected
    written.model_dump = lambda: {"data": {"category": {"budgeted": expected}}}
    ctx.categories.update_for_month = AsyncMock(return_value=written)

    with patch.object(module, "get_app_context", return_value=ctx):
        result = await module.categories_update_for_month(month="2026-07-01", category_id="c1", adjust_by=adjust_by)

    assert ctx.categories.update_for_month.await_args.args[3].category.budgeted == expected
    assert result["previous_budgeted"] == 10_000
    assert result["change"] == adjust_by


async def test_setting_both_a_total_and_a_delta_is_refused() -> None:
    import mcp_server_for_ynab.server.tools.raw.categories as module

    with patch.object(module, "get_app_context", return_value=_ctx()):
        result = await module.categories_update_for_month(month="2026-07-01", category_id="c1", budgeted=1, adjust_by=1)

    assert "Both were given" in result["error"]["message"]


async def test_a_single_category_write_is_refused_when_the_amount_moved_under_it() -> None:
    """A comparison before the write, not a precondition on it — it stops a
    caller working from a stale figure, and nothing more."""
    import mcp_server_for_ynab.server.tools.raw.categories as module

    ctx = _ctx()
    current = MagicMock()
    current.data.category.id = "c1"
    current.data.category.budgeted = 10_000
    ctx.categories.get_for_month = AsyncMock(return_value=current)
    ctx.categories.update_for_month = AsyncMock()

    with patch.object(module, "get_app_context", return_value=ctx):
        result = await module.categories_update_for_month(
            month="2026-07-01", category_id="c1", adjust_by=4_500, expected_budgeted=9_000
        )

    assert result["error"]["error_type"] == "conflict"
    assert result["error"]["details"]["budgeted"] == 10_000
    ctx.categories.update_for_month.assert_not_awaited()
