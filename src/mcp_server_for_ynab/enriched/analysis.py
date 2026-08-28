"""Enriched analysis tools: overspent categories, funding gaps, scheduled risks."""

from __future__ import annotations

from datetime import date, timedelta
from itertools import pairwise
from typing import Any

from mcp_server_for_ynab.models.amounts import milliunits_to_display
from mcp_server_for_ynab.server.context import AppContext


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
    budgeted to meet the goal target this month. It is POSITIVE when the goal is
    short — 35388340 means $35,388.34 still needs to be budgeted. Filtering for
    negative values here silently returned an empty list for every plan.
    """
    target_month = month or (date.today().isoformat()[:7] + "-01")
    month_resp = await ctx.months.get(plan_id, target_month)
    cats = month_resp.data.month.categories

    gaps = [c for c in cats if c.goal_under_funded and c.goal_under_funded > 0 and not c.deleted and not c.hidden]
    gaps.sort(key=lambda c: c.goal_under_funded or 0, reverse=True)  # largest shortfall first

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


# A charge seen twice is a coincidence as often as a subscription, so three
# occurrences is the floor for calling something recurring.
_MIN_OCCURRENCES = 3

# Cadence alone over-reports badly, and the failure is not subtle: a grocery
# store visited most weeks, a hardware store, an airline booked for a few trips
# — all land inside a cadence band and get reported as subscriptions. On a real
# plan that turned 58 "recurring charges" into mostly ordinary shopping.
#
# What separates the two is not rhythm but consistency of amount. A
# subscription bills the same figure every time; shopping at a regularly
# visited merchant scatters. So a series has to clear two further bars: most of
# its charges near the median amount, and gaps that are actually even rather
# than merely averaging into a band.
_AMOUNT_TOLERANCE = 0.06
_MIN_STABLE_SHARE = 0.75
_GAP_TOLERANCE = 0.30
_MIN_REGULAR_SHARE = 0.70

# Below this, percentage tolerance is meaningless — a few cents of drift on a
# small charge is not a price change.
_AMOUNT_FLOOR = 500

# Cadences are named from the median gap between charges, with a tolerance wide
# enough to absorb weekends, month lengths, and a biller that moves a day.
_CADENCES: tuple[tuple[str, int, int, float], ...] = (
    # label, low days, high days, charges per year
    ("weekly", 6, 8, 52.0),
    ("every other week", 12, 16, 26.0),
    ("monthly", 26, 35, 12.0),
    ("every other month", 55, 70, 6.0),
    ("quarterly", 82, 100, 4.0),
    ("twice a year", 170, 195, 2.0),
    ("yearly", 350, 380, 1.0),
)


def _median(values: list[int]) -> float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[midpoint])
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _classify_cadence(gaps: list[int]) -> tuple[str | None, float | None]:
    """Name the rhythm of a series of day-gaps, or decline to."""
    if not gaps:
        return None, None

    typical = _median(gaps)
    for label, low, high, per_year in _CADENCES:
        if low <= typical <= high:
            return label, per_year
    return None, None


def _share_within(values: list[int], centre: float, tolerance: float) -> float:
    """Fraction of values lying within `tolerance` of `centre`, proportionally."""
    if not values or centre <= 0:
        return 0.0
    allowed = max(centre * tolerance, _AMOUNT_FLOOR if centre > _AMOUNT_FLOOR else centre * tolerance)
    inside = sum(1 for value in values if abs(value - centre) <= allowed)
    return inside / len(values)


def _gaps_are_regular(gaps: list[int]) -> float:
    """Fraction of gaps close to the median gap.

    A median falling inside a cadence band says nothing about whether the
    charges were evenly spaced: three visits at 2, 6 and 40 days have a
    perfectly weekly median and no rhythm at all.
    """
    if not gaps:
        return 0.0
    typical = _median(gaps)
    if typical <= 0:
        return 0.0
    inside = sum(1 for gap in gaps if abs(gap - typical) <= typical * _GAP_TOLERANCE)
    return inside / len(gaps)


async def recurring_charges(
    ctx: AppContext,
    plan_id: str,
    months: int = 12,
    since_date: str | None = None,
) -> dict[str, Any]:
    """Find repeating charges and estimate what they cost per year.

    Charges are grouped by `payee_id`, never by payee name. YNAB already
    resolves a merchant to one payee record regardless of how a bank spelled the
    descriptor on any given statement line, so the identifier is exact and the
    fuzzy-matching problem that makes name-based detection unreliable does not
    arise. The cost is that a subscription the user recorded under two distinct
    payees reads as two series, which is the safer way to be wrong: it
    over-reports rather than silently merging unrelated charges.

    Only outflows are considered, transfers are excluded (moving money between
    your own accounts is not a subscription), and a series needs at least three
    charges on a recognisable cadence before it is reported.
    """
    start = since_date or (date.today() - timedelta(days=int(months * 30.5))).isoformat()

    response = await ctx.transactions.list(plan_id, since_date=start)
    transactions = [
        txn
        for txn in response.data.transactions
        if not txn.deleted and txn.amount < 0 and txn.payee_id is not None and txn.transfer_account_id is None
    ]

    by_payee: dict[str, list[Any]] = {}
    for txn in transactions:
        by_payee.setdefault(str(txn.payee_id), []).append(txn)

    series: list[dict[str, Any]] = []
    for payee_id, charges in by_payee.items():
        if len(charges) < _MIN_OCCURRENCES:
            continue

        charges.sort(key=lambda t: t.date)
        dates = [date.fromisoformat(t.date) for t in charges]
        gaps = [(later - earlier).days for earlier, later in pairwise(dates)]
        cadence, per_year = _classify_cadence(gaps)
        if cadence is None:
            continue

        regularity = _gaps_are_regular(gaps)
        if regularity < _MIN_REGULAR_SHARE:
            continue

        amounts = [abs(t.amount) for t in charges]
        typical_amount = int(_median(amounts))
        stability = _share_within(amounts, typical_amount, _AMOUNT_TOLERANCE)
        if stability < _MIN_STABLE_SHARE:
            continue

        latest, earliest = amounts[-1], amounts[0]

        series.append(
            {
                "payee_id": payee_id,
                "payee_name": charges[-1].payee_name,
                "category_name": charges[-1].category_name,
                "cadence": cadence,
                "occurrences": len(charges),
                "first_seen": charges[0].date,
                "last_seen": charges[-1].date,
                "typical_amount": typical_amount,
                "typical_amount_display": milliunits_to_display(typical_amount),
                "last_amount": latest,
                "last_amount_display": milliunits_to_display(latest),
                # Prices drift. Saying so is more useful than hiding it behind
                # a single "typical" figure the user cannot reconcile.
                "amount_changed": latest != earliest,
                # How firmly this looks like a subscription rather than a
                # merchant the user happens to visit on a rhythm.
                "amount_consistency": round(stability, 2),
                "cadence_regularity": round(regularity, 2),
                "estimated_annual_cost": int(typical_amount * (per_year or 0)),
                "estimated_annual_cost_display": milliunits_to_display(int(typical_amount * (per_year or 0))),
                "days_since_last": (date.today() - dates[-1]).days,
            }
        )

    series.sort(key=lambda s: s["estimated_annual_cost"], reverse=True)
    total = sum(int(s["estimated_annual_cost"]) for s in series)

    return {
        "scope": "recurring_charges",
        "plan_id": plan_id,
        "since_date": start,
        "recurring_count": len(series),
        "estimated_annual_total": total,
        "estimated_annual_total_display": milliunits_to_display(total),
        "grouping": "payee_id",
        "note": (
            "Grouped by YNAB payee id, so no name matching is involved. A series needs at least "
            f"{_MIN_OCCURRENCES} charges, evenly spaced on a recognisable cadence, at a consistent amount. "
            "The amount test is what separates a subscription from a merchant visited on a rhythm: a "
            "grocery store every week is regular but not a subscription. Occurrences is the strength of "
            "the signal — treat a series seen 3 times more cautiously than one seen 12 times."
        ),
        "charges": series,
    }
