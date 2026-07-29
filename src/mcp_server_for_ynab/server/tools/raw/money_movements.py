"""Raw MCP tools: money movements resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler


def _reg(name: str, summary: str) -> None:
    tool_registry.register(name, "money_movements", "read", "raw", summary)


_reg("money_movements_list", "List all category-to-category fund moves. Supports delta sync.")
_reg("money_movements_list_by_month", "List category-to-category fund moves for a specific month.")
_reg("money_movement_groups_list", "List money movement groups. Supports delta sync.")
_reg("money_movement_groups_list_by_month", "List money movement groups for a specific month.")


@mcp.tool(
    name="money_movements_list",
    description=(
        "[READ] List all money movements for a plan. A money movement is budgeted funds moved "
        "between categories within a month — it is not a transaction and has no payee or account. "
        "A null from_category_id or to_category_id means Ready to Assign. "
        "Amounts are in milliunits (1000 = $1.00). "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def money_movements_list(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.money_movements.list(resolved, last_knowledge_of_server=last_knowledge_of_server)
    return result.model_dump()


@mcp.tool(
    name="money_movements_list_by_month",
    description=(
        "[READ] List money movements (budgeted funds moved between categories) for a specific month. "
        "month: ISO date string for the first day of the month (e.g. '2024-01-01'). "
        "A null from_category_id or to_category_id means Ready to Assign. "
        "Amounts are in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def money_movements_list_by_month(
    month: str,
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.money_movements.list_by_month(resolved, month, last_knowledge_of_server=last_knowledge_of_server)
    return result.model_dump()


@mcp.tool(
    name="money_movement_groups_list",
    description=(
        "[READ] List money movement groups for a plan. A group ties together the movements made "
        "in a single action; it carries no amount of its own. Join movements to a group on "
        "money_movement_group_id. "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def money_movement_groups_list(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.money_movements.list_groups(resolved, last_knowledge_of_server=last_knowledge_of_server)
    return result.model_dump()


@mcp.tool(
    name="money_movement_groups_list_by_month",
    description=(
        "[READ] List money movement groups for a specific month. A group ties together the "
        "movements made in a single action; it carries no amount of its own. "
        "month: ISO date string for the first day of the month (e.g. '2024-01-01')."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def money_movement_groups_list_by_month(
    month: str,
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.money_movements.list_groups_by_month(
        resolved, month, last_knowledge_of_server=last_knowledge_of_server
    )
    return result.model_dump()
