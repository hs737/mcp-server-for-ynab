"""MCP tools that read across months: ranges, matrices, and integrity checks.

Separate from `enriched.py` because these share a cost model that has to be
stated in every description: YNAB has no range endpoint, so a range of N months
is N requests against an hourly limit of 200.
"""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.enriched.audit import (
    assignment_patterns,
    balance_identity,
    copied_forward_months,
    flow_trace,
    group_parity,
    overspent_history,
    unassigned_transfers,
)
from mcp_server_for_ynab.enriched.changes import changes_since
from mcp_server_for_ynab.enriched.credit import credit_funding
from mcp_server_for_ynab.enriched.multi_month import MAX_RANGE_MONTHS, group_series, month_series
from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler

_COST = (
    f"Costs one YNAB request per month in the range (limit {MAX_RANGE_MONTHS} months); "
    "check overview_request_budget before a long range."
)


def _reg(name: str, family: str, summary: str) -> None:
    tool_registry.register(name, family, "read", "enriched", summary)


_reg("months_range", "months", "Category-by-month matrix of budgeted, activity and balance.")
_reg("category_groups_summary_by_month", "months", "Per-group, per-month totals across a range.")
_reg("analysis_overspent_history", "analysis", "Overspending per category per month, cash vs credit.")
_reg("analysis_group_parity", "analysis", "Compare two category groups month by month.")
_reg("analysis_copied_forward_months", "analysis", "Months whose assignments repeat the month before.")
_reg("analysis_credit_funding", "analysis", "Card debt vs payment-category funds, and trapped money.")
_reg("analysis_flow_trace", "analysis", "One category's assigned, moved, spent and left, by month.")
_reg("analysis_unassigned_transfers", "analysis", "Transfers that moved no category money, against assignments.")
_reg("analysis_assignment_patterns", "analysis", "Categories assigned a base plus their own inflow.")
_reg("overview_balance_identity", "overview", "Check categories + Ready to Assign against accounts.")
_reg("changes_since", "changes", "What changed since a server_knowledge value.")


