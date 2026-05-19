"""Raw MCP tools: categories and category groups resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ynab_mcp.models.ynab.categories import (
    SaveCategory,
    SaveCategoryGroup,
    SaveCategoryGroupWrapper,
    SaveCategoryWrapper,
)
from ynab_mcp.server.app import mcp
from ynab_mcp.server.context import get_app_context
from ynab_mcp.server.registry import tool_registry
from ynab_mcp.server.tools.boundary import tool_handler


def _reg(name: str, classification: str, summary: str) -> None:
    tool_registry.register(name, "categories", classification, "raw", summary)  # type: ignore[arg-type]


_reg("categories_list", "read", "List all categories grouped by category group. Supports delta sync.")
_reg("categories_get", "read", "Get a single category by ID.")
_reg("categories_get_for_month", "read", "Get a category's budgeted/activity/balance for a specific month.")
_reg("categories_create", "write", "Create a new category. [WRITE]")
_reg("categories_update", "write", "Update a category. [WRITE]")
_reg(
    "categories_update_for_month",
    "write",
    "Update a category's budgeted amount for a specific month. [WRITE]",
)
_reg("category_groups_create", "write", "Create a new category group. [WRITE]")
_reg("category_groups_update", "write", "Update a category group. [WRITE]")


@mcp.tool(
    name="categories_list",
    description=(
        "[READ] List all categories grouped by category group. "
        "Amounts (budgeted, activity, balance) are in milliunits (1000 = $1.00). "
        "Note: category group listing is embedded here — YNAB returns categories already grouped. "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def categories_list(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.categories.list(resolved, last_knowledge_of_server=last_knowledge_of_server)
    return result.model_dump()


@mcp.tool(
    name="categories_get",
    description="[READ] Get a single category by ID. Amounts are in milliunits (1000 = $1.00).",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def categories_get(category_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.categories.get(resolved, category_id)
    return result.model_dump()


@mcp.tool(
    name="categories_get_for_month",
    description=(
        "[READ] Get a category's budgeted, activity, and balance for a specific month. "
        "month: ISO date string for the first day of the month (e.g. '2024-01-01'). "
        "Amounts are in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def categories_get_for_month(
    month: str,
    category_id: str,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.categories.get_for_month(resolved, month, category_id)
    return result.model_dump()


@mcp.tool(
    name="categories_create",
    description="[WRITE] Create a new category. budgeted amount is in milliunits (1000 = $1.00).",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def categories_create(
    name: str,
    plan_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveCategoryWrapper(category=SaveCategory(name=name, note=note))
    result = await ctx.categories.create(resolved, payload)
    return result.model_dump()


@mcp.tool(
    name="categories_update",
    description=(
        "[WRITE] Update a category. budgeted amount is in milliunits (1000 = $1.00). Only provided fields are updated."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def categories_update(
    category_id: str,
    plan_id: str | None = None,
    name: str | None = None,
    note: str | None = None,
    budgeted: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveCategoryWrapper(category=SaveCategory(name=name, note=note, budgeted=budgeted))
    result = await ctx.categories.update(resolved, category_id, payload)
    return result.model_dump()


@mcp.tool(
    name="categories_update_for_month",
    description=(
        "[WRITE] Update a category's budgeted amount for a specific month. "
        "month: ISO date string for the first day of the month (e.g. '2024-01-01'). "
        "budgeted is in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def categories_update_for_month(
    month: str,
    category_id: str,
    budgeted: int,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveCategoryWrapper(category=SaveCategory(budgeted=budgeted))
    result = await ctx.categories.update_for_month(resolved, month, category_id, payload)
    return result.model_dump()


@mcp.tool(
    name="category_groups_create",
    description="[WRITE] Create a new category group.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def category_groups_create(name: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveCategoryGroupWrapper(category_group=SaveCategoryGroup(name=name))
    result = await ctx.categories.create_group(resolved, payload)
    return result.model_dump()


@mcp.tool(
    name="category_groups_update",
    description=("[WRITE] Update a category group. Note: YNAB does not support deleting category groups via the API."),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def category_groups_update(
    category_group_id: str,
    name: str,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveCategoryGroupWrapper(category_group=SaveCategoryGroup(name=name))
    result = await ctx.categories.update_group(resolved, category_group_id, payload)
    return result.model_dump()
