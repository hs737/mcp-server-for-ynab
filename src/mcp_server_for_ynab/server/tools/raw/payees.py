"""Raw MCP tools: payees and payee locations resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.history import capture, journal
from mcp_server_for_ynab.models.ynab.payees import SavePayee, SavePayeeWrapper
from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler
from mcp_server_for_ynab.server.tools.registration import write_tool


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
    annotations=ToolAnnotations(read_only_hint=True),
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
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def payees_get(payee_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.payees.get(resolved, payee_id)
    return result.model_dump()


@write_tool(
    name="payees_create",
    description=(
        "[WRITE] Create a new payee. "
        "Note: payee creation was added in YNAB API v1.81.0 (March 26, 2026). "
        "Payees are also created implicitly when you create transactions with a new payee_name."
    ),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
)
@tool_handler
async def payees_create(name: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SavePayeeWrapper(payee=SavePayee(name=name))
    result = await ctx.payees.create(resolved, payload)

    journal.record(
        operation="payee_create",
        tool="payees_create",
        plan_id=resolved,
        entity_id=result.data.payee.id,
        after={"name": name},
    )

    return result.model_dump()


@write_tool(
    name="payees_update",
    description="[WRITE] Update a payee's name.",
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
)
@tool_handler
async def payees_update(payee_id: str, name: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SavePayeeWrapper(payee=SavePayee(name=name))
    before = await capture.before_payee(ctx, resolved, payee_id)
    result = await ctx.payees.update(resolved, payee_id, payload)

    entry = journal.record(
        operation="payee_update",
        tool="payees_update",
        plan_id=resolved,
        entity_id=payee_id,
        before=before,
        after={"name": result.data.payee.name},
        note=None if before else "No before-state captured; this entry cannot be reverted.",
    )

    return {**result.model_dump(), "history_entry_id": entry.id}


# ---------------------------------------------------------------------------
# Payee locations — low priority, geographic data from bank imports
# ---------------------------------------------------------------------------


@mcp.tool(
    name="payee_locations_list",
    description=(
        "[READ] List all payee locations (geographic lat/lon data from bank imports). "
        "Low priority: rarely useful for AI budget workflows."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
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
    annotations=ToolAnnotations(read_only_hint=True),
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
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def payee_locations_list_for_payee(payee_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.payees.list_locations_for_payee(resolved, payee_id)
    return result.model_dump()