@mcp.tool(
    name="months_range",
    description=(
        "[READ] Budgeted, activity and balance for every category across a range of months, as one "
        "matrix. This is the tool for any month-over-month question: one call instead of one "
        "months_get per month, and a quarter of the size, because it returns six fields per category "
        "rather than every goal field YNAB tracks. "
        "from_month and to_month: 'YYYY-MM', an ISO date, or 'current'. to_month defaults to the "
        "current month. "
        "Narrow it with category_ids or group_ids (category_ids wins if both are given). "
        "fields: which of budgeted, activity and balance each cell carries — all three by default, "
        "and dropping the two you are not reading takes roughly two thirds off a forty-category "
        "range. "
        "include_hidden=true adds hidden categories, including the credit-card payment ones. "
        "The response carries as_of: a range is a snapshot, and one cached earlier in a session is "
        "not what the plan says now. Re-read it, or use changes_since, before acting on an old one. "
        "Amounts are in milliunits (1000 = $1.00). " + _COST
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def months_range_tool(
    from_month: str,
    to_month: str | None = None,
    plan_id: str | None = None,
    category_ids: list[str] | None = None,
    group_ids: list[str] | None = None,
    include_hidden: bool = False,
    fields: list[str] | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await month_series(
        ctx,
        resolved,
        from_month,
        to_month,
        category_ids=category_ids,
        group_ids=group_ids,
        include_hidden=include_hidden,
        fields=fields,
    )


@mcp.tool(
    name="category_groups_summary_by_month",
    description=(
        "[READ] Per-group, per-month totals of budgeted, activity and balance. "
        "Most 'is this budget healthy' questions live at group level, and a group view is small "
        "enough to read whole where a category view is not. "
        "from_month and to_month: 'YYYY-MM', an ISO date, or 'current'. to_month defaults to the "
        "current month. "
        "Hidden categories are included by default here, because excluding them would silently drop "
        "the credit-card payment group; pass include_hidden=false to leave them out. "
        "Amounts are in milliunits (1000 = $1.00). " + _COST
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def category_groups_summary_by_month(
    from_month: str,
    to_month: str | None = None,
    plan_id: str | None = None,
    include_hidden: bool = True,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await group_series(ctx, resolved, from_month, to_month, include_hidden=include_hidden)


@mcp.tool(
    name="analysis_overspent_history",
    description=(
        "[READ] Every negative month-end category balance across a range, with each overspend "
        "flagged as cash or credit and a running total of what was absorbed by Ready to Assign. "
        "Cash overspending comes out of the next month's Ready to Assign, which is why a month can "
        "look under-funded for a reason invisible inside it; credit overspending stays as a negative "
        "balance and becomes debt the payment category has not covered. YNAB does not report which "
        "kind an overspend was, so it is inferred from the accounts the category was spent on. "
        "from_month and to_month: 'YYYY-MM', an ISO date, or 'current'. "
        "Also returns the categories that were overspent in the most months. " + _COST + " Plus one "
        "for the transaction history used to tell cash from credit."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def analysis_overspent_history(
    from_month: str,
    to_month: str | None = None,
    plan_id: str | None = None,
    include_hidden: bool = False,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await overspent_history(ctx, resolved, from_month, to_month, include_hidden=include_hidden)


@mcp.tool(
    name="analysis_group_parity",
    description=(
        "[READ] Compare two category groups month by month: assigned, activity, balance, and the "
        "gap between them. Written for plans that split money between two people — paired 'his' and "
        "'hers' or 'partner A' and 'partner B' groups — where the question is whether the two are "
        "being funded and spent evenly. "
        "Gaps are always group A minus group B. Get group ids from categories_list. "
        "from_month and to_month: 'YYYY-MM', an ISO date, or 'current'. " + _COST
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def analysis_group_parity(
    group_a_id: str,
    group_b_id: str,
    from_month: str,
    to_month: str | None = None,
    plan_id: str | None = None,
    include_hidden: bool = False,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await group_parity(
        ctx, resolved, group_a_id, group_b_id, from_month, to_month, include_hidden=include_hidden
    )


@mcp.tool(
    name="analysis_copied_forward_months",
    description=(
        "[READ] Find months whose assignments are an exact copy of the month before. "
        "That is the signature of YNAB's 'assign last month's amounts' applied without review, which "
        "carries one-off assignments forward as though they were the plan — a one-time $10,000 move "
        "repeated silently the next month. "
        "Defaults to the last 12 months; pass from_month and to_month to widen or shift it. "
        "The month before the range is read too, so the first month has something to be compared "
        "against. " + _COST
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def analysis_copied_forward_months(
    from_month: str | None = None,
    to_month: str | None = None,
    plan_id: str | None = None,
    include_hidden: bool = False,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await copied_forward_months(ctx, resolved, from_month, to_month, include_hidden=include_hidden)


@mcp.tool(
    name="analysis_credit_funding",
    description=(
        "[READ] For every credit card and line of credit: what it owes, what its payment category "
        "holds, and the difference. Two problems live here and nowhere else in YNAB's interface — "
        "debt with no money set aside for it, and money stranded in the payment category of a closed "
        "account, which the budget counts as spoken for but cannot spend. "
        "Also reports payment categories that went negative in recent months, which is how "
        "overspending on a card turns into uncovered debt. "
        "months: how many recent months of payment-category history to include (default 6, one "
        "request each; 0 to skip). Accounts and payment categories are matched by name, because "
        "YNAB provides no identifier linking them; anything unmatched is reported rather than "
        "dropped."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def analysis_credit_funding(plan_id: str | None = None, months: int = 6) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await credit_funding(ctx, resolved, months=months)


@mcp.tool(
    name="analysis_flow_trace",
    description=(
        "[READ] Follow one category's money through a range of months: assigned in, moved in, moved "
        "out, spent, refunded, and the balance left at the end of each month. "
        "This is 'where did the holiday money go', which needs three different YNAB resources to "
        "answer because assigning, moving between categories, and spending are three different "
        "records. "
        "from_month and to_month: 'YYYY-MM', an ISO date, or 'current'. " + _COST + " Plus two for "
        "the money movements and transactions."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def analysis_flow_trace(
    category_id: str,
    from_month: str,
    to_month: str | None = None,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await flow_trace(ctx, resolved, category_id, from_month, to_month)


@mcp.tool(
    name="overview_balance_identity",
    description=(
        "[READ] Check that the plan adds up: category balances plus Ready to Assign should equal the "
        "on-budget account balances plus credit-card debt. It holds whether or not the budget is "
        "healthy, so a mismatch means the data is inconsistent — a stale read, a missing category, "
        "an account the plan is not counting — rather than that the budgeting is wrong. "
        "Run it first in a review: if it ties, the rest of the numbers can be trusted. "
        "Costs three requests."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def overview_balance_identity(plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await balance_identity(ctx, resolved)


@mcp.tool(
    name="changes_since",
    description=(
        "[READ] What changed in the plan since a given server_knowledge value: categories, months, "
        "and transactions, compactly. Use it after the user edits their budget in the app instead of "
        "re-reading everything. "
        "Call it with no arguments first to get a baseline server_knowledge, then pass that value "
        "back on each later call. Every response returns the value to use next time. "
        "This is the cheap way to keep a long session honest: re-reading a range you already have "
        "costs one request per month, and this costs three no matter how much moved. "
        "Deleted records are omitted, and delta sync reports that a record changed, not how — the "
        "values shown are current ones. Costs three requests."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def changes_since_tool(
    server_knowledge: int | None = None,
    plan_id: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await changes_since(ctx, resolved, server_knowledge, limit=limit)


@mcp.tool(
    name="analysis_unassigned_transfers",
    description=(
        "[READ] Transfers between two on-budget accounts, month by month, against what was assigned "
        "in the category groups they were meant to fund. "
        "A transfer between on-budget accounts moves no category money — both accounts are already "
        "inside the budget — so a standing 'move $1,500 to the joint account' changes no category "
        "balance, while looking in the register exactly like it did. Seven months of that went "
        "unnoticed on the plan this was written for. "
        "group_ids: the groups those transfers were meant to fund. Pass them and the months where "
        "money moved and nothing was assigned come back flagged; leave them out and you get the "
        "transfers alone. Get group ids from categories_list. "
        "account_ids narrows it to transfers touching those accounts. "
        "from_month and to_month: 'YYYY-MM', an ISO date, or 'current'. "
        "Costs two requests, plus one per month when group_ids is given."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def analysis_unassigned_transfers(
    from_month: str,
    to_month: str | None = None,
    group_ids: list[str] | None = None,
    account_ids: list[str] | None = None,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await unassigned_transfers(
        ctx,
        resolved,
        from_month,
        to_month,
        group_ids=group_ids,
        account_ids=account_ids,
    )


@mcp.tool(
    name="analysis_assignment_patterns",
    description=(
        "[READ] Categories whose monthly assignment equals a fixed base plus the money that arrived "
        "in the category that month. "
        "This is the interest double-count: a savings category earns interest, the interest is "
        "categorised into it, and the assignment is then written as 'the usual $1,500 plus the "
        "$12.40 of interest' — funding it twice. Each month is individually plausible, which is why "
        "nobody notices; sixteen months of it came to about $841 on the plan this was written for. "
        "Narrow it with group_ids or category_ids. from_month and to_month: 'YYYY-MM', an ISO date, "
        "or 'current'. "
        "total_if_unintended is what the pattern would have double-funded. It is a signal, not a "
        "verdict: a category deliberately funded to cover its own activity produces the same shape, "
        "so the matching months are reported for checking. " + _COST + " Plus one for the inflows."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def analysis_assignment_patterns(
    from_month: str,
    to_month: str | None = None,
    group_ids: list[str] | None = None,
    category_ids: list[str] | None = None,
    include_hidden: bool = False,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await assignment_patterns(
        ctx,
        resolved,
        from_month,
        to_month,
        group_ids=group_ids,
        category_ids=category_ids,
        include_hidden=include_hidden,
    )
