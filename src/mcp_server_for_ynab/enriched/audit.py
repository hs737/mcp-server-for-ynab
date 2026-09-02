"""Questions you can only answer by looking at several months at once.

Everything here was hand-rolled during a twenty-one-month review of a real
plan, out of `months_get` payloads parsed off disk, because the server had no
route that crossed months. Each function is one of those scripts, made into a
tool.

They share a cost model worth stating plainly: YNAB has no range endpoint, so a
range of N months is N requests against an hourly limit of 200. Ranges are
capped in `multi_month`, and every tool description says what it spends.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from mcp_server_for_ynab.enriched.multi_month import (
    fetch_months,
    month_sequence,
    normalize_month,
    visible,
)
from mcp_server_for_ynab.models.amounts import milliunits_to_display
from mcp_server_for_ynab.models.ynab.accounts import AccountType
from mcp_server_for_ynab.models.ynab.months import Month
from mcp_server_for_ynab.server.context import AppContext

# Only these two account types have credit-card payment categories, which is
# what makes overspending on them behave differently.
_CREDIT_TYPES = frozenset({AccountType.CREDIT_CARD, AccountType.LINE_OF_CREDIT})

INTERNAL_GROUP_NAME = "internal master category"


def _month_of(iso_date: str) -> str:
    return f"{iso_date[:7]}-01"


async def _credit_spending_by_month(
    ctx: AppContext,
    plan_id: str,
    since: str,
) -> dict[tuple[str, str], int]:
    """How much of each category's outflow in each month was charged to a card.

    Keyed by (month, category_id), in positive milliunits. Splits are walked to
    their subtransactions, because the parent of a split carries no category and
    counting it would attribute the whole amount to nothing.
    """
    accounts_resp, txn_resp = await asyncio.gather(
        ctx.accounts.list(plan_id),
        ctx.transactions.list(plan_id, since_date=since),
    )
    credit_accounts = {a.id for a in accounts_resp.data.accounts if a.type in _CREDIT_TYPES}

    spend: dict[tuple[str, str], int] = {}
    for txn in txn_resp.data.transactions:
        if txn.deleted or txn.account_id not in credit_accounts:
            continue
        month = _month_of(txn.date)

        if txn.subtransactions:
            for part in txn.subtransactions:
                if part.deleted or part.amount >= 0 or not part.category_id:
                    continue
                spend[(month, part.category_id)] = spend.get((month, part.category_id), 0) + -part.amount
            continue

        if txn.amount >= 0 or not txn.category_id or txn.transfer_account_id:
            continue
        spend[(month, txn.category_id)] = spend.get((month, txn.category_id), 0) + -txn.amount

    return spend


async def overspent_history(
    ctx: AppContext,
    plan_id: str,
    from_month: str,
    to_month: str | None = None,
    *,
    include_hidden: bool = False,
) -> dict[str, Any]:
    """Every negative month-end category balance across a range, cash or credit.

    The distinction matters because the two behave differently. Cash
    overspending is taken out of the next month's Ready to Assign — the money
    was spent from an account, so the budget has to find it somewhere. Credit
    overspending stays as a negative category balance and quietly becomes debt
    the payment category has not covered.

    YNAB does not report which kind an overspend was, so it is inferred: an
    overspend is credit overspending up to the amount that category charged to
    a card that month, and cash for the remainder. That is exact for the common
    case of a category spent on one kind of account and an approximation when a
    category was spent from both in the same month.
    """
    months = month_sequence(from_month, to_month)
    fetched, credit_spend = await asyncio.gather(
        fetch_months(ctx, plan_id, months),
        _credit_spending_by_month(ctx, plan_id, months[0]),
    )

    by_month: list[dict[str, Any]] = []
    running_absorbed = 0
    total_cash = 0
    total_credit = 0

    for month in fetched:
        rows: list[dict[str, Any]] = []
        for category in visible(month.categories, include_hidden=include_hidden):
            if category.balance >= 0:
                continue
            overspent = -category.balance
            on_card = credit_spend.get((month.month, category.id), 0)
            credit_part = min(overspent, on_card)
            cash_part = overspent - credit_part
            total_cash += cash_part
            total_credit += credit_part
            rows.append(
                {
                    "id": category.id,
                    "group": category.category_group_name,
                    "name": category.name,
                    "budgeted": category.budgeted,
                    "activity": category.activity,
                    "balance": category.balance,
                    "overspent": overspent,
                    "overspent_display": milliunits_to_display(overspent),
                    "kind": "credit" if cash_part == 0 else ("cash" if credit_part == 0 else "mixed"),
                    "cash_overspend": cash_part,
                    "credit_overspend": credit_part,
                }
            )

        rows.sort(key=lambda r: int(r["overspent"]), reverse=True)
        month_cash = sum(int(r["cash_overspend"]) for r in rows)
        running_absorbed += month_cash
        by_month.append(
            {
                "month": month.month,
                "overspent_count": len(rows),
                "total_overspent": sum(int(r["overspent"]) for r in rows),
                "cash_overspend": month_cash,
                "cash_overspend_display": milliunits_to_display(month_cash),
                "credit_overspend": sum(int(r["credit_overspend"]) for r in rows),
                # Cash overspending in this month is taken out of the next
                # month's Ready to Assign, which is why a month can look
                # under-funded for a reason invisible inside it.
                "absorbed_into_ready_to_assign_running_total": running_absorbed,
                "absorbed_running_total_display": milliunits_to_display(running_absorbed),
                "categories": rows,
            }
        )

    repeat: dict[str, dict[str, Any]] = {}
    for entry in by_month:
        for row in entry["categories"]:
            seen = repeat.setdefault(
                row["id"],
                {"id": row["id"], "name": row["name"], "group": row["group"], "months": 0, "total_overspent": 0},
            )
            seen["months"] += 1
            seen["total_overspent"] += int(row["overspent"])

    worst = sorted(repeat.values(), key=lambda r: (-int(r["months"]), -int(r["total_overspent"])))[:15]
    for row in worst:
        row["total_overspent_display"] = milliunits_to_display(int(row["total_overspent"]))

    return {
        "scope": "overspent_history",
        "plan_id": plan_id,
        "from_month": months[0],
        "to_month": months[-1],
        "month_count": len(months),
        "total_cash_overspend": total_cash,
        "total_cash_overspend_display": milliunits_to_display(total_cash),
        "total_credit_overspend": total_credit,
        "total_credit_overspend_display": milliunits_to_display(total_credit),
        "absorbed_into_ready_to_assign": running_absorbed,
        "absorbed_into_ready_to_assign_display": milliunits_to_display(running_absorbed),
        "most_repeatedly_overspent": worst,
        "months": by_month,
        "note": (
            "Cash overspending is deducted from the following month's Ready to Assign; credit "
            "overspending carries forward as a negative category balance and as debt the payment "
            "category has not covered. The split is inferred from which accounts the category was "
            "spent on that month, because YNAB does not report it."
        ),
    }


def _group_totals(month: Month, group_id: str, *, include_hidden: bool) -> dict[str, Any]:
    members = [c for c in visible(month.categories, include_hidden=include_hidden) if c.category_group_id == group_id]
    return {
        "budgeted": sum(c.budgeted for c in members),
        "activity": sum(c.activity for c in members),
        "balance": sum(c.balance for c in members),
        "category_count": len(members),
        "name": members[0].category_group_name if members else None,
    }


async def group_parity(
    ctx: AppContext,
    plan_id: str,
    group_a_id: str,
    group_b_id: str,
    from_month: str,
    to_month: str | None = None,
    *,
    include_hidden: bool = False,
) -> dict[str, Any]:
    """Compare two category groups month by month, and report the gap.

    Plans that split money between two people keep paired groups — "his" and
    "hers", "partner A" and "partner B" — and the question asked of them is
    always the same: are these two being funded and spent evenly? Answering it
    from raw month data means two subtotals per month and a subtraction per
    month, done by hand.

    The gap is always A minus B.
    """
    months = month_sequence(from_month, to_month)
    fetched = await fetch_months(ctx, plan_id, months)

    rows: list[dict[str, Any]] = []
    name_a: str | None = None
    name_b: str | None = None
    totals = {"a_budgeted": 0, "b_budgeted": 0, "a_activity": 0, "b_activity": 0}

    for month in fetched:
        a = _group_totals(month, group_a_id, include_hidden=include_hidden)
        b = _group_totals(month, group_b_id, include_hidden=include_hidden)
        name_a = name_a or a["name"]
        name_b = name_b or b["name"]
        totals["a_budgeted"] += int(a["budgeted"])
        totals["b_budgeted"] += int(b["budgeted"])
        totals["a_activity"] += int(a["activity"])
        totals["b_activity"] += int(b["activity"])

        rows.append(
            {
                "month": month.month,
                "a": {k: a[k] for k in ("budgeted", "activity", "balance", "category_count")},
                "b": {k: b[k] for k in ("budgeted", "activity", "balance", "category_count")},
                "budgeted_gap": int(a["budgeted"]) - int(b["budgeted"]),
                "budgeted_gap_display": milliunits_to_display(int(a["budgeted"]) - int(b["budgeted"])),
                "activity_gap": int(a["activity"]) - int(b["activity"]),
                "activity_gap_display": milliunits_to_display(int(a["activity"]) - int(b["activity"])),
                "balance_gap": int(a["balance"]) - int(b["balance"]),
                "balance_gap_display": milliunits_to_display(int(a["balance"]) - int(b["balance"])),
            }
        )

    budgeted_gap = totals["a_budgeted"] - totals["b_budgeted"]
    activity_gap = totals["a_activity"] - totals["b_activity"]
    missing = [
        group_id
        for group_id, name in ((group_a_id, name_a), (group_b_id, name_b))
        if name is None  # no categories matched in any month
    ]

    result: dict[str, Any] = {
        "scope": "group_parity",
        "plan_id": plan_id,
        "from_month": months[0],
        "to_month": months[-1],
        "month_count": len(months),
        "group_a": {"id": group_a_id, "name": name_a, **{k[2:]: v for k, v in totals.items() if k.startswith("a_")}},
        "group_b": {"id": group_b_id, "name": name_b, **{k[2:]: v for k, v in totals.items() if k.startswith("b_")}},
        "total_budgeted_gap": budgeted_gap,
        "total_budgeted_gap_display": milliunits_to_display(budgeted_gap),
        "total_activity_gap": activity_gap,
        "total_activity_gap_display": milliunits_to_display(activity_gap),
        "months": rows,
        "note": (
            "Gaps are group A minus group B. Activity is negative for spending, so a negative "
            "activity gap means A spent more."
        ),
    }
    if missing:
        result["warning"] = (
            f"No categories were found for group id(s) {missing} in any month of the range. "
            "Check the ids with categories_list."
        )
    return result


async def copied_forward_months(
    ctx: AppContext,
    plan_id: str,
    from_month: str | None = None,
    to_month: str | None = None,
    *,
    include_hidden: bool = False,
) -> dict[str, Any]:
    """Flag months whose assignments are a verbatim copy of the month before.

    YNAB offers "assign last month's amounts", and applied without looking it
    carries one-off moves forward as though they were the plan. On the budget
    this was written for, September repeated August exactly, a $10,000 one-time
    transfer included, and finding it took a diff of two 50 KB documents.

    The month before `from_month` is read as well, so the first month in the
    range can be compared to something.
    """
    end = normalize_month(to_month or date.today().replace(day=1).isoformat(), field="to_month")
    if from_month is None:
        year, month = int(end[:4]), int(end[5:7]) - 11
        while month <= 0:
            year, month = year - 1, month + 12
        start = date(year, month, 1).isoformat()
    else:
        start = normalize_month(from_month, field="from_month")

    # One extra month at the front: the first month of the range needs a
    # predecessor or it cannot be judged.
    prior_year, prior_month = int(start[:4]), int(start[5:7]) - 1
    if prior_month == 0:
        prior_year, prior_month = prior_year - 1, 12
    months = month_sequence(date(prior_year, prior_month, 1).isoformat(), end)

    fetched = await fetch_months(ctx, plan_id, months)
    assignments = [
        {c.id: c.budgeted for c in visible(month.categories, include_hidden=include_hidden)} for month in fetched
    ]

    rows: list[dict[str, Any]] = []
    for index in range(1, len(fetched)):
        current, previous = assignments[index], assignments[index - 1]
        shared = current.keys() & previous.keys()
        differences = [cid for cid in shared if current[cid] != previous[cid]]
        added = current.keys() - previous.keys()
        assigned_anything = any(value for value in current.values())
        identical = not differences and not added and assigned_anything

        row: dict[str, Any] = {
            "month": fetched[index].month,
            "compared_to": fetched[index - 1].month,
            "identical_assignments": identical,
            "categories_compared": len(shared),
            "categories_differing": len(differences) + len(added),
            "total_budgeted": sum(current.values()),
            "total_budgeted_display": milliunits_to_display(sum(current.values())),
        }
        if identical:
            names = {c.id: c.name for c in fetched[index].categories}
            carried = [
                {"id": cid, "name": names.get(cid), "budgeted": value, "budgeted_display": milliunits_to_display(value)}
                for cid, value in sorted(current.items(), key=lambda kv: abs(kv[1]), reverse=True)
                if value
            ][:10]
            row["largest_assignments_carried_forward"] = carried
        rows.append(row)

    copied = [r["month"] for r in rows if r["identical_assignments"]]
    return {
        "scope": "copied_forward_months",
        "plan_id": plan_id,
        "from_month": start,
        "to_month": end,
        "month_count": len(rows),
        "copied_forward_count": len(copied),
        "copied_forward_months": copied,
        "months": rows,
        "note": (
            "A month is flagged when every category's assigned amount equals the previous month's and "
            "something was actually assigned. That is the signature of 'assign last month's amounts' "
            "applied without review, which carries one-off assignments forward as if they were the plan."
        ),
    }


async def flow_trace(
    ctx: AppContext,
    plan_id: str,
    category_id: str,
    from_month: str,
    to_month: str | None = None,
) -> dict[str, Any]:
    """Where one category's money came from and went, month by month.

    Assigned in, moved in and out, spent, refunded, and what was left. This is
    the question a partner actually asks — "what happened to the holiday money"
    — and it needs three different YNAB resources to answer, because assigning,
    moving, and spending are three different records.
    """
    months = month_sequence(from_month, to_month)
    fetched, movements_resp, txn_resp = await asyncio.gather(
        fetch_months(ctx, plan_id, months),
        ctx.money_movements.list(plan_id),
        ctx.transactions.list_by_category(plan_id, category_id, since_date=months[0]),
    )

    moved_in: dict[str, int] = {}
    moved_out: dict[str, int] = {}
    for movement in movements_resp.data.money_movements:
        if movement.deleted or movement.month not in set(months):
            continue
        if movement.to_category_id == category_id:
            moved_in[movement.month] = moved_in.get(movement.month, 0) + movement.amount
        if movement.from_category_id == category_id:
            moved_out[movement.month] = moved_out.get(movement.month, 0) + movement.amount

    spent: dict[str, int] = {}
    refunds: dict[str, int] = {}
    txn_count: dict[str, int] = {}
    for txn in txn_resp.data.transactions:
        if txn.deleted:
            continue
        stamp = _month_of(txn.date)
        txn_count[stamp] = txn_count.get(stamp, 0) + 1
        if txn.amount < 0:
            spent[stamp] = spent.get(stamp, 0) + -txn.amount
        else:
            refunds[stamp] = refunds.get(stamp, 0) + txn.amount

    rows: list[dict[str, Any]] = []
    name: str | None = None
    for month in fetched:
        match = next((c for c in month.categories if c.id == category_id), None)
        if match is not None:
            name = match.name
        rows.append(
            {
                "month": month.month,
                "assigned": match.budgeted if match else None,
                "assigned_display": milliunits_to_display(match.budgeted) if match else None,
                "moved_in": moved_in.get(month.month, 0),
                "moved_out": moved_out.get(month.month, 0),
                "spent": spent.get(month.month, 0),
                "spent_display": milliunits_to_display(spent.get(month.month, 0)),
                "refunds": refunds.get(month.month, 0),
                "transaction_count": txn_count.get(month.month, 0),
                "balance": match.balance if match else None,
                "balance_display": milliunits_to_display(match.balance) if match else None,
            }
        )

    return {
        "scope": "flow_trace",
        "plan_id": plan_id,
        "category_id": category_id,
        "category_name": name,
        "from_month": months[0],
        "to_month": months[-1],
        "totals": {
            "assigned": sum(int(r["assigned"] or 0) for r in rows),
            "moved_in": sum(int(r["moved_in"]) for r in rows),
            "moved_out": sum(int(r["moved_out"]) for r in rows),
            "spent": sum(int(r["spent"]) for r in rows),
            "refunds": sum(int(r["refunds"]) for r in rows),
        },
        "months": rows,
        "note": (
            "`assigned` is the month's budgeted figure, which already reflects any money moved into or "
            "out of the category that month — moved_in and moved_out are shown separately so a large "
            "assignment can be told apart from a large transfer. `spent` and `refunds` are positive "
            "numbers. A category with no row data in a month did not exist yet."
        ),
    }


async def balance_identity(ctx: AppContext, plan_id: str) -> dict[str, Any]:
    """Check that the plan's categories, Ready to Assign, and accounts agree.

    Every dollar assigned to a category is a dollar sitting in an on-budget
    account, so:

        categories + Ready to Assign  =  on-budget accounts + credit-card debt

    which is the same statement as "the money in your accounts, plus the money
    your cards have borrowed on your behalf, is exactly the money your budget
    has spoken for". It holds whether or not the cards are properly funded, so
    a mismatch is a data problem — a stale read, a category the API did not
    return, an account the plan is not counting — rather than a budgeting one.

    Running it first is what makes the rest of a review trustworthy.
    """
    accounts_resp, categories_resp, month_resp = await asyncio.gather(
        ctx.accounts.list(plan_id),
        ctx.categories.list(plan_id),
        ctx.months.get(plan_id, date.today().replace(day=1).isoformat()),
    )

    groups = [g for g in categories_resp.data.category_groups if not g.deleted]
    internal = [g for g in groups if g.name.strip().lower() == INTERNAL_GROUP_NAME]
    internal_ids = {g.id for g in internal}

    # The internal group holds "Inflow: Ready to Assign", whose balance is
    # cumulative income rather than available money. Counting it would inflate
    # the category side by the whole history of the plan.
    counted = [c for g in groups if g.id not in internal_ids for c in g.categories if not c.deleted]
    category_total = sum(c.balance for c in counted)
    ready_to_assign = month_resp.data.month.to_be_budgeted

    accounts = [a for a in accounts_resp.data.accounts if not a.deleted]
    on_budget = [a for a in accounts if a.on_budget]
    on_budget_total = sum(a.balance for a in on_budget)
    card_debt = sum(-a.balance for a in on_budget if a.type in _CREDIT_TYPES and a.balance < 0)

    budget_side = category_total + ready_to_assign
    account_side = on_budget_total + card_debt
    difference = budget_side - account_side

    return {
        "scope": "balance_identity",
        "plan_id": plan_id,
        "as_of": date.today().isoformat(),
        "ties": difference == 0,
        "difference": difference,
        "difference_display": milliunits_to_display(difference),
        "budget_side": {
            "total": budget_side,
            "total_display": milliunits_to_display(budget_side),
            "category_balances": category_total,
            "category_balances_display": milliunits_to_display(category_total),
            "category_count": len(counted),
            "ready_to_assign": ready_to_assign,
            "ready_to_assign_display": milliunits_to_display(ready_to_assign),
        },
        "account_side": {
            "total": account_side,
            "total_display": milliunits_to_display(account_side),
            "on_budget_balances": on_budget_total,
            "on_budget_balances_display": milliunits_to_display(on_budget_total),
            "on_budget_account_count": len(on_budget),
            "credit_card_debt": card_debt,
            "credit_card_debt_display": milliunits_to_display(card_debt),
        },
        "excluded_internal_categories": [
            {"id": c.id, "name": c.name, "balance": c.balance, "balance_display": milliunits_to_display(c.balance)}
            for g in internal
            for c in g.categories
            if not c.deleted
        ],
        "note": (
            "categories + Ready to Assign = on-budget accounts + credit-card debt. Hidden categories, "
            "including credit-card payment categories, are counted; YNAB's internal group is not, "
            "because its 'Inflow: Ready to Assign' balance is cumulative income rather than available "
            "money. It is listed above so an unexpected balance there is still visible. A non-zero "
            "difference means the data is inconsistent, not that the budget is unhealthy."
        ),
    }
