"""Enriched analysis tools: overspent categories, funding gaps, scheduled risks."""

from __future__ import annotations

from datetime import date
from typing import Any

from ynab_mcp.models.amounts import milliunits_to_display
from ynab_mcp.server.context import AppContext


async def overspent_categories(ctx: AppContext, plan_id: str, month: str | None = None) -> dict[str, Any]:
    """List categories with negative balances for a given month.

    Returns each overspent category with balance, budgeted amount, and activity
    so the agent can explain why overspending occurred.
    """
    target_month = month or (date.today().isoformat()[:7] + "-01")
    month_resp = await ctx.months.get(plan_id, target_month)
    cats = month_resp.data.month.categories

    overspent = [c for c in cats if c.balance < 0 and not c.deleted and not c.hidden]
    overspent.sort(key=lambda c: c.balance)

    total_overspent = sum(c.balance for c in overspent)
    return {
        "scope": "overspent_categories",
        "plan_id": plan_id,
        "month": target_month,
        "overspent_count": len(overspent),
        "total_overspent": total_overspent,
        "total_overspent_display": milliunits_to_display(total_overspent),
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "balance": c.balance,
                "balance_display": milliunits_to_display(c.balance),
                "budgeted": c.budgeted,
                "budgeted_display": milliunits_to_display(c.budgeted),
                "activity": c.activity,
                "activity_display": milliunits_to_display(c.activity),
                "goal_type": c.goal_type,
            }
            for c in overspent
        ],
    }


async def target_funding_gaps(ctx: AppContext, plan_id: str, month: str | None = None) -> dict[str, Any]:
    """List categories with unmet funding goals for a given month.

    goal_under_funded is the YNAB field expressing how much more needs to be
    budgeted to meet the goal target this month.
    """
    target_month = month or (date.today().isoformat()[:7] + "-01")
    month_resp = await ctx.months.get(plan_id, target_month)
    cats = month_resp.data.month.categories

    gaps = [c for c in cats if c.goal_under_funded and c.goal_under_funded < 0 and not c.deleted and not c.hidden]
    gaps.sort(key=lambda c: c.goal_under_funded or 0)

    total_gap = sum(c.goal_under_funded or 0 for c in gaps)
    return {
        "scope": "target_funding_gaps",
        "plan_id": plan_id,
        "month": target_month,
        "underfunded_count": len(gaps),
        "total_gap": total_gap,
        "total_gap_display": milliunits_to_display(total_gap),
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "goal_type": c.goal_type,
                "goal_under_funded": c.goal_under_funded,
                "gap_display": milliunits_to_display(c.goal_under_funded or 0),
                "budgeted": c.budgeted,
                "budgeted_display": milliunits_to_display(c.budgeted),
                "balance": c.balance,
                "balance_display": milliunits_to_display(c.balance),
            }
            for c in gaps
        ],
    }


async def upcoming_scheduled_risks(
    ctx: AppContext,
    plan_id: str,
    *,
    lookahead_days: int = 30,
) -> dict[str, Any]:
    """Identify scheduled transactions due within lookahead_days that may exceed available funds.

    Compares each upcoming scheduled outflow against the current balance of its
    assigned category, surfacing cases where the category balance is insufficient.
    """
    import asyncio
    from datetime import timedelta

    today = date.today()
    cutoff = (today + timedelta(days=lookahead_days)).isoformat()
    today_str = today.isoformat()

    sched_resp, cats_resp = await asyncio.gather(
        ctx.scheduled_transactions.list(plan_id),
        ctx.categories.list(plan_id),
    )

    scheduled = sched_resp.data.scheduled_transactions
    all_cats = {c.id: c for g in cats_resp.data.category_groups for c in g.categories if not c.deleted}

    upcoming = [
        s
        for s in scheduled
        if not s.deleted and s.date_next >= today_str and s.date_next <= cutoff and s.amount < 0  # outflows only
    ]
    upcoming.sort(key=lambda s: s.date_next)

    risks = []
    for s in upcoming:
        cat = all_cats.get(s.category_id or "") if s.category_id else None
        cat_balance = cat.balance if cat else None
        is_risk = cat_balance is not None and cat_balance < abs(s.amount)
        risks.append(
            {
                "scheduled_transaction_id": s.id,
                "date_next": s.date_next,
                "payee_name": s.payee_name,
                "amount": s.amount,
                "amount_display": milliunits_to_display(s.amount),
                "category_id": s.category_id,
                "category_name": s.category_name,
                "category_balance": cat_balance,
                "category_balance_display": (milliunits_to_display(cat_balance) if cat_balance is not None else None),
                "shortfall": ((cat_balance - abs(s.amount)) if cat_balance is not None else None),
                "shortfall_display": (
                    milliunits_to_display(cat_balance - abs(s.amount)) if cat_balance is not None else None
                ),
                "is_risk": is_risk,
                "frequency": s.frequency,
            }
        )

    at_risk = [r for r in risks if r["is_risk"]]
    return {
        "scope": "upcoming_scheduled_risks",
        "plan_id": plan_id,
        "as_of": today_str,
        "lookahead_days": lookahead_days,
        "cutoff_date": cutoff,
        "upcoming_count": len(upcoming),
        "at_risk_count": len(at_risk),
        "scheduled_transactions": risks,
    }
