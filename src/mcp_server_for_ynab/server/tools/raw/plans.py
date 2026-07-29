"""Raw MCP tools: plans (budgets) resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler


def _reg(name: str, classification: str, summary: str) -> None:
    tool_registry.register(name, "plans", classification, "raw", summary)  # type: ignore[arg-type]


_reg("plans_list", "read", "List all YNAB plans (budgets).")
_reg("plans_get", "read", "Get a single plan with full detail. Supports delta sync.")
_reg("plans_get_settings", "read", "Get plan settings (currency/date format). Narrow in value.")


@mcp.tool(
    name="plans_list",
    description="[READ] List all YNAB plans (budgets) available to the authenticated user.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def plans_list() -> dict[str, Any]:
    ctx = get_app_context()
    result = await ctx.plans.list()
    return result.model_dump()


@mcp.tool(
    name="plans_get",
    description=(
        "[READ] Get a single plan with full account, category, and month data. "
        "Pass last_knowledge_of_server for delta sync — only changed data is returned. "
        "The response includes server_knowledge for use in the next delta request."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def plans_get(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.plans.get(resolved, last_knowledge_of_server=last_knowledge_of_server)
    return result.model_dump()


@mcp.tool(
    name="plans_get_settings",
    description=(
        "[READ] Get plan settings including currency format and date format. "
        "Note: this endpoint is intentionally narrow — it returns formatting preferences "
        "only, not budget data."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def plans_get_settings(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.plans.get_settings(resolved)
    return result.model_dump()
