"""Raw MCP tools: scheduled transactions resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.history import capture, journal
from mcp_server_for_ynab.models.ynab.scheduled_transactions import (
    Frequency,
    SaveScheduledTransaction,
    SaveScheduledTransactionWrapper,
)
from mcp_server_for_ynab.models.ynab.transactions import FlagColor
from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler
from mcp_server_for_ynab.server.tools.registration import write_tool


def _reg(name: str, classification: str, summary: str) -> None:
    tool_registry.register(name, "scheduled_transactions", classification, "raw", summary)  # type: ignore[arg-type]


_reg("scheduled_transactions_list", "read", "List scheduled transactions. Supports delta sync.")
_reg("scheduled_transactions_get", "read", "Get a single scheduled transaction.")
_reg("scheduled_transactions_create", "write", "Create a scheduled transaction. [WRITE]")
_reg("scheduled_transactions_update", "write", "Update a scheduled transaction. [WRITE]")
_reg("scheduled_transactions_delete", "write", "Delete a scheduled transaction. [WRITE]")


@mcp.tool(
    name="scheduled_transactions_list",
    description=(
        "[READ] List all scheduled transactions for a plan. "
        "Includes date_next (next occurrence) for each. "
        "Amounts are in milliunits (1000 = $1.00). "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def scheduled_transactions_list(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.scheduled_transactions.list(resolved, last_knowledge_of_server=last_knowledge_of_server)
    return result.model_dump()


@mcp.tool(
    name="scheduled_transactions_get",
    description=("[READ] Get a single scheduled transaction by ID. Amount is in milliunits (1000 = $1.00)."),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def scheduled_transactions_get(scheduled_transaction_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.scheduled_transactions.get(resolved, scheduled_transaction_id)
    return result.model_dump()


@write_tool(
    name="scheduled_transactions_create",
    description=(
        "[WRITE] Create a scheduled transaction. "
        "amount: milliunits (1000 = $1.00). Negative for outflow, positive for inflow. "
        "date: ISO date string for the first occurrence (e.g. '2024-01-15'). "
        "frequency: never, daily, weekly, everyOtherWeek, twiceAMonth, every4Weeks, "
        "monthly, everyOtherMonth, every3Months, every4Months, twiceAYear, yearly, everyOtherYear."
    ),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
)
@tool_handler
async def scheduled_transactions_create(
    account_id: str,
    date: str,
    frequency: str,
    amount: int,
    plan_id: str | None = None,
    payee_id: str | None = None,
    payee_name: str | None = None,
    category_id: str | None = None,
    memo: str | None = None,
    flag_color: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveScheduledTransactionWrapper(
        scheduled_transaction=SaveScheduledTransaction(
            account_id=account_id,
            date=date,
            frequency=Frequency(frequency),
            amount=amount,
            payee_id=payee_id,
            payee_name=payee_name,
            category_id=category_id,
            memo=memo,
            flag_color=FlagColor(flag_color) if flag_color else None,
        )
    )
    result = await ctx.scheduled_transactions.create(resolved, payload)

    entry = journal.record(
        operation="scheduled_create",
        tool="scheduled_transactions_create",
        plan_id=resolved,
        entity_id=result.data.scheduled_transaction.id,
        after=capture._slice(result.data.scheduled_transaction, capture.SCHEDULED_FIELDS),
    )

    return {**result.model_dump(), "history_entry_id": entry.id}


@write_tool(
    name="scheduled_transactions_update",
    description=("[WRITE] Update a scheduled transaction. amount: milliunits (1000 = $1.00)."),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
)
@tool_handler
async def scheduled_transactions_update(
    scheduled_transaction_id: str,
    account_id: str,
    date: str,
    frequency: str,
    amount: int,
    plan_id: str | None = None,
    payee_id: str | None = None,
    payee_name: str | None = None,
    category_id: str | None = None,
    memo: str | None = None,
    flag_color: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveScheduledTransactionWrapper(
        scheduled_transaction=SaveScheduledTransaction(
            account_id=account_id,
            date=date,
            frequency=Frequency(frequency),
            amount=amount,
            payee_id=payee_id,
            payee_name=payee_name,
            category_id=category_id,
            memo=memo,
            flag_color=FlagColor(flag_color) if flag_color else None,
        )
    )
    before = await capture.before_scheduled(ctx, resolved, scheduled_transaction_id)
    result = await ctx.scheduled_transactions.update(resolved, scheduled_transaction_id, payload)

    entry = journal.record(
        operation="scheduled_update",
        tool="scheduled_transactions_update",
        plan_id=resolved,
        entity_id=scheduled_transaction_id,
        before=before,
        after=capture._slice(result.data.scheduled_transaction, capture.SCHEDULED_FIELDS),
        note=None if before else "No before-state captured; this entry cannot be reverted.",
    )

    return {**result.model_dump(), "history_entry_id": entry.id}


@write_tool(
    name="scheduled_transactions_delete",
    description="[WRITE] Delete a scheduled transaction.",
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True),
)
@tool_handler
async def scheduled_transactions_delete(scheduled_transaction_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    before = await capture.before_scheduled(ctx, resolved, scheduled_transaction_id)
    result = await ctx.scheduled_transactions.delete(resolved, scheduled_transaction_id)

    entry = journal.record(
        operation="scheduled_delete",
        tool="scheduled_transactions_delete",
        plan_id=resolved,
        entity_id=scheduled_transaction_id,
        before=before,
        note=(None if before else "No before-state captured; this deletion cannot be undone from history."),
    )

    return {**result.model_dump(), "history_entry_id": entry.id}
