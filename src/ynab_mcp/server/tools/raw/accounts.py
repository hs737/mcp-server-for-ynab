"""Raw MCP tools: accounts resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ynab_mcp.models.ynab.accounts import AccountType, SaveAccount, SaveAccountWrapper
from ynab_mcp.server.app import mcp
from ynab_mcp.server.context import get_app_context
from ynab_mcp.server.registry import tool_registry
from ynab_mcp.server.tools.boundary import tool_handler


def _reg(name: str, classification: str, summary: str) -> None:
    tool_registry.register(name, "accounts", classification, "raw", summary)  # type: ignore[arg-type]


_reg("accounts_list", "read", "List all accounts for a plan. Supports delta sync.")
_reg("accounts_get", "read", "Get a single account by ID.")
_reg("accounts_create", "write", "Create a new account. [WRITE]")


@mcp.tool(
    name="accounts_list",
    description=(
        "[READ] List all accounts for a plan. "
        "Balances are in milliunits (1000 = $1.00). "
        "Supports delta sync via last_knowledge_of_server."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def accounts_list(
    plan_id: str | None = None,
    last_knowledge_of_server: int | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.accounts.list(resolved, last_knowledge_of_server=last_knowledge_of_server)
    return result.model_dump()


@mcp.tool(
    name="accounts_get",
    description="[READ] Get a single account by ID. Balance is in milliunits (1000 = $1.00).",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def accounts_get(account_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    result = await ctx.accounts.get(resolved, account_id)
    return result.model_dump()


@mcp.tool(
    name="accounts_create",
    description=(
        "[WRITE] Create a new account. "
        "balance is the initial account balance in milliunits (1000 = $1.00). "
        "type must be one of: checking, savings, cash, creditCard, lineOfCredit, "
        "otherAsset, otherLiability, mortgage, autoLoan, studentLoan, personalLoan, "
        "medicalDebt, otherDebt."
    ),
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False),
)
@tool_handler
async def accounts_create(
    name: str,
    type: str,
    balance: int,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    payload = SaveAccountWrapper(account=SaveAccount(name=name, type=AccountType(type), balance=balance))
    result = await ctx.accounts.create(resolved, payload)
    return result.model_dump()
