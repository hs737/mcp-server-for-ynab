"""Raw MCP tools: payees and payee locations resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ynab_mcp.models.ynab.payees import SavePayee, SavePayeeWrapper
from ynab_mcp.server.app import mcp
from ynab_mcp.server.context import get_app_context
from ynab_mcp.server.registry import tool_registry
from ynab_mcp.server.tools.boundary import tool_handler


def _reg(name: str, classification: str, summary: str, priority: str = "standard") -> None:
    tool_registry.register(name, "payees", classification, "raw", summary, priority=priority)  # type: ignore[arg-type]


_reg("payees_list", "read", "List all payees. Supports delta sync.")
_reg("payees_get", "read", "Get a single payee by ID.")
_reg("payees_create", "write", "Create a new payee (added in YNAB v1.81.0). [WRITE]")
_reg("payees_update", "write", "Update a payee name. [WRITE]")
_reg("payee_locations_list", "read", "List all payee locations (geographic, low priority).", "low")
_reg("payee_locations_get", "read", "Get a single payee location (geographic, low priority).", "low")
_reg(
    "payee_locations_list_for_payee",
    "read",
    "List locations for a specific payee (geographic, low priority).",
    "low",
)


@mcp.tool(
    name="payees_list",
    description=("[READ] List all payees for a plan. Supports delta sync via last_knowledge_of_server."),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def payees_list(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.payees.list(resolved, last_knowledge_of_server=last_knowledge_of_server)
    return result.model_dump()


@mcp.tool(
    name="payees_get",
    description="[READ] Get a single payee by ID.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def payees_get(payee_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.payees.get(resolved, payee_id)
    return result.model_dump()


@mcp.tool(
    name="payees_create",
    description=(
        "[WRITE] Create a new payee. "
        "Note: payee creation was added in YNAB API v1.81.0 (March 26, 2026). "
        "Payees are also created implicitly when you create transactions with a new payee_name."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def payees_create(name: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SavePayeeWrapper(payee=SavePayee(name=name))
    result = await ctx.payees.create(resolved, payload)
    return result.model_dump()


@mcp.tool(
    name="payees_update",
    description="[WRITE] Update a payee's name.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def payees_update(payee_id: str, name: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SavePayeeWrapper(payee=SavePayee(name=name))
    result = await ctx.payees.update(resolved, payee_id, payload)
    return result.model_dump()


# ---------------------------------------------------------------------------
# Payee locations — low priority, geographic data from bank imports
# ---------------------------------------------------------------------------


@mcp.tool(
    name="payee_locations_list",
    description=(
        "[READ] List all payee locations (geographic lat/lon data from bank imports). "
        "Low priority: rarely useful for AI budget workflows."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def payee_locations_list(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.payees.list_locations(resolved)
    return result.model_dump()


@mcp.tool(
    name="payee_locations_get",
    description=(
        "[READ] Get a single payee location by ID (geographic lat/lon data). "
        "Low priority: rarely useful for AI budget workflows."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def payee_locations_get(payee_location_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.payees.get_location(resolved, payee_location_id)
    return result.model_dump()


@mcp.tool(
    name="payee_locations_list_for_payee",
    description=(
        "[READ] List all locations for a specific payee (geographic lat/lon data). "
        "Low priority: rarely useful for AI budget workflows."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def payee_locations_list_for_payee(payee_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.payees.list_locations_for_payee(resolved, payee_id)
    return result.model_dump()
