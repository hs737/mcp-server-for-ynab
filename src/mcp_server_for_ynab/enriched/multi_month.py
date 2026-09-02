"""Reading a range of months without drowning the caller in JSON.

One `months_get` against a real plan is about 59 KB: ninety categories, each
carrying every goal field YNAB tracks, hidden ones included. Reviewing
twenty-one months that way is twenty-one calls that each overflow a context
window, and the reviewer ends up parsing files off disk instead of reading a
budget.

Two things fix that, and both live here. `compact_category` keeps the six
fields a month-over-month review actually uses and drops the rest, which
measured about four times smaller on that plan. `month_series` turns a range
into one matrix keyed by category, so a twenty-one-month audit is one tool call
whose shape can be read straight down a column instead of twenty-one documents
to be joined by hand.

What this does not save is requests. YNAB has no range route, so a twelve-month
window is still twelve GETs against an hourly limit of 200. Every tool built on
this says so in its description, and the range is capped.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpError, YnabMcpException
from mcp_server_for_ynab.models.ynab.categories import Category
from mcp_server_for_ynab.models.ynab.months import Month
from mcp_server_for_ynab.server.context import AppContext

# A range longer than this would spend most of an hour's request budget in one
# call. Three years is more than any review has needed and leaves room to work
# afterwards.
MAX_RANGE_MONTHS = 36

# YNAB tolerates parallel reads, but firing thirty-six at once is a good way to
# collect a 429 for no gain — the wall-clock difference against six at a time is
# not worth it.
_CONCURRENCY = 6


def _fail(message: str) -> YnabMcpException:
    return YnabMcpException(YnabMcpError(error_type=ErrorType.VALIDATION_ERROR, message=message))


def current_month() -> str:
    return date.today().replace(day=1).isoformat()


def normalize_month(value: str, *, field: str = "month") -> str:
    """Accept 'current', 'YYYY-MM', or any ISO date, and return the first of that month.

    Agents write months three different ways and YNAB accepts only one of them.
    Rejecting '2025-03' with a 400 from the API teaches nothing; normalising it
    costs a line.
    """
    text = (value or "").strip()
    if not text:
        raise _fail(f"{field} is required. Pass 'current', 'YYYY-MM', or 'YYYY-MM-DD'.")
    if text.lower() == "current":
        return current_month()

    parts = text.split("-")
    try:
        if len(parts) == 2:
            year, month = int(parts[0]), int(parts[1])
            return date(year, month, 1).isoformat()
        return date.fromisoformat(text).replace(day=1).isoformat()
    except ValueError as exc:
        raise _fail(f"{field} {value!r} is not a month. Pass 'current', 'YYYY-MM', or 'YYYY-MM-DD'. ({exc})") from exc


def month_sequence(from_month: str, to_month: str | None = None) -> list[str]:
    """Every first-of-month between two bounds, inclusive."""
    start = normalize_month(from_month, field="from_month")
    end = normalize_month(to_month or current_month(), field="to_month")
    if end < start:
        raise _fail(f"from_month {start} is after to_month {end}.")

    months: list[str] = []
    year, month = int(start[:4]), int(start[5:7])
    while True:
        stamp = date(year, month, 1).isoformat()
        if stamp > end:
            break
        months.append(stamp)
        if len(months) > MAX_RANGE_MONTHS:
            raise _fail(
                f"{start} to {end} is more than {MAX_RANGE_MONTHS} months. "
                "Each month is one request against YNAB's hourly limit, so long ranges are refused. "
                "Split the review into shorter windows."
            )
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


async def fetch_months(ctx: AppContext, plan_id: str, months: list[str]) -> list[Month]:
    """Read several months, in order, a few at a time."""
    gate = asyncio.Semaphore(_CONCURRENCY)

    async def one(stamp: str) -> Month:
        async with gate:
            response = await ctx.months.get(plan_id, stamp)
            return response.data.month

    return list(await asyncio.gather(*(one(stamp) for stamp in months)))


def visible(categories: list[Category], *, include_hidden: bool = False) -> list[Category]:
    """Drop deleted categories, and hidden ones unless asked for.

    Hidden is not a display preference in YNAB: a category's credit-card payment
    counterpart lives in a hidden group, so `include_hidden=True` is how those
    enter a report at all.
    """
    return [c for c in categories if not c.deleted and (include_hidden or not c.hidden)]


def compact_category(category: Category) -> dict[str, Any]:
    """The six fields a month-over-month review reads, and nothing else."""
    return {
        "id": category.id,
        "group": category.category_group_name,
        "name": category.name,
        "budgeted": category.budgeted,
        "activity": category.activity,
        "balance": category.balance,
    }


def month_totals(month: Month) -> dict[str, Any]:
    return {
        "month": month.month,
        "income": month.income,
        "budgeted": month.budgeted,
        "activity": month.activity,
        "to_be_budgeted": month.to_be_budgeted,
        "age_of_money": month.age_of_money,
    }


def _selected(
    categories: list[Category],
    *,
    category_ids: list[str] | None,
    group_ids: list[str] | None,
) -> list[Category]:
    if category_ids:
        wanted = set(category_ids)
        return [c for c in categories if c.id in wanted]
    if group_ids:
        wanted = set(group_ids)
        return [c for c in categories if c.category_group_id in wanted]
    return categories


async def month_series(
    ctx: AppContext,
    plan_id: str,
    from_month: str,
    to_month: str | None = None,
    *,
    category_ids: list[str] | None = None,
    group_ids: list[str] | None = None,
    include_hidden: bool = False,
) -> dict[str, Any]:
    """A category-by-month matrix of budgeted, activity, and balance.

    The unit of a budget review is a row read across time — "what happened to
    groceries over eighteen months" — and that question answered from
    `months_get` means eighteen documents and a join. Here it is one row.
    """
    months = month_sequence(from_month, to_month)
    fetched = await fetch_months(ctx, plan_id, months)

    # Categories are keyed by id rather than accumulated per month, because a
    # category renamed or moved between groups mid-range must stay one row. The
    # latest month wins for the descriptive fields.
    rows: dict[str, dict[str, Any]] = {}
    for month in fetched:
        chosen = _selected(
            visible(month.categories, include_hidden=include_hidden),
            category_ids=category_ids,
            group_ids=group_ids,
        )
        for category in chosen:
            row = rows.setdefault(category.id, {"id": category.id, "series": []})
            row["group"] = category.category_group_name
            row["group_id"] = category.category_group_id
            row["name"] = category.name
            row["series"].append(
                {
                    "month": month.month,
                    "budgeted": category.budgeted,
                    "activity": category.activity,
                    "balance": category.balance,
                }
            )

    ordered = sorted(rows.values(), key=lambda r: (r.get("group") or "", r.get("name") or ""))
    return {
        "scope": "months_range",
        "plan_id": plan_id,
        "from_month": months[0],
        "to_month": months[-1],
        "months": months,
        "month_count": len(months),
        "category_count": len(ordered),
        "include_hidden": include_hidden,
        "amounts": "milliunits (1000 = $1.00)",
        "month_totals": [month_totals(month) for month in fetched],
        "categories": ordered,
    }


async def group_series(
    ctx: AppContext,
    plan_id: str,
    from_month: str,
    to_month: str | None = None,
    *,
    include_hidden: bool = True,
) -> dict[str, Any]:
    """Per-group, per-month totals of budgeted, activity, and balance.

    Most "is this budget healthy" questions live at group level, and a group
    view is small enough to read whole. Hidden categories are included by
    default here, unlike everywhere else: leaving them out would silently drop
    the credit-card payment group, which is exactly the part of a plan that
    goes wrong unnoticed.
    """
    months = month_sequence(from_month, to_month)
    fetched = await fetch_months(ctx, plan_id, months)

    groups: dict[str, dict[str, Any]] = {}
    for month in fetched:
        totals: dict[str, dict[str, Any]] = {}
        for category in visible(month.categories, include_hidden=include_hidden):
            bucket = totals.setdefault(
                category.category_group_id,
                {"budgeted": 0, "activity": 0, "balance": 0, "category_count": 0},
            )
            bucket["budgeted"] += category.budgeted
            bucket["activity"] += category.activity
            bucket["balance"] += category.balance
            bucket["category_count"] += 1

            group = groups.setdefault(
                category.category_group_id,
                {"group_id": category.category_group_id, "series": []},
            )
            group["group"] = category.category_group_name

        for group_id, bucket in totals.items():
            groups[group_id]["series"].append({"month": month.month, **bucket})

    ordered = sorted(groups.values(), key=lambda g: g.get("group") or "")
    return {
        "scope": "category_groups_summary_by_month",
        "plan_id": plan_id,
        "from_month": months[0],
        "to_month": months[-1],
        "months": months,
        "month_count": len(months),
        "group_count": len(ordered),
        "include_hidden": include_hidden,
        "amounts": "milliunits (1000 = $1.00)",
        "month_totals": [month_totals(month) for month in fetched],
        "groups": ordered,
    }
