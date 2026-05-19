"""Raw MCP tools: money movements resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ynab_mcp.server.app import mcp
from ynab_mcp.server.context import get_app_context
from ynab_mcp.server.registry import tool_registry


def _reg(name: str, summary: str) -> None:
    tool_registry.register(name, "money_movements", "read", "raw", summary)


_reg("money_movements_list", "List all money movements. Supports delta sync.")
_reg("money_movements_list_by_month", "List money movements for a specific month.")
_reg("money_movement_groups_list", "List money movement groups. Supports delta sync.")
_reg("money_movement_groups_list_by_month", "List money movement groups for a specific month.")


@mcp.tool(
    name="money_movements_list",
    description=(
        "[READ] List all money movements for a plan. "
        "Amounts are in milliunits (1000 = $1.00). "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
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
        "[READ] List money movements for a specific month. "
        "month: ISO date string for the first day of the month (e.g. '2024-01-01'). "
        "Amounts are in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
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
        "[READ] List money movement groups for a plan. "
        "Amounts are in milliunits (1000 = $1.00). "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
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
        "[READ] List money movement groups for a specific month. "
        "month: ISO date string for the first day of the month (e.g. '2024-01-01'). "
        "Amounts are in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
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
