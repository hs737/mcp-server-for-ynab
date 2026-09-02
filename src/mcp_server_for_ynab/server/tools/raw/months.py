"""Raw MCP tools: months resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.enriched.multi_month import (
    MAX_RANGE_MONTHS,
    compact_category,
    month_totals,
    normalize_month,
    visible,
)
from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler


def _reg(name: str, summary: str) -> None:
    tool_registry.register(name, "months", "read", "raw", summary)


_reg("months_list", "List all budget months (summaries). Supports delta sync.")
_reg("months_get", "Get one month's categories. compact=true for a small payload.")


@mcp.tool(
    name="months_list",
    description=(
        "[READ] List all budget months with summary data (income, budgeted, activity, "
        "to_be_budgeted). Amounts are in milliunits (1000 = $1.00). "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def months_list(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.months.list(resolved, last_knowledge_of_server=last_knowledge_of_server)
    return result.model_dump()


@mcp.tool(
    name="months_get",
    description=(
        "[READ] Get one month's categories with their budgeted, activity, and balance. "
        "month: ISO date for the first day of the month ('2024-01-01'), 'YYYY-MM', or 'current'. "
        "compact=true returns only id, group, name, budgeted, activity and balance per category — "
        "about a quarter of the size, and enough for any month-over-month review. Use the full form "
        "only when you need goal fields or notes. "
        "include_hidden=true adds hidden categories, which is where YNAB keeps the credit-card "
        "payment categories; deleted categories are never returned. "
        f"To compare several months, use months_range instead (up to {MAX_RANGE_MONTHS} months in one call). "
        "Amounts are in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def months_get(
    month: str,
    plan_id: str | None = None,
    compact: bool = False,
    include_hidden: bool = False,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    # YNAB's route accepts only a full first-of-month date and answers a bare
    # '2026-07' with a 404 that says "Resource not found" and nothing about the
    # format. Normalising here is what makes the month forms the range tools
    # accept work on this one too.
    result = await ctx.months.get(resolved, normalize_month(month))

    data = result.data.month
    kept = visible(data.categories, include_hidden=include_hidden)
    omitted = len(data.categories) - len(kept)

    if compact:
        return {
            "scope": "months_get",
            "plan_id": resolved,
            "compact": True,
            "include_hidden": include_hidden,
            "omitted_category_count": omitted,
            "category_count": len(kept),
            "amounts": "milliunits (1000 = $1.00)",
            "month": month_totals(data),
            "categories": [compact_category(c) for c in kept],
        }

    payload = result.model_dump()
    payload["data"]["month"]["categories"] = [c.model_dump() for c in kept]
    payload["omitted_category_count"] = omitted
    payload["include_hidden"] = include_hidden
    return payload
