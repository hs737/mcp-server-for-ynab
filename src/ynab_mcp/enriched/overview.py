"""Enriched orientation tools: budget snapshot, month health, cash position."""

from __future__ import annotations

from datetime import date
from typing import Any

from ynab_mcp.models.amounts import milliunits_to_display
from ynab_mcp.server.context import AppContext


async def budget_snapshot(ctx: AppContext, plan_id: str) -> dict[str, Any]:
    """Summarize current budget health in a single agent-friendly response."""
    today = date.today().isoformat()
    current_month = today[:7] + "-01"

    month_data, accounts_data, categories_data = await _gather(ctx, plan_id, current_month)

    month = month_data.data.month
    accounts = [a for a in accounts_data.data.accounts if not a.closed and not a.deleted]
    on_budget = [a for a in accounts if a.on_budget]
    off_budget = [a for a in accounts if not a.on_budget]

    # Overspent categories
    all_cats = [c for g in categories_data.data.category_groups for c in g.categories if not c.deleted and not c.hidden]
    overspent = [c for c in all_cats if c.balance < 0]

    return {
        "scope": "budget_snapshot",
        "plan_id": plan_id,
        "month": current_month,
        "to_be_budgeted": month.to_be_budgeted,
        "to_be_budgeted_display": milliunits_to_display(month.to_be_budgeted),
        "income": month.income,
        "income_display": milliunits_to_display(month.income),
        "budgeted": month.budgeted,
        "budgeted_display": milliunits_to_display(month.budgeted),
        "activity": month.activity,
        "activity_display": milliunits_to_display(month.activity),
        "age_of_money": month.age_of_money,
        "on_budget_account_count": len(on_budget),
        "off_budget_account_count": len(off_budget),
        "overspent_category_count": len(overspent),
        "overspent_categories": [
            {
                "id": c.id,
                "name": c.name,
                "balance": c.balance,
                "balance_display": milliunits_to_display(c.balance),
            }
            for c in overspent[:10]
        ],
        "server_knowledge": categories_data.data.server_knowledge,
    }


async def month_health(ctx: AppContext, plan_id: str, month: str | None = None) -> dict[str, Any]:
    """Summarize a budget month: income, spending, remaining, overspent categories."""
    target_month = month or (date.today().isoformat()[:7] + "-01")
    month_resp = await ctx.months.get(plan_id, target_month)
    m = month_resp.data.month

    cats_in_month = m.categories
    overspent = [c for c in cats_in_month if c.balance < 0 and not c.deleted and not c.hidden]
    underfunded = [
        c for c in cats_in_month if c.goal_under_funded and c.goal_under_funded < 0 and not c.deleted and not c.hidden
    ]

    return {
        "scope": "month_health",
        "plan_id": plan_id,
        "month": target_month,
        "income": m.income,
        "income_display": milliunits_to_display(m.income),
        "budgeted": m.budgeted,
        "budgeted_display": milliunits_to_display(m.budgeted),
        "activity": m.activity,
        "activity_display": milliunits_to_display(m.activity),
        "to_be_budgeted": m.to_be_budgeted,
        "to_be_budgeted_display": milliunits_to_display(m.to_be_budgeted),
        "age_of_money": m.age_of_money,
        "overspent_count": len(overspent),
        "overspent_categories": [
            {
                "id": c.id,
                "name": c.name,
                "balance": c.balance,
                "balance_display": milliunits_to_display(c.balance),
            }
            for c in overspent[:10]
        ],
        "underfunded_goal_count": len(underfunded),
        "underfunded_goals": [
            {
                "id": c.id,
                "name": c.name,
                "goal_under_funded": c.goal_under_funded,
                "display": milliunits_to_display(c.goal_under_funded or 0),
            }
            for c in underfunded[:10]
        ],
    }


async def cash_position(ctx: AppContext, plan_id: str) -> dict[str, Any]:
    """Summarize account balances: on-budget, off-budget, net worth."""
    accounts_resp = await ctx.accounts.list(plan_id)
    accounts = [a for a in accounts_resp.data.accounts if not a.deleted and not a.closed]

    on_budget = [a for a in accounts if a.on_budget]
    off_budget = [a for a in accounts if not a.on_budget]

    on_budget_total = sum(a.balance for a in on_budget)
    off_budget_total = sum(a.balance for a in off_budget)
    net_worth = on_budget_total + off_budget_total

    return {
        "scope": "cash_position",
        "plan_id": plan_id,
        "on_budget_total": on_budget_total,
        "on_budget_total_display": milliunits_to_display(on_budget_total),
        "off_budget_total": off_budget_total,
        "off_budget_total_display": milliunits_to_display(off_budget_total),
        "net_worth": net_worth,
        "net_worth_display": milliunits_to_display(net_worth),
        "on_budget_accounts": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "balance": a.balance,
                "balance_display": milliunits_to_display(a.balance),
                "cleared_balance": a.cleared_balance,
                "uncleared_balance": a.uncleared_balance,
            }
            for a in on_budget
        ],
        "off_budget_accounts": [
            {
                "id": a.id,
                "name": a.name,
                "type": a.type,
                "balance": a.balance,
                "balance_display": milliunits_to_display(a.balance),
            }
            for a in off_budget
        ],
        "server_knowledge": accounts_resp.data.server_knowledge,
    }


async def _gather(ctx: AppContext, plan_id: str, current_month: str) -> tuple[Any, Any, Any]:
    import asyncio

    return await asyncio.gather(
        ctx.months.get(plan_id, current_month),
        ctx.accounts.list(plan_id),
        ctx.categories.list(plan_id),
    )
