"""Enriched triage tools: what actually needs a human's attention.

A triage queue is only useful if everything in it is work. YNAB's
`type=uncategorized` filter is not that queue: on a real plan it returned 533
transactions, of which about fourteen needed anything. The rest were
transactions on an off-budget tracking account, which never take a category,
and transfers between two on-budget accounts, which never take one either. A
count of 533 tells the user their budget is a disaster and tells an agent to
fetch 195 KB of JSON to find out otherwise.

So the queues here exclude what cannot be worked on, say how many they
excluded and why, and report a count that means "this many things need you".
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from mcp_server_for_ynab.models.amounts import milliunits_to_display
from mcp_server_for_ynab.models.ynab.accounts import Account
from mcp_server_for_ynab.models.ynab.transactions import ClearedStatus, Transaction
from mcp_server_for_ynab.server.context import AppContext

DEFAULT_PAGE = 100

# How long an uncleared manual entry on a bank-linked account has to sit before
# it stops looking like something in flight and starts looking like a
# duplicate, a typo, or a payment that never happened.
DEFAULT_STALE_DAYS = 30

# Reconciling is a monthly habit for most people; a couple of months of silence
# is where the balances start drifting unnoticed.
DEFAULT_RECONCILE_STALE_DAYS = 45


def _page(items: list[Any], limit: int, offset: int) -> tuple[list[Any], dict[str, Any]]:
    window = items[offset : offset + max(1, limit)]
    meta: dict[str, Any] = {
        "returned": len(window),
        "offset": offset,
        "limit": limit,
        "has_more": offset + len(window) < len(items),
    }
    if meta["has_more"]:
        meta["next_offset"] = offset + len(window)
    return window, meta


def _classify(
    transactions: list[Transaction],
    accounts: list[Account],
    *,
    include_transfers: bool,
    include_tracking_accounts: bool,
) -> tuple[list[Transaction], dict[str, int]]:
    """Split a queue into work and noise.

    Two kinds of transaction are in YNAB's uncategorized list and can never
    leave it by being categorized:

    - anything on an off-budget (tracking) account, which has no budget to
      categorize against
    - a transfer between two on-budget accounts, which moves money the budget
      already accounts for

    A transfer from an on-budget account *to* a tracking account is different:
    that money leaves the budget and does need a category, so it stays.
    """
    on_budget = {a.id for a in accounts if a.on_budget and not a.deleted}
    tracking = {a.id for a in accounts if not a.on_budget and not a.deleted}

    kept: list[Transaction] = []
    excluded = {"tracking_account": 0, "on_budget_transfer": 0}

    for txn in transactions:
        if txn.account_id in tracking:
            excluded["tracking_account"] += 1
            if not include_tracking_accounts:
                continue
        elif txn.transfer_account_id and txn.transfer_account_id in on_budget:
            excluded["on_budget_transfer"] += 1
            if not include_transfers:
                continue
        kept.append(txn)

    return kept, excluded


async def _uncategorized(
    ctx: AppContext,
    plan_id: str,
    *,
    include_transfers: bool,
    include_tracking_accounts: bool,
) -> tuple[list[Transaction], dict[str, int], int, int]:
    import asyncio

    resp, accounts_resp = await asyncio.gather(
        ctx.transactions.list(plan_id, type="uncategorized"),
        ctx.accounts.list(plan_id),
    )
    raw = [t for t in resp.data.transactions if not t.deleted]
    kept, excluded = _classify(
        raw,
        accounts_resp.data.accounts,
        include_transfers=include_transfers,
        include_tracking_accounts=include_tracking_accounts,
    )
    kept.sort(key=lambda t: t.date, reverse=True)
    return kept, excluded, len(raw), resp.data.server_knowledge


async def triage_uncategorized(
    ctx: AppContext,
    plan_id: str,
    *,
    include_transfers: bool = False,
    include_tracking_accounts: bool = False,
    limit: int = DEFAULT_PAGE,
    offset: int = 0,
) -> dict[str, Any]:
    """Transactions that genuinely need a category, most-recent first."""
    kept, excluded, raw_count, server_knowledge = await _uncategorized(
        ctx,
        plan_id,
        include_transfers=include_transfers,
        include_tracking_accounts=include_tracking_accounts,
    )
    window, meta = _page(kept, limit, offset)

    return {
        "scope": "triage_uncategorized",
        "plan_id": plan_id,
        "count": len(kept),
        "raw_count": raw_count,
        "excluded": excluded,
        "excluded_total": raw_count - len(kept),
        "filters": {
            "include_transfers": include_transfers,
            "include_tracking_accounts": include_tracking_accounts,
        },
        **meta,
        "server_knowledge": server_knowledge,
        "transactions": [_slim(t) for t in window],
        "note": (
            "count is the number needing a category. raw_count is what YNAB's uncategorized filter "
            "returned before transactions on tracking accounts and transfers between on-budget "
            "accounts were removed — neither can be categorized."
        ),
    }


async def triage_unapproved(
    ctx: AppContext,
    plan_id: str,
    *,
    limit: int = DEFAULT_PAGE,
    offset: int = 0,
) -> dict[str, Any]:
    """Return all unapproved transactions, most-recent first."""
    resp = await ctx.transactions.list(plan_id, type="unapproved")
    txns = [t for t in resp.data.transactions if not t.deleted]
    txns.sort(key=lambda t: t.date, reverse=True)
    window, meta = _page(txns, limit, offset)

    return {
        "scope": "triage_unapproved",
        "plan_id": plan_id,
        "count": len(txns),
        **meta,
        "server_knowledge": resp.data.server_knowledge,
        "transactions": [_slim(t) for t in window],
    }


async def triage_summary(ctx: AppContext, plan_id: str) -> dict[str, Any]:
    """Combined count of pending work: uncategorized + unapproved transactions."""
    import asyncio

    (kept, excluded, raw_count, _), unapproved_resp = await asyncio.gather(
        _uncategorized(ctx, plan_id, include_transfers=False, include_tracking_accounts=False),
        ctx.transactions.list(plan_id, type="unapproved"),
    )
    unapproved = [t for t in unapproved_resp.data.transactions if not t.deleted]

    return {
        "scope": "triage_summary",
        "plan_id": plan_id,
        "as_of": date.today().isoformat(),
        "uncategorized_count": len(kept),
        "uncategorized_raw_count": raw_count,
        "uncategorized_excluded": excluded,
        "unapproved_count": len(unapproved),
        "total_pending": len(kept) + len(unapproved),
        "needs_attention": bool(kept) or bool(unapproved),
        "note": (
            "uncategorized_count excludes transactions that cannot take a category: those on "
            "off-budget tracking accounts, and transfers between two on-budget accounts."
        ),
    }


async def unmatched_manual(
    ctx: AppContext,
    plan_id: str,
    *,
    account_id: str | None = None,
    older_than_days: int = DEFAULT_STALE_DAYS,
    since_date: str | None = None,
) -> dict[str, Any]:
    """Hand-entered transactions on bank-linked accounts that never cleared.

    On an account YNAB imports from, a manual entry is a promise that a real
    transaction is coming. When one sits uncleared for weeks, the bank never
    produced a match: the entry is a duplicate of something already imported, a
    payment that did not go through, or a typo. Either way YNAB and the bank
    disagree by exactly that amount, and nothing else in the tool surface points
    at it.

    On the plan this was written for, ten such entries on one checking account
    summed to $9,469 — the whole of the difference between YNAB and the bank.
    """
    import asyncio

    start = since_date or (date.today() - timedelta(days=545)).isoformat()
    cutoff = (date.today() - timedelta(days=max(0, older_than_days))).isoformat()

    accounts_resp, txn_resp = await asyncio.gather(
        ctx.accounts.list(plan_id),
        ctx.transactions.list(plan_id, since_date=start),
    )

    accounts = {
        a.id: a for a in accounts_resp.data.accounts if not a.deleted and (account_id is None or a.id == account_id)
    }
    # An unlinked account is reconciled by hand, so an uncleared entry there is
    # normal bookkeeping rather than a mismatch.
    linked = {a.id for a in accounts.values() if a.direct_import_linked}

    stale = [
        t
        for t in txn_resp.data.transactions
        if not t.deleted
        and t.account_id in linked
        and t.import_id is None
        and t.cleared == ClearedStatus.UNCLEARED
        and t.date <= cutoff
    ]
    stale.sort(key=lambda t: t.date)

    by_account: dict[str, dict[str, Any]] = {}
    for txn in stale:
        bucket = by_account.setdefault(
            txn.account_id,
            {
                "account_id": txn.account_id,
                "account_name": accounts[txn.account_id].name,
                "count": 0,
                "net_amount": 0,
                "oldest": txn.date,
            },
        )
        bucket["count"] += 1
        bucket["net_amount"] += txn.amount
        bucket["oldest"] = min(str(bucket["oldest"]), txn.date)

    for bucket in by_account.values():
        bucket["net_amount_display"] = milliunits_to_display(int(bucket["net_amount"]))

    net = sum(t.amount for t in stale)
    return {
        "scope": "triage_unmatched_manual",
        "plan_id": plan_id,
        "as_of": date.today().isoformat(),
        "since_date": start,
        "older_than_days": older_than_days,
        "cutoff_date": cutoff,
        "linked_account_count": len(linked),
        "count": len(stale),
        "net_amount": net,
        "net_amount_display": milliunits_to_display(net),
        "by_account": sorted(by_account.values(), key=lambda b: abs(int(b["net_amount"])), reverse=True),
        "transactions": [_slim(t) for t in stale],
        "note": (
            "These are transactions with no import_id — entered by hand — still uncleared on an account "
            "YNAB imports from. Their net amount is how far YNAB's balance stands from the bank's for "
            "these entries alone. Each is a duplicate, a payment that never landed, or an entry to fix."
        ),
    }


async def reconciliation(
    ctx: AppContext,
    plan_id: str,
    *,
    stale_after_days: int = DEFAULT_RECONCILE_STALE_DAYS,
) -> dict[str, Any]:
    """Accounts ranked by how long it has been since anyone reconciled them.

    Reconciliation is what makes every other number in a plan trustworthy, and
    it is the one fact no other tool here reports. An account last reconciled
    eleven months ago is not a small problem: everything downstream of it —
    balances, category activity, the identity check — inherits whatever drifted
    in the meantime.
    """
    resp = await ctx.accounts.list(plan_id)
    today = date.today()

    rows: list[dict[str, Any]] = []
    for account in resp.data.accounts:
        if account.deleted:
            continue

        age: int | None = None
        if account.last_reconciled_at:
            try:
                age = (today - date.fromisoformat(account.last_reconciled_at[:10])).days
            except ValueError:  # pragma: no cover - defensive against a shape change
                age = None

        warnings: list[str] = []
        if account.last_reconciled_at is None:
            warnings.append("Never reconciled.")
        elif age is not None and age > stale_after_days:
            warnings.append(f"Last reconciled {age} days ago.")
        if account.on_budget and account.type in ("checking", "savings", "cash") and account.cleared_balance < 0:
            warnings.append(
                "Cleared balance is negative on a cash account, which means the bank shows an overdraft "
                "or the account holds transactions it should not."
            )
        if account.direct_import_in_error:
            warnings.append("YNAB's bank connection for this account is in an error state.")

        rows.append(
            {
                "account_id": account.id,
                "name": account.name,
                "type": account.type,
                "on_budget": account.on_budget,
                "closed": account.closed,
                "linked": account.direct_import_linked,
                "last_reconciled_at": account.last_reconciled_at,
                "days_since_reconciled": age,
                "balance": account.balance,
                "balance_display": milliunits_to_display(account.balance),
                "cleared_balance": account.cleared_balance,
                "cleared_balance_display": milliunits_to_display(account.cleared_balance),
                "uncleared_balance": account.uncleared_balance,
                "uncleared_balance_display": milliunits_to_display(account.uncleared_balance),
                "warnings": warnings,
            }
        )

    # Never-reconciled first, then oldest first: both ends of "least trustworthy".
    rows.sort(key=lambda r: (r["days_since_reconciled"] is not None, -(r["days_since_reconciled"] or 0)))
    flagged = [r for r in rows if r["warnings"]]

    return {
        "scope": "triage_reconciliation",
        "plan_id": plan_id,
        "as_of": today.isoformat(),
        "stale_after_days": stale_after_days,
        "account_count": len(rows),
        "flagged_count": len(flagged),
        "total_uncleared": sum(int(r["uncleared_balance"]) for r in rows),
        "total_uncleared_display": milliunits_to_display(sum(int(r["uncleared_balance"]) for r in rows)),
        "accounts": rows,
        "note": (
            "Ordered least-trustworthy first: never reconciled, then longest since. An account's "
            "uncleared balance is the part of its YNAB balance the bank has not confirmed."
        ),
    }


def _slim(t: object) -> dict[str, Any]:
    assert isinstance(t, Transaction)
    return {
        "id": t.id,
        "date": t.date,
        "amount": t.amount,
        "amount_display": milliunits_to_display(t.amount),
        "payee_name": t.payee_name,
        "account_name": t.account_name,
        "category_id": t.category_id,
        "category_name": t.category_name,
        "memo": t.memo,
        "cleared": t.cleared,
        "approved": t.approved,
        "import_payee_name": t.import_payee_name,
    }
