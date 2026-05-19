"""Raw MCP tools: transactions resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ynab_mcp.models.ynab.transactions import (
    ClearedStatus,
    FlagColor,
    SaveTransaction,
    SaveTransactionWrapper,
    UpdateTransaction,
    UpdateTransactionsWrapper,
)
from ynab_mcp.server.app import mcp
from ynab_mcp.server.context import get_app_context
from ynab_mcp.server.registry import tool_registry


def _reg(name: str, classification: str, summary: str) -> None:
    tool_registry.register(name, "transactions", classification, "raw", summary)  # type: ignore[arg-type]


_reg("transactions_list", "read", "List transactions. Supports filtering and delta sync.")
_reg("transactions_list_by_account", "read", "List transactions for a specific account.")
_reg("transactions_list_by_category", "read", "List transactions for a specific category.")
_reg("transactions_list_by_payee", "read", "List transactions for a specific payee.")
_reg("transactions_list_by_month", "read", "List transactions for a specific month.")
_reg("transactions_get", "read", "Get a single transaction including subtransactions.")
_reg("transactions_create", "write", "Create a transaction. [WRITE]")
_reg("transactions_update", "write", "Update a transaction. [WRITE]")
_reg("transactions_bulk_update", "write", "Update multiple transactions. Partial success. [WRITE]")
_reg("transactions_delete", "write", "Delete a transaction. Transfer-aware. [WRITE]")
_reg("transactions_trigger_import", "write", "Trigger YNAB import from linked accounts. [WRITE]")


@mcp.tool(
    name="transactions_list",
    description=(
        "[READ] List transactions for a plan. "
        "since_date: ISO date string (e.g. '2024-01-01') — only transactions on or after this date. "
        "type: 'uncategorized' or 'unapproved' for filtered lists. "
        "Amounts are in milliunits (1000 = $1.00). "
        "Includes subtransactions for split transactions. "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def transactions_list(
    plan_id: str | None = None,
    since_date: str | None = None,
    type: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.transactions.list(
        resolved,
        since_date=since_date,
        type=type,
        last_knowledge_of_server=last_knowledge_of_server,
    )
    return result.model_dump()


@mcp.tool(
    name="transactions_list_by_account",
    description=("[READ] List transactions for a specific account. Amounts are in milliunits. Supports delta sync."),
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def transactions_list_by_account(
    account_id: str,
    plan_id: str | None = None,
    since_date: str | None = None,
    type: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.transactions.list_by_account(
        resolved,
        account_id,
        since_date=since_date,
        type=type,
        last_knowledge_of_server=last_knowledge_of_server,
    )
    return result.model_dump()


@mcp.tool(
    name="transactions_list_by_category",
    description="[READ] List transactions for a specific category. Amounts in milliunits.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def transactions_list_by_category(
    category_id: str,
    plan_id: str | None = None,
    since_date: str | None = None,
    type: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.transactions.list_by_category(
        resolved,
        category_id,
        since_date=since_date,
        type=type,
        last_knowledge_of_server=last_knowledge_of_server,
    )
    return result.model_dump()


@mcp.tool(
    name="transactions_list_by_payee",
    description="[READ] List transactions for a specific payee. Amounts in milliunits.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def transactions_list_by_payee(
    payee_id: str,
    plan_id: str | None = None,
    since_date: str | None = None,
    type: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.transactions.list_by_payee(
        resolved,
        payee_id,
        since_date=since_date,
        type=type,
        last_knowledge_of_server=last_knowledge_of_server,
    )
    return result.model_dump()


@mcp.tool(
    name="transactions_list_by_month",
    description=(
        "[READ] List transactions for a specific month. "
        "month: ISO date string for the first day of the month (e.g. '2024-01-01'). "
        "Amounts in milliunits."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def transactions_list_by_month(
    month: str,
    plan_id: str | None = None,
    since_date: str | None = None,
    type: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.transactions.list_by_month(
        resolved,
        month,
        since_date=since_date,
        type=type,
        last_knowledge_of_server=last_knowledge_of_server,
    )
    return result.model_dump()


@mcp.tool(
    name="transactions_get",
    description=(
        "[READ] Get a single transaction by ID. "
        "Includes subtransactions for split transactions. "
        "Check transfer_account_id to identify transfer transactions. "
        "Amount is in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def transactions_get(transaction_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.transactions.get(resolved, transaction_id)
    return result.model_dump()


@mcp.tool(
    name="transactions_create",
    description=(
        "[WRITE] Create a single transaction. "
        "amount: milliunits (1000 = $1.00). Negative for outflow, positive for inflow. "
        "For transfers: set payee_id to the transfer_payee_id of the target account. "
        "For splits: provide subtransactions whose amounts sum to the parent amount. "
        "date: ISO date string (e.g. '2024-01-15')."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
async def transactions_create(
    account_id: str,
    date: str,
    amount: int,
    plan_id: str | None = None,
    payee_id: str | None = None,
    payee_name: str | None = None,
    category_id: str | None = None,
    memo: str | None = None,
    cleared: str | None = None,
    approved: bool | None = None,
    flag_color: str | None = None,
    import_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveTransactionWrapper(
        transaction=SaveTransaction(
            account_id=account_id,
            date=date,
            amount=amount,
            payee_id=payee_id,
            payee_name=payee_name,
            category_id=category_id,
            memo=memo,
            cleared=ClearedStatus(cleared) if cleared else None,
            approved=approved,
            flag_color=FlagColor(flag_color) if flag_color else None,
            import_id=import_id,
        )
    )
    result = await ctx.transactions.create(resolved, payload)
    return result.model_dump()


@mcp.tool(
    name="transactions_update",
    description=(
        "[WRITE] Update a transaction. "
        "amount: milliunits (1000 = $1.00). "
        "All provided fields are updated. Omit fields you do not want to change."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
async def transactions_update(
    transaction_id: str,
    account_id: str,
    date: str,
    amount: int,
    plan_id: str | None = None,
    payee_id: str | None = None,
    payee_name: str | None = None,
    category_id: str | None = None,
    memo: str | None = None,
    cleared: str | None = None,
    approved: bool | None = None,
    flag_color: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveTransactionWrapper(
        transaction=SaveTransaction(
            account_id=account_id,
            date=date,
            amount=amount,
            payee_id=payee_id,
            payee_name=payee_name,
            category_id=category_id,
            memo=memo,
            cleared=ClearedStatus(cleared) if cleared else None,
            approved=approved,
            flag_color=FlagColor(flag_color) if flag_color else None,
        )
    )
    result = await ctx.transactions.update(resolved, transaction_id, payload)
    return result.model_dump()


@mcp.tool(
    name="transactions_bulk_update",
    description=(
        "[WRITE] Update multiple transactions in one call. "
        "IMPORTANT: This is NOT atomic. The response contains transaction_ids (successfully updated) "
        "and duplicate_import_ids (skipped). Always verify the response — do not assume all-or-nothing success. "
        "transactions: list of objects with id (required) and any fields to update. "
        "All amounts in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
async def transactions_bulk_update(
    transactions: list[dict[str, Any]],
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    updates = [UpdateTransaction.model_validate(t) for t in transactions]
    payload = UpdateTransactionsWrapper(transactions=updates)
    result = await ctx.transactions.bulk_update(resolved, payload)
    return result.model_dump()


@mcp.tool(
    name="transactions_delete",
    description=(
        "[WRITE] Delete a transaction. "
        "WARNING: For transfer transactions, deleting one side affects the paired transaction. "
        "Check transfer_account_id before deleting to understand transfer implications."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True),
)
async def transactions_delete(transaction_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.transactions.delete(resolved, transaction_id)
    return result.model_dump()


@mcp.tool(
    name="transactions_trigger_import",
    description=(
        "[WRITE] Trigger YNAB's built-in import from linked bank accounts. "
        "This does NOT accept raw transaction data or external file uploads. "
        "Only accounts with direct bank links are affected. "
        "Returns the IDs of transactions that were imported."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
async def transactions_trigger_import(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.transactions.trigger_import(resolved)
    return result.model_dump()
