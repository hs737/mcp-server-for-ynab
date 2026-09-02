"""Credit cards, lines of credit, and the money that is supposed to pay them.

A credit account in YNAB has a shadow: a category in the hidden "Credit Card
Payments" group, named identically to the account. Spending on the card moves
budgeted money into that category, and paying the card spends it. When the two
agree, the debt is funded. When they do not, nothing in the budget says so —
the category is hidden, the account balance looks like any other liability, and
the shortfall only surfaces when the statement is due.

Two failures are worth naming because neither is visible anywhere else:

**Unfunded debt.** The card owes more than its payment category holds. The
difference is debt the plan has not actually set money aside for.

**Trapped funds.** An account was closed, but its payment category kept the
money that was assigned to it. On the plan this was written against, $4,545 sat
in the payment category of a card closed months earlier — money the budget
counted as spoken for and the user could not find.

The account-to-category link is by name, because the API offers no identifier
tying them together. Names are exact on every plan we have seen, trailing
whitespace included, so matching is exact first and whitespace-insensitive as a
fallback; anything still unmatched is reported rather than silently dropped.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from mcp_server_for_ynab.enriched.multi_month import fetch_months, month_sequence
from mcp_server_for_ynab.models.amounts import milliunits_to_display
from mcp_server_for_ynab.models.ynab.accounts import Account, AccountType
from mcp_server_for_ynab.models.ynab.categories import Category, CategoryGroup
from mcp_server_for_ynab.server.context import AppContext

CREDIT_ACCOUNT_TYPES = frozenset({AccountType.CREDIT_CARD, AccountType.LINE_OF_CREDIT})

# YNAB names this group the same way in every plan and marks it hidden. The
# group's `internal` flag is not a reliable discriminator — live plans set it on
# ordinary user groups too — so the name is what identifies it.
PAYMENT_GROUP_NAME = "credit card payments"


def payment_group(groups: list[CategoryGroup]) -> CategoryGroup | None:
    for group in groups:
        if group.name.strip().lower() == PAYMENT_GROUP_NAME and not group.deleted:
            return group
    return None


def _key(name: str) -> str:
    return name.strip().lower()


def credit_position(accounts: list[Account], groups: list[CategoryGroup]) -> dict[str, Any]:
    """Match credit accounts to their payment categories. No I/O.

    Kept separate from the tool so `overview_budget_snapshot`, which already
    holds both lists, can report unfunded debt and trapped funds without
    spending two more requests.
    """
    group = payment_group(groups)
    categories: list[Category] = [c for c in group.categories if not c.deleted] if group else []
    by_name: dict[str, Category] = {_key(c.name): c for c in categories}

    credit_accounts = [a for a in accounts if a.type in CREDIT_ACCOUNT_TYPES and not a.deleted]
    matched_category_ids: set[str] = set()
    rows: list[dict[str, Any]] = []

    for account in sorted(credit_accounts, key=lambda a: a.name):
        category = by_name.get(_key(account.name))
        if category is not None:
            matched_category_ids.add(category.id)

        # A credit account's balance is negative when money is owed. A positive
        # balance is an overpaid card, which is not debt and must not be
        # reported as funded debt.
        debt = -account.balance if account.balance < 0 else 0
        funded = category.balance if category else None
        unfunded = max(0, debt - funded) if funded is not None else None

        row: dict[str, Any] = {
            "account_id": account.id,
            "account_name": account.name,
            "type": account.type,
            "closed": account.closed,
            "balance": account.balance,
            "balance_display": milliunits_to_display(account.balance),
            "debt": debt,
            "debt_display": milliunits_to_display(debt),
            "payment_category_id": category.id if category else None,
            "payment_category_name": category.name if category else None,
            "funded": funded,
            "funded_display": milliunits_to_display(funded) if funded is not None else None,
            "unfunded": unfunded,
            "unfunded_display": milliunits_to_display(unfunded) if unfunded is not None else None,
            "fully_funded": None if funded is None else unfunded == 0,
        }

        if category is None:
            row["note"] = (
                "No payment category with this account's name. Either the category was renamed, "
                "or this account is not a YNAB credit account with a payment category."
            )
        elif account.closed and category.balance > 0:
            row["trapped"] = category.balance
            row["trapped_display"] = milliunits_to_display(category.balance)
            row["note"] = (
                "This account is closed but its payment category still holds money. "
                "Those funds are assigned to a card that can no longer be paid; move them "
                "back to Ready to Assign or to another category."
            )
        elif category.balance < 0:
            row["note"] = (
                "The payment category is negative, which means spending on this card was not "
                "covered by its spending categories. The shortfall carries forward."
            )

        rows.append(row)

    unmatched: list[dict[str, Any]] = [
        {
            "category_id": c.id,
            "category_name": c.name,
            "balance": c.balance,
            "balance_display": milliunits_to_display(c.balance),
        }
        for c in categories
        if c.id not in matched_category_ids
    ]

    total_debt = sum(int(r["debt"]) for r in rows)
    total_funded = sum(int(r["funded"] or 0) for r in rows)
    total_unfunded = sum(int(r["unfunded"] or 0) for r in rows)
    trapped = sum(int(r.get("trapped") or 0) for r in rows) + sum(
        int(u["balance"]) for u in unmatched if int(u["balance"]) > 0
    )

    return {
        "payment_group_found": group is not None,
        "payment_group_id": group.id if group else None,
        "credit_account_count": len(rows),
        "total_card_debt": total_debt,
        "total_card_debt_display": milliunits_to_display(total_debt),
        "total_payment_funds": total_funded,
        "total_payment_funds_display": milliunits_to_display(total_funded),
        "total_unfunded_debt": total_unfunded,
        "total_unfunded_debt_display": milliunits_to_display(total_unfunded),
        "trapped_funds": trapped,
        "trapped_funds_display": milliunits_to_display(trapped),
        "accounts": rows,
        "unmatched_payment_categories": unmatched,
    }


async def credit_funding(ctx: AppContext, plan_id: str, *, months: int = 6) -> dict[str, Any]:
    """Report funded and unfunded card debt, trapped funds, and payment-category history.

    `months` months of history cost one request each, on top of the two this
    tool always makes. Pass 0 to skip the history.
    """
    import asyncio

    accounts_resp, categories_resp = await asyncio.gather(
        ctx.accounts.list(plan_id),
        ctx.categories.list(plan_id),
    )

    position = credit_position(accounts_resp.data.accounts, categories_resp.data.category_groups)
    group_id = position["payment_group_id"]

    history: list[dict[str, Any]] = []
    if months > 0 and group_id:
        today = date.today()
        first = today.replace(day=1)
        start_year, start_month = first.year, first.month - (months - 1)
        while start_month <= 0:
            start_year, start_month = start_year - 1, start_month + 12
        stamps = month_sequence(f"{start_year:04d}-{start_month:02d}", first.isoformat())
        for month in await fetch_months(ctx, plan_id, stamps):
            negatives = [
                {
                    "category_id": c.id,
                    "name": c.name,
                    "balance": c.balance,
                    "balance_display": milliunits_to_display(c.balance),
                }
                for c in month.categories
                if c.category_group_id == group_id and c.balance < 0 and not c.deleted
            ]
            if negatives:
                history.append({"month": month.month, "negative_payment_categories": negatives})

    return {
        "scope": "credit_funding",
        "plan_id": plan_id,
        "as_of": date.today().isoformat(),
        **position,
        "months_of_history": months,
        "payment_category_negatives_by_month": history,
        "note": (
            "Unfunded debt is what a card owes beyond what its payment category holds. "
            "Trapped funds are money sitting in the payment category of a closed account, or in a "
            "payment category with no matching account — it is assigned to a card that cannot be paid. "
            "Accounts and payment categories are matched by name; YNAB provides no identifier linking them."
        ),
    }
