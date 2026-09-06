"""Reconciling an account: comparing YNAB against the bank, and closing the gap.

Reconciliation is the workflow YNAB's own interface is built around and the one
this server had no route for. Every primitive was here — list an account's
register, mark transactions reconciled, create an adjustment — and the work of
joining them was done by hand, in Python, against CSVs, three times in one
session.

Three functions, in the order the work happens:

`preview` answers "does the bank agree with YNAB, and if not, what is in the
way": the cleared balance as of a date against the statement balance, the
difference between them, and the four kinds of transaction that explain a
difference — cleared but not yet reconciled, uncleared and old, entered by hand
and never matched, and pending card authorisations that will never post.

`match_statement` takes the rows of a bank export and pairs them with the
register, on exact amount within a few days. It is the step that turns "we are
$79 apart" into four specific transactions. The matcher this replaces was forty
lines and found four ghost authorisations, five uncleared transfers and two
bounced-payment pairs with no false positives at three days' tolerance.

`apply` is the write: mark the agreed transactions reconciled and, if a residual
remains, create the adjustment that closes it — as one journaled decision, at
two requests regardless of how many transactions are involved.

One thing none of them can do, said here once and in every response that could
mislead: YNAB's API has no route to set an account's `last_reconciled_at`.
Marking three hundred transactions reconciled leaves that date untouched, so the
app will still say "last reconciled a year ago" afterwards. Reporting success
without saying so reads, to the person who then opens YNAB, as a lie.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from mcp_server_for_ynab.models.amounts import dollars_to_milliunits, milliunits_to_display
from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpError, YnabMcpException
from mcp_server_for_ynab.models.ynab.accounts import Account
from mcp_server_for_ynab.models.ynab.transactions import ClearedStatus, Transaction

# YNAB's direct import creates a transaction for a card *authorisation* — a hold
# the merchant places before the real charge posts — and gives it an import_id
# starting with this. When the charge posts at a different amount it arrives as
# its own transaction and the hold is left behind, uncleared, inflating the
# card balance until someone deletes it.
PENDING_IMPORT_PREFIX = "YNAB:P:"

# How far a bank's posting date may sit from the date in YNAB and still be the
# same transaction. Three days covers a weekend.
DEFAULT_DATE_TOLERANCE_DAYS = 3

# How long an uncleared transaction has to sit before it stops looking like
# something in flight.
DEFAULT_STALE_DAYS = 7

# Lists in a reconciliation response are working queues, not archives. Past this
# many the count is what matters and the rows are noise.
MAX_ROWS = 100

LAST_RECONCILED_NOTE = (
    "YNAB's API has no route to set an account's last_reconciled_at, so it is unchanged by this "
    "call and the YNAB app will still show the date of the last reconciliation done there. The "
    "transactions really are marked reconciled; only the account's date is stale. Say so rather "
    "than reporting that the account has been reconciled."
)


def _fail(message: str) -> YnabMcpException:
    return YnabMcpException(YnabMcpError(error_type=ErrorType.VALIDATION_ERROR, message=message))


def as_of_or_today(value: str | None) -> str:
    """A statement's closing date, checked here rather than deep in the arithmetic.

    An unparseable date otherwise surfaces as an internal error from a date
    comparison several functions down, which tells the caller nothing about
    which argument was wrong.
    """
    if not value:
        return date.today().isoformat()
    try:
        return date.fromisoformat(value.strip()[:10]).isoformat()
    except ValueError as exc:
        raise _fail(
            f"as_of_date {value!r} is not an ISO date. Use the statement's closing date, e.g. '2026-08-31'."
        ) from exc


def _row(txn: Transaction) -> dict[str, Any]:
    return {
        "id": txn.id,
        "date": txn.date,
        "amount": txn.amount,
        "amount_display": milliunits_to_display(txn.amount),
        "payee_name": txn.payee_name or txn.import_payee_name,
        "memo": txn.memo,
        "cleared": txn.cleared,
        "approved": txn.approved,
        "import_id": txn.import_id,
        "transfer_account_id": txn.transfer_account_id,
    }


def _capped(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return rows[:MAX_ROWS]


def _sum(txns: list[Transaction]) -> int:
    return sum(t.amount for t in txns)


def _money(label: str, amount: int) -> dict[str, Any]:
    return {label: amount, f"{label}_display": milliunits_to_display(amount)}


async def account_and_register(
    ctx: Any,
    plan_id: str,
    account_id: str,
    *,
    since_date: str | None = None,
) -> tuple[Account, list[Transaction]]:
    """The account and its register, in two requests, whatever the size of either."""
    account_resp, txn_resp = await asyncio.gather(
        ctx.accounts.get(plan_id, account_id),
        ctx.transactions.list_by_account(plan_id, account_id, since_date=since_date),
    )
    register = [t for t in txn_resp.data.transactions if not t.deleted]
    register.sort(key=lambda t: t.date)
    return account_resp.data.account, register


def _split_register(
    register: list[Transaction],
    as_of: str,
    stale_before: str,
) -> dict[str, list[Transaction]]:
    """The four queues that explain a difference against a statement."""
    up_to = [t for t in register if t.date <= as_of]
    uncleared = [t for t in up_to if t.cleared == ClearedStatus.UNCLEARED]
    return {
        "up_to": up_to,
        "settled": [t for t in up_to if t.cleared != ClearedStatus.UNCLEARED],
        "to_mark": [t for t in up_to if t.cleared == ClearedStatus.CLEARED],
        "uncleared": uncleared,
        "stale_uncleared": [t for t in uncleared if t.date <= stale_before],
        "manual_uncleared": [t for t in uncleared if t.import_id is None],
        "pending_imports": [t for t in uncleared if t.import_id and t.import_id.startswith(PENDING_IMPORT_PREFIX)],
        "after_as_of": [t for t in register if t.date > as_of],
    }


async def preview(
    ctx: Any,
    plan_id: str,
    account_id: str,
    statement_balance: int,
    *,
    as_of_date: str | None = None,
    stale_after_days: int = DEFAULT_STALE_DAYS,
) -> dict[str, Any]:
    """Does the bank agree with YNAB as of a date, and if not, what is in the way."""
    as_of = as_of_or_today(as_of_date)
    stale_before = (date.fromisoformat(as_of) - timedelta(days=max(0, stale_after_days))).isoformat()

    account, register = await account_and_register(ctx, plan_id, account_id)
    queues = _split_register(register, as_of, stale_before)

    # Computed from the register rather than read off the account, because the
    # account's cleared_balance is always "now" and a statement is always a
    # date. They agree only when nothing has cleared since.
    cleared_balance = _sum(queues["settled"])
    difference = statement_balance - cleared_balance

    payload: dict[str, Any] = {
        "scope": "reconcile_preview",
        "plan_id": plan_id,
        "account_id": account_id,
        "account_name": account.name,
        "as_of_date": as_of,
        "amounts": "milliunits (1000 = $1.00)",
        **_money("statement_balance", statement_balance),
        **_money("cleared_balance", cleared_balance),
        **_money("difference", difference),
        "balanced": difference == 0,
        **_money("account_cleared_balance_now", account.cleared_balance),
        **_money("account_uncleared_balance_now", account.uncleared_balance),
        "last_reconciled_at": account.last_reconciled_at,
        "to_mark_count": len(queues["to_mark"]),
        **_money("to_mark_total", _sum(queues["to_mark"])),
        "uncleared_count": len(queues["uncleared"]),
        **_money("uncleared_total", _sum(queues["uncleared"])),
        "stale_uncleared_count": len(queues["stale_uncleared"]),
        "manual_uncleared_count": len(queues["manual_uncleared"]),
        "pending_import_count": len(queues["pending_imports"]),
        **_money("pending_import_total", _sum(queues["pending_imports"])),
        "stale_after_days": stale_after_days,
        "to_mark": _capped([_row(t) for t in queues["to_mark"]]),
        "stale_uncleared": _capped([_row(t) for t in queues["stale_uncleared"]]),
        "manual_uncleared": _capped([_row(t) for t in queues["manual_uncleared"]]),
        "pending_imports": _capped([_row(t) for t in queues["pending_imports"]]),
        "last_reconciled_note": LAST_RECONCILED_NOTE,
    }

    if queues["after_as_of"]:
        payload["dated_after_as_of_count"] = len(queues["after_as_of"])

    payload["next_step"] = (
        (
            f"The statement agrees with YNAB. reconcile_apply marks the {len(queues['to_mark'])} "
            "cleared transactions reconciled; no adjustment is needed."
        )
        if difference == 0
        else (
            f"The statement is {milliunits_to_display(difference)} away from YNAB's cleared balance. "
            "Look in stale_uncleared, manual_uncleared and pending_imports for the cause, or run "
            "transactions_match_statement against the bank export to find it exactly. "
            "reconcile_apply will post the difference as an adjustment if you decide it is real."
        )
    )
    payload["note"] = (
        "cleared_balance is computed from the register as of as_of_date — cleared and reconciled "
        "transactions on or before that date — which is what a statement can be compared against. "
        "account_cleared_balance_now is YNAB's own figure for today and will differ if anything "
        "cleared since."
    )
    return payload


def _statement_rows(rows: list[dict[str, Any]], amounts_in: str) -> list[dict[str, Any]]:
    """Validate and normalise the rows of a bank export."""
    if amounts_in not in ("milliunits", "dollars"):
        raise _fail(f"amounts_in must be 'milliunits' or 'dollars'; got {amounts_in!r}.")
    if not rows:
        raise _fail("rows is empty. Pass the statement lines as {date, amount, description} objects.")

    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        raw_date = row.get("date")
        raw_amount = row.get("amount")
        if not isinstance(raw_date, str):
            raise _fail(f"rows[{index}] has no date. Use an ISO date string, e.g. '2026-08-14'.")
        try:
            stamp = date.fromisoformat(raw_date.strip()[:10]).isoformat()
        except ValueError as exc:
            raise _fail(f"rows[{index}] date {raw_date!r} is not an ISO date. ({exc})") from exc
        if isinstance(raw_amount, bool) or not isinstance(raw_amount, int | float):
            raise _fail(f"rows[{index}] amount must be a number; got {raw_amount!r}.")

        amount = dollars_to_milliunits(float(raw_amount)) if amounts_in == "dollars" else int(raw_amount)
        parsed.append(
            {
                "index": index,
                "date": stamp,
                "amount": amount,
                "amount_display": milliunits_to_display(amount),
                "description": row.get("description"),
            }
        )

    parsed.sort(key=lambda r: (r["date"], r["index"]))
    return parsed


async def match_statement(
    ctx: Any,
    plan_id: str,
    account_id: str,
    rows: list[dict[str, Any]],
    *,
    amounts_in: str = "milliunits",
    date_tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS,
    since_date: str | None = None,
) -> dict[str, Any]:
    """Pair the rows of a bank export with an account's register.

    Matching is on exact amount within a date tolerance, one-to-one, closest
    date first. Amount is the anchor rather than payee text because the text is
    the part the bank rewrites between the authorisation and the posting, while
    the figure either agrees or does not. Nothing fuzzy is attempted: a
    near-match reported as a match is worse than an unmatched row, because the
    unmatched row is what gets looked at.
    """
    if date_tolerance_days < 0:
        raise _fail(f"date_tolerance_days cannot be negative; got {date_tolerance_days}.")

    statement = _statement_rows(rows, amounts_in)
    window_start = (date.fromisoformat(statement[0]["date"]) - timedelta(days=date_tolerance_days)).isoformat()
    window_end = (date.fromisoformat(statement[-1]["date"]) + timedelta(days=date_tolerance_days)).isoformat()

    _, register = await account_and_register(ctx, plan_id, account_id, since_date=since_date or window_start)
    candidates = [t for t in register if window_start <= t.date <= window_end]

    by_amount: dict[int, list[Transaction]] = {}
    for txn in candidates:
        by_amount.setdefault(txn.amount, []).append(txn)

    taken: set[str] = set()
    matched: list[dict[str, Any]] = []
    unmatched_statement: list[dict[str, Any]] = []

    for row in statement:
        row_date = date.fromisoformat(row["date"])
        pool = [t for t in by_amount.get(row["amount"], []) if t.id not in taken]
        best: Transaction | None = None
        best_gap = date_tolerance_days + 1
        for txn in pool:
            gap = abs((date.fromisoformat(txn.date) - row_date).days)
            if gap <= date_tolerance_days and gap < best_gap:
                best, best_gap = txn, gap

        if best is None:
            unmatched_statement.append(row)
            continue

        taken.add(best.id)
        matched.append(
            {
                "statement": {k: v for k, v in row.items() if k != "index"},
                "transaction": _row(best),
                "date_gap_days": best_gap,
            }
        )

    unmatched_ynab = [t for t in candidates if t.id not in taken]

    statement_total = sum(int(r["amount"]) for r in statement)
    return {
        "scope": "transactions_match_statement",
        "plan_id": plan_id,
        "account_id": account_id,
        "amounts": "milliunits (1000 = $1.00), negative for money out",
        "amounts_in": amounts_in,
        "window": {"from": window_start, "to": window_end},
        "date_tolerance_days": date_tolerance_days,
        "statement_row_count": len(statement),
        **_money("statement_total", statement_total),
        "register_row_count": len(candidates),
        "matched_count": len(matched),
        "unmatched_on_statement_count": len(unmatched_statement),
        **_money("unmatched_on_statement_total", sum(int(r["amount"]) for r in unmatched_statement)),
        "unmatched_in_ynab_count": len(unmatched_ynab),
        **_money("unmatched_in_ynab_total", _sum(unmatched_ynab)),
        "matched": _capped(matched),
        "unmatched_on_statement": _capped([{k: v for k, v in r.items() if k != "index"} for r in unmatched_statement]),
        "unmatched_in_ynab": _capped(
            [
                {
                    **_row(t),
                    "looks_like": (
                        "pending card authorisation that never posted"
                        if t.import_id and t.import_id.startswith(PENDING_IMPORT_PREFIX)
                        else "entered by hand and never matched"
                        if t.import_id is None
                        else "imported but absent from this statement"
                    ),
                }
                for t in unmatched_ynab
            ]
        ),
        "note": (
            "unmatched_on_statement is money the bank saw and YNAB has no record of — transactions to "
            "add. unmatched_in_ynab is the reverse, and is where duplicates, never-posted card "
            "authorisations and bounced payments show up. Amounts follow YNAB's convention: negative "
            "is money out. If the export writes debits as positive numbers, negate them first, or "
            "everything will come back unmatched."
        ),
    }


def resolve_marks(
    register: list[Transaction],
    *,
    as_of: str,
    transaction_ids: list[str] | None,
) -> list[Transaction]:
    """Which transactions a reconciliation is about to mark reconciled.

    Explicit ids win, and are checked against the register: an id that is not on
    this account, or already reconciled, is a caller error worth naming rather
    than a no-op to discover afterwards in a count.
    """
    if transaction_ids is None:
        return [t for t in register if t.date <= as_of and t.cleared == ClearedStatus.CLEARED]

    if not transaction_ids:
        return []

    by_id = {t.id: t for t in register}
    unknown = [txn_id for txn_id in transaction_ids if txn_id not in by_id]
    if unknown:
        raise _fail(
            f"{len(unknown)} of {len(transaction_ids)} transaction_ids are not in this account's register: "
            f"{', '.join(unknown[:5])}{'...' if len(unknown) > 5 else ''}. "
            "Pass ids from reconcile_preview or transactions_match_statement for this account."
        )

    return [by_id[txn_id] for txn_id in transaction_ids if by_id[txn_id].cleared != ClearedStatus.RECONCILED]
