"""Capturing before-state, and confirming a write actually landed.

Two jobs that belong together because both bracket a write:

`before_*` reads the current state so a revert has something to restore. It runs
before the write and must never block it — if the read fails, the write still
happens and the entry records that no before-state was captured, which is
honest and still better than refusing to write.

`verify_*` re-reads after the write and compares what was asked for against what
YNAB stored. This is not paranoia: YNAB accepts `budgeted` on the category
update route, returns 200, and ignores it. A tool that reports success on the
strength of a 200 is reporting the request, not the result.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp_server_for_ynab.server.context import AppContext

logger = logging.getLogger(__name__)

TRANSACTION_FIELDS = (
    "account_id",
    "date",
    "amount",
    "payee_id",
    "category_id",
    "memo",
    "cleared",
    "approved",
    "flag_color",
)

SCHEDULED_FIELDS = (
    "account_id",
    "date_first",
    "date_next",
    "frequency",
    "amount",
    "payee_id",
    "category_id",
    "memo",
    "flag_color",
)


def _slice(model: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    dumped = model.model_dump(mode="json")
    state = {f: dumped.get(f) for f in fields}
    state["id"] = dumped.get("id")
    return state


async def before_transaction(ctx: AppContext, plan_id: str, transaction_id: str) -> dict[str, Any] | None:
    try:
        resp = await ctx.transactions.get(plan_id, transaction_id)
    except Exception as exc:
        logger.warning("Could not capture before-state for transaction %s: %s", transaction_id, exc)
        return None
    return _slice(resp.data.transaction, TRANSACTION_FIELDS)


# Reading N transactions one at a time is N requests against an hourly limit of
# 200, which is how a 312-item reconciliation locked a token out for an hour.
# One unfiltered list call costs a single request and answers for all of them,
# so it wins from two ids upward and the batch cost stops depending on the batch
# size — which is what the tool description promises.
#
# A single id is the one case that goes direct: one request either way, and
# fetching the whole register to read one row is a large payload for nothing.
_LIST_CAPTURE_THRESHOLD = 1

# When the list does not account for some of the batch, those are fetched one by
# one — but only so many. Falling back on three hundred ids would spend exactly
# the hour this function exists to save, so past this point the entry records
# that those before-states are missing and the caller is told, which is the
# honest failure rather than an expensive one.
_MAX_INDIVIDUAL_FALLBACK = 10


async def before_transactions(ctx: AppContext, plan_id: str, transaction_ids: list[str]) -> list[dict[str, Any]]:
    """Before-state for a batch, at one request rather than one per item.

    The batch write itself is a single PATCH; capturing what preceded it used to
    be the expensive half, and nothing in the tool description said so. One list
    call covers the whole batch, so a batch of two costs what a batch of three
    hundred costs.

    Ids the list does not contain are fetched individually — a scheduled
    transaction's materialised instance carries a compound id
    (`<uuid>_2026-08-12`) that the register route does not return, and silently
    recording no before-state for it would mean the revert quietly skipped it.
    Those extra reads are the one way this exceeds a single request, and they
    are capped; callers are told the real cost rather than a convenient one.
    """
    if not transaction_ids:
        return []

    if len(transaction_ids) <= _LIST_CAPTURE_THRESHOLD:
        captured = [await before_transaction(ctx, plan_id, txn_id) for txn_id in transaction_ids]
        return [state for state in captured if state]

    wanted = set(transaction_ids)
    found: dict[str, dict[str, Any]] = {}
    try:
        listing = await ctx.transactions.list(plan_id)
    except Exception as exc:
        logger.warning("Could not list transactions to capture before-state: %s", exc)
    else:
        found = {txn.id: _slice(txn, TRANSACTION_FIELDS) for txn in listing.data.transactions if txn.id in wanted}

    missing = [txn_id for txn_id in transaction_ids if txn_id not in found]
    if len(missing) > _MAX_INDIVIDUAL_FALLBACK:
        logger.warning(
            "Transaction list accounted for %d of %d ids; %d before-states not captured "
            "(fetching them individually would exhaust the request budget).",
            len(found),
            len(transaction_ids),
            len(missing),
        )
        missing = []

    for txn_id in missing:
        state = await before_transaction(ctx, plan_id, txn_id)
        if state:
            found[txn_id] = state

    return [found[txn_id] for txn_id in transaction_ids if txn_id in found]


async def before_scheduled(ctx: AppContext, plan_id: str, scheduled_id: str) -> dict[str, Any] | None:
    try:
        resp = await ctx.scheduled_transactions.get(plan_id, scheduled_id)
    except Exception as exc:
        logger.warning("Could not capture before-state for scheduled %s: %s", scheduled_id, exc)
        return None
    return _slice(resp.data.scheduled_transaction, SCHEDULED_FIELDS)


async def before_category(ctx: AppContext, plan_id: str, category_id: str) -> dict[str, Any] | None:
    try:
        resp = await ctx.categories.get(plan_id, category_id)
    except Exception as exc:
        logger.warning("Could not capture before-state for category %s: %s", category_id, exc)
        return None
    category = resp.data.category
    return {"id": category.id, "name": category.name, "note": category.note}


async def before_category_month(ctx: AppContext, plan_id: str, month: str, category_id: str) -> dict[str, Any] | None:
    try:
        resp = await ctx.categories.get_for_month(plan_id, month, category_id)
    except Exception as exc:
        logger.warning("Could not capture before-state for category %s in %s: %s", category_id, month, exc)
        return None
    return {"id": resp.data.category.id, "month": month, "budgeted": resp.data.category.budgeted}


async def before_payee(ctx: AppContext, plan_id: str, payee_id: str) -> dict[str, Any] | None:
    try:
        resp = await ctx.payees.get(plan_id, payee_id)
    except Exception as exc:
        logger.warning("Could not capture before-state for payee %s: %s", payee_id, exc)
        return None
    return {"id": resp.data.payee.id, "name": resp.data.payee.name}


async def before_category_group(ctx: AppContext, plan_id: str, group_id: str) -> dict[str, Any] | None:
    """Groups have no single-group read route, so find it in the list."""
    try:
        resp = await ctx.categories.list(plan_id)
    except Exception as exc:
        logger.warning("Could not capture before-state for category group %s: %s", group_id, exc)
        return None
    for group in resp.data.category_groups:
        if group.id == group_id:
            return {"id": group.id, "name": group.name}
    return None


def _verdict(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    mismatches = {
        field: {"requested": value, "stored": actual.get(field)}
        for field, value in expected.items()
        if value is not None and actual.get(field) != value
    }
    result: dict[str, Any] = {"verified": not mismatches, "checked_fields": sorted(expected)}
    if mismatches:
        result["mismatches"] = mismatches
        result["warning"] = (
            "YNAB accepted the request but stored different values for the fields listed. "
            "The write did not fully take effect."
        )
    return result


async def verify_transaction(
    ctx: AppContext, plan_id: str, transaction_id: str, expected: dict[str, Any]
) -> dict[str, Any]:
    """Re-read a transaction and confirm the requested fields were stored."""
    try:
        resp = await ctx.transactions.get(plan_id, transaction_id)
    except Exception as exc:
        return {"verified": None, "verification_error": f"Could not re-read the transaction: {exc}"}
    return _verdict(expected, _slice(resp.data.transaction, TRANSACTION_FIELDS))


async def verify_category_month(
    ctx: AppContext, plan_id: str, month: str, category_id: str, expected_budgeted: int
) -> dict[str, Any]:
    try:
        resp = await ctx.categories.get_for_month(plan_id, month, category_id)
    except Exception as exc:
        return {"verified": None, "verification_error": f"Could not re-read the category: {exc}"}
    return _verdict({"budgeted": expected_budgeted}, {"budgeted": resp.data.category.budgeted})


async def verify_category(ctx: AppContext, plan_id: str, category_id: str, expected: dict[str, Any]) -> dict[str, Any]:
    try:
        resp = await ctx.categories.get(plan_id, category_id)
    except Exception as exc:
        return {"verified": None, "verification_error": f"Could not re-read the category: {exc}"}
    category = resp.data.category
    return _verdict(expected, {"name": category.name, "note": category.note})
