"""Raw MCP tools: categories and category groups resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.enriched.multi_month import compact_category, visible
from mcp_server_for_ynab.history import capture, journal
from mcp_server_for_ynab.models.ynab.categories import (
    SaveCategory,
    SaveCategoryGroup,
    SaveCategoryGroupWrapper,
    SaveCategoryWrapper,
)
from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler
from mcp_server_for_ynab.server.tools.registration import write_tool


def _reg(name: str, classification: str, summary: str) -> None:
    tool_registry.register(name, "categories", classification, "raw", summary)  # type: ignore[arg-type]


_reg("categories_list", "read", "List categories by group. compact=true for a small payload. Supports delta sync.")
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
        "Amounts (budgeted, activity, balance) are in milliunits (1000 = $1.00) and are for the "
        "current month. "
        "compact=true returns only id, group, name, budgeted, activity and balance per category — "
        "about a quarter of the size, and enough to find an id or read the shape of a plan. "
        "include_hidden=true adds hidden categories, which is where YNAB keeps the credit-card "
        "payment categories; deleted categories are never returned. "
        "Note: category group listing is embedded here — YNAB returns categories already grouped. "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def categories_list(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
    compact: bool = False,
    include_hidden: bool = False,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.categories.list(resolved, last_knowledge_of_server=last_knowledge_of_server)

    groups = [g for g in result.data.category_groups if not g.deleted]
    omitted = 0
    kept: list[tuple[Any, list[Any]]] = []
    for group in groups:
        members = visible(group.categories, include_hidden=include_hidden)
        omitted += len(group.categories) - len(members)
        kept.append((group, members))

    if compact:
        return {
            "scope": "categories_list",
            "plan_id": resolved,
            "compact": True,
            "include_hidden": include_hidden,
            "omitted_category_count": omitted,
            "category_count": sum(len(members) for _, members in kept),
            "amounts": "milliunits (1000 = $1.00), current month",
            "server_knowledge": result.data.server_knowledge,
            "groups": [
                {
                    "id": group.id,
                    "name": group.name,
                    "hidden": group.hidden,
                    "categories": [compact_category(c) for c in members],
                }
                for group, members in kept
            ],
        }

    payload = result.model_dump()
    payload["data"]["category_groups"] = [
        {**group.model_dump(), "categories": [c.model_dump() for c in members]} for group, members in kept
    ]
    payload["omitted_category_count"] = omitted
    payload["include_hidden"] = include_hidden
    return payload


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


@write_tool(
    name="categories_create",
    description=(
        "[WRITE] Create a new category inside a category group. "
        "category_group_id is required — get one from categories_list or category_groups_create. "
        "To set the category's budgeted amount, call categories_update_for_month afterwards."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def categories_create(
    name: str,
    category_group_id: str,
    plan_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveCategoryWrapper(category=SaveCategory(name=name, note=note, category_group_id=category_group_id))
    result = await ctx.categories.create(resolved, payload)

    journal.record(
        operation="category_create",
        tool="categories_create",
        plan_id=resolved,
        entity_id=result.data.category.id,
        after={"name": name, "category_group_id": category_group_id},
    )

    return result.model_dump()


@write_tool(
    name="categories_update",
    description=(
        "[WRITE] Update a category's name or note. Only provided fields are updated. "
        "This route cannot change the budgeted amount — YNAB accepts the field and ignores it, "
        "because budgeted amounts are per-month. Use categories_update_for_month instead."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def categories_update(
    category_id: str,
    plan_id: str | None = None,
    name: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveCategoryWrapper(category=SaveCategory(name=name, note=note))

    before = await capture.before_category(ctx, resolved, category_id)
    result = await ctx.categories.update(resolved, category_id, payload)

    requested = {k: v for k, v in {"name": name, "note": note}.items() if v is not None}
    verification = await capture.verify_category(ctx, resolved, category_id, requested)

    entry = journal.record(
        operation="category_update",
        tool="categories_update",
        plan_id=resolved,
        entity_id=category_id,
        before=before,
        after={"name": result.data.category.name, "note": result.data.category.note},
        note=None if before else "No before-state captured; this entry cannot be reverted.",
    )

    return {**result.model_dump(), "history_entry_id": entry.id, "verification": verification}


@write_tool(
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

    before = await capture.before_category_month(ctx, resolved, month, category_id)
    result = await ctx.categories.update_for_month(resolved, month, category_id, payload)
    verification = await capture.verify_category_month(ctx, resolved, month, category_id, budgeted)

    entry = journal.record(
        operation="category_month_budget",
        tool="categories_update_for_month",
        plan_id=resolved,
        entity_id=category_id,
        before=before,
        after={"month": month, "budgeted": result.data.category.budgeted},
        note=None if before else "No before-state captured; this entry cannot be reverted.",
    )

    return {**result.model_dump(), "history_entry_id": entry.id, "verification": verification}


@write_tool(
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

    journal.record(
        operation="category_group_create",
        tool="category_groups_create",
        plan_id=resolved,
        entity_id=result.data.category_group.id,
        after={"name": name},
    )

    return result.model_dump()


@write_tool(
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
    before = await capture.before_category_group(ctx, resolved, category_group_id)
    result = await ctx.categories.update_group(resolved, category_group_id, payload)

    entry = journal.record(
        operation="category_group_update",
        tool="category_groups_update",
        plan_id=resolved,
        entity_id=category_group_id,
        before=before,
        after={"name": result.data.category_group.name},
        note=None if before else "No before-state captured; this entry cannot be reverted.",
    )

    return {**result.model_dump(), "history_entry_id": entry.id}
