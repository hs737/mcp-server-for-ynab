"""Raw MCP tools: months resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler


def _reg(name: str, summary: str) -> None:
    tool_registry.register(name, "months", "read", "raw", summary)


_reg("months_list", "List all budget months (summaries). Supports delta sync.")
_reg("months_get", "Get full month data including all categories.")


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
        "[READ] Get full month data including all categories with their budgeted/activity/balance. "
        "month: ISO date string for the first day of the month (e.g. '2024-01-01'). "
        "Use 'current' as a convenience alias for the current month. "
        "Amounts are in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def months_get(month: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.months.get(resolved, month)
    return result.model_dump()
