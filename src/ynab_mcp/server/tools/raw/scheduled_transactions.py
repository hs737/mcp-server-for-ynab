"""Raw MCP tools: scheduled transactions resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ynab_mcp.models.ynab.scheduled_transactions import (
    Frequency,
    SaveScheduledTransaction,
    SaveScheduledTransactionWrapper,
)
from ynab_mcp.models.ynab.transactions import FlagColor
from ynab_mcp.server.app import mcp
from ynab_mcp.server.context import get_app_context
from ynab_mcp.server.registry import tool_registry


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
    annotations=ToolAnnotations(readOnlyHint=True),
)
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
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def scheduled_transactions_get(scheduled_transaction_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.scheduled_transactions.get(resolved, scheduled_transaction_id)
    return result.model_dump()


@mcp.tool(
    name="scheduled_transactions_create",
    description=(
        "[WRITE] Create a scheduled transaction. "
        "amount: milliunits (1000 = $1.00). Negative for outflow, positive for inflow. "
        "date: ISO date string for the first occurrence (e.g. '2024-01-15'). "
        "frequency: never, daily, weekly, everyOtherWeek, twiceAMonth, every4Weeks, "
        "monthly, everyOtherMonth, every3Months, every4Months, twiceAYear, yearly, everyOtherYear."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
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
    return result.model_dump()


@mcp.tool(
    name="scheduled_transactions_update",
    description=("[WRITE] Update a scheduled transaction. amount: milliunits (1000 = $1.00)."),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
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
    result = await ctx.scheduled_transactions.update(resolved, scheduled_transaction_id, payload)
    return result.model_dump()


@mcp.tool(
    name="scheduled_transactions_delete",
    description="[WRITE] Delete a scheduled transaction.",
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True),
)
async def scheduled_transactions_delete(scheduled_transaction_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.scheduled_transactions.delete(resolved, scheduled_transaction_id)
    return result.model_dump()
