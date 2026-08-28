"""Enriched MCP tools: AI-friendly consolidated tools."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.enriched.analysis import (
    overspent_categories,
    recurring_charges,
    target_funding_gaps,
    upcoming_scheduled_risks,
)
from mcp_server_for_ynab.enriched.bookkeeping import (
    categorization_suggestions,
    memo_annotation_suggestions,
    transaction_history,
)
from mcp_server_for_ynab.enriched.overview import budget_snapshot, cash_position, month_health
from mcp_server_for_ynab.enriched.triage import triage_summary, triage_unapproved, triage_uncategorized
from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler


def _reg(name: str, family: str, summary: str) -> None:
    tool_registry.register(name, family, "read", "enriched", summary)


_reg("overview_available_tools", "meta", "List all available tools with metadata.")
_reg(
    "overview_budget_snapshot",
    "overview",
    "Full budget health snapshot: income, spending, overspent categories, account counts.",
)
_reg(
    "overview_month_health",
    "overview",
    "Month analysis: income, budgeted, activity, overspent and underfunded categories.",
)
_reg("overview_cash_position", "overview", "Account balances: on-budget, off-budget, net worth.")
_reg("triage_summary", "triage", "Combined count of uncategorized + unapproved transactions.")
_reg("triage_uncategorized", "triage", "List all uncategorized transactions, most-recent first.")
_reg("triage_unapproved", "triage", "List all unapproved transactions, most-recent first.")
_reg(
    "bookkeeping_categorization_suggestions",
    "bookkeeping",
    "Suggest categories for uncategorized transactions from payee history.",
)
_reg("bookkeeping_memo_annotation_suggestions", "bookkeeping", "Flag large or split transactions missing memos.")
_reg("bookkeeping_transaction_history", "bookkeeping", "Filtered transaction history with totals.")
_reg("analysis_overspent_categories", "analysis", "Categories with negative balances for a month.")
_reg("analysis_target_funding_gaps", "analysis", "Categories with unmet funding goals for a month.")
_reg(
    "analysis_upcoming_scheduled_risks",
    "analysis",
    "Scheduled outflows due within N days that may exceed category balances.",
)
_reg(
    "analysis_recurring_charges",
    "analysis",
    "Repeating charges grouped by payee id, with cadence and estimated annual cost.",
)


_reg(
    "overview_request_budget",
    "meta",
    "Requests left against YNAB's hourly rate limit.",
)


@mcp.tool(
    name="overview_request_budget",
    description=(
        "[READ] How many API requests remain in the current rolling hour. "
        "YNAB allows 200 per token per hour and this server budgets slightly below that. "
        "Enriched tools spend several requests each, so check this before a long working session, "
        "and prefer enriched tools over many raw calls when the remaining count is low. "
        "This tool costs no API requests."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def overview_request_budget() -> dict[str, Any]:
    ctx = get_app_context()
    return {"scope": "request_budget", **ctx.http.budget.status()}


@mcp.tool(
    name="overview_available_tools",
    description=(
        "[READ] List all available tools grouped by family, with classification and summary. "
        "Start here to understand what the server can do before running other tools."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def overview_available_tools() -> dict[str, Any]:
    by_family = tool_registry.by_family()
    families = {
        family: [
            {
                "name": t.name,
                "classification": t.classification,
                "tool_type": t.tool_type,
                "summary": t.summary,
                "priority": t.priority,
            }
            for t in tools
        ]
        for family, tools in sorted(by_family.items())
    }
    return {
        "scope": "overview_available_tools",
        "total_tool_count": len(tool_registry.all()),
        "families": families,
    }


@mcp.tool(
    name="overview_budget_snapshot",
    description=(
        "[READ] Single-call budget health snapshot. "
        "Returns current month income, spending, to-be-budgeted, age of money, "
        "account counts, and overspent categories. Good first call for any budget session."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def overview_budget_snapshot_tool(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await budget_snapshot(ctx, resolved)


@mcp.tool(
    name="overview_month_health",
    description=(
        "[READ] Summarize a budget month. "
        "Returns income, budgeted, activity, to-be-budgeted, overspent categories, "
        "and underfunded goals. Defaults to current month. "
        "month: ISO date string for first day of month (e.g. '2024-01-01')."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def overview_month_health_tool(
    plan_id: str | None = None,
    month: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await month_health(ctx, resolved, month)


@mcp.tool(
    name="overview_cash_position",
    description=(
        "[READ] Summarize account balances. "
        "Returns on-budget total, off-budget total, net worth, and per-account detail. "
        "Cleared vs uncleared breakdown included for on-budget accounts."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def overview_cash_position_tool(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await cash_position(ctx, resolved)


@mcp.tool(
    name="triage_summary",
    description=(
        "[READ] Combined triage summary: count of uncategorized and unapproved transactions. "
        "Use this to quickly assess whether the budget needs attention before diving deeper."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def triage_summary_tool(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await triage_summary(ctx, resolved)


@mcp.tool(
    name="triage_uncategorized",
    description=(
        "[READ] List all uncategorized transactions, most-recent first. "
        "Each entry includes payee, amount, account, and memo for manual categorization."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def triage_uncategorized_tool(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await triage_uncategorized(ctx, resolved)


@mcp.tool(
    name="triage_unapproved",
    description=(
        "[READ] List all unapproved transactions, most-recent first. "
        "Imported transactions from bank connections typically start as unapproved."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def triage_unapproved_tool(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await triage_unapproved(ctx, resolved)


@mcp.tool(
    name="bookkeeping_categorization_suggestions",
    description=(
        "[READ] Suggest categories for uncategorized transactions using payee history. "
        "Confidence: high (>=80% of past transactions), medium (>=50%), or low (<50%). "
        "Does NOT write — use transactions_update to apply suggestions."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def bookkeeping_categorization_suggestions_tool(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await categorization_suggestions(ctx, resolved)


@mcp.tool(
    name="bookkeeping_memo_annotation_suggestions",
    description=(
        "[READ] Find transactions missing memos that probably need them. "
        "Flags large transactions (>= $50) and splits without memos. "
        "since_date: ISO date to limit history (e.g. '2024-01-01')."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def bookkeeping_memo_annotation_suggestions_tool(
    plan_id: str | None = None,
    since_date: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await memo_annotation_suggestions(ctx, resolved, since_date=since_date)


@mcp.tool(
    name="bookkeeping_transaction_history",
    description=(
        "[READ] Retrieve recent transactions with optional filters and totals. "
        "Filter by one of: payee_id, category_id, or account_id. "
        "since_date: ISO date to limit history (e.g. '2024-01-01'). "
        "Returns inflow, outflow, and net totals in addition to the transaction list."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def bookkeeping_transaction_history_tool(
    plan_id: str | None = None,
    since_date: str | None = None,
    payee_id: str | None = None,
    category_id: str | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await transaction_history(
        ctx,
        resolved,
        since_date=since_date,
        payee_id=payee_id,
        category_id=category_id,
        account_id=account_id,
    )


@mcp.tool(
    name="analysis_overspent_categories",
    description=(
        "[READ] Categories with negative balances for a given month. "
        "Sorted by most-overspent first. Includes budgeted, activity, and balance. "
        "month: ISO date string for first day of month (e.g. '2024-01-01'). Defaults to current month."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def analysis_overspent_categories_tool(
    plan_id: str | None = None,
    month: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await overspent_categories(ctx, resolved, month)


@mcp.tool(
    name="analysis_target_funding_gaps",
    description=(
        "[READ] Categories with unmet funding goals for a given month. "
        "Shows how much more needs to be budgeted to meet each goal target. "
        "month: ISO date string for first day of month (e.g. '2024-01-01'). Defaults to current month."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def analysis_target_funding_gaps_tool(
    plan_id: str | None = None,
    month: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await target_funding_gaps(ctx, resolved, month)


@mcp.tool(
    name="analysis_upcoming_scheduled_risks",
    description=(
        "[READ] Scheduled outflows due within lookahead_days that may exceed category balances. "
        "Flags each transaction as is_risk=true when the category balance is insufficient. "
        "lookahead_days: how many days ahead to scan (default 30, max recommended 90)."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def analysis_upcoming_scheduled_risks_tool(
    plan_id: str | None = None,
    lookahead_days: int = 30,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await upcoming_scheduled_risks(ctx, resolved, lookahead_days=lookahead_days)


@mcp.tool(
    name="analysis_recurring_charges",
    description=(
        "[READ] Find repeating charges (subscriptions, memberships, regular bills) and estimate what "
        "each costs per year. months: how far back to look, default 12. "
        "Charges are grouped by YNAB payee id, not by payee name, so no fuzzy name matching is involved: "
        "YNAB already resolves a merchant to one payee regardless of how the bank spelled it. "
        "Only outflows count; transfers between your own accounts are excluded. "
        "A series needs at least 3 charges on a recognisable cadence (weekly through yearly) to be "
        "reported. Each result carries occurrences — treat a series seen 3 times as a weaker signal than "
        "one seen 12 times — plus amount_changed and days_since_last, which surface price rises and "
        "charges that may have lapsed. Amounts are in milliunits (1000 = $1.00)."
    ),
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def analysis_recurring_charges_tool(
    plan_id: str | None = None,
    months: int = 12,
    since_date: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await recurring_charges(ctx, resolved, months=months, since_date=since_date)
