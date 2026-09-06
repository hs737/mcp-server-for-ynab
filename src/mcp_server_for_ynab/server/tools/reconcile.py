"""MCP tools for reconciling an account against a bank statement.

Kept together rather than split across the read and write modules because they
are one workflow, and the order matters: preview to see the gap, match a bank
export to find what causes it, apply to close it. Two reads and a composed
write, sharing the vocabulary in `enriched/reconcile.py`.

`reconcile_apply` is the third composed write in this server, and follows the
same rules as the other two (see `writes.py`): it is journaled as one entry, so
one decision undoes as one decision; it records the before-state of everything
it touches; and it reports what was applied and what failed, because YNAB has no
transaction boundary. What it adds is a second kind of change in the same entry
— transactions marked reconciled, and an adjustment transaction created — which
the revert has to undo together, since restoring the statuses without deleting
the adjustment would leave the account off by exactly the amount that was in
dispute.
"""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.enriched.reconcile import (
    DEFAULT_DATE_TOLERANCE_DAYS,
    DEFAULT_STALE_DAYS,
    LAST_RECONCILED_NOTE,
    account_and_register,
    as_of_or_today,
    match_statement,
    preview,
    resolve_marks,
)
from mcp_server_for_ynab.history import capture, journal
from mcp_server_for_ynab.models.amounts import milliunits_to_display
from mcp_server_for_ynab.models.ynab.transactions import (
    ClearedStatus,
    SaveTransaction,
    SaveTransactionWrapper,
    UpdateTransaction,
    UpdateTransactionsWrapper,
)
from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler
from mcp_server_for_ynab.server.tools.registration import write_tool

# YNAB names its own reconciliation adjustments this. Using the same payee means
# a person reading the register afterwards sees the entry they expect rather
# than one that looks like it came from somewhere else.
ADJUSTMENT_PAYEE = "Reconciliation Balance Adjustment"

tool_registry.register(
    "reconcile_preview",
    "reconcile",
    "read",
    "enriched",
    "Cleared balance against a statement, and what explains the difference.",
)
tool_registry.register(
    "transactions_match_statement",
    "reconcile",
    "read",
    "enriched",
    "Pair bank-export rows with an account's register on amount and date.",
)
tool_registry.register(
    "reconcile_apply",
    "reconcile",
    "write",
    "enriched",
    "Mark transactions reconciled and post the adjustment, as one write. [WRITE]",
)


@mcp.tool(
    name="reconcile_preview",
    description=(
        "[READ] Does this account agree with its statement, and if not, what is in the way. "
        "This is what YNAB's reconcile screen does, and nothing else here answers it: the cleared "
        "balance as of a date, the statement balance you give it, the difference between them, and "
        "the four queues that explain a difference — transactions cleared but not yet reconciled, "
        "uncleared ones old enough to be suspect, hand-entered ones the bank never matched, and "
        "card authorisations that never posted. "
        "statement_balance: the closing balance from the statement, in milliunits (1000 = $1.00), "
        "negative for a credit card you owe money on. "
        "as_of_date: the statement's closing date (ISO, defaults to today). The cleared balance is "
        "computed as of that date, which is why it can differ from YNAB's own current figure. "
        "Costs two requests, and changes nothing — reconcile_apply is the write."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def reconcile_preview(
    account_id: str,
    statement_balance: int,
    as_of_date: str | None = None,
    stale_after_days: int = DEFAULT_STALE_DAYS,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await preview(
        ctx,
        resolved,
        account_id,
        statement_balance,
        as_of_date=as_of_date,
        stale_after_days=stale_after_days,
    )


@mcp.tool(
    name="transactions_match_statement",
    description=(
        "[READ] Pair the rows of a bank export with an account's register, and name what is left "
        "over on each side. "
        "rows: the statement lines, as objects with date (ISO), amount, and optionally description. "
        "amounts_in: 'milliunits' (default, 1000 = $1.00) or 'dollars' if you are passing the CSV's "
        "own figures. Either way the sign is YNAB's: negative for money out. An export that writes "
        "debits as positive numbers must be negated first, or every row comes back unmatched. "
        "date_tolerance_days: how far a posting date may sit from YNAB's date and still match "
        "(default 3, which covers a weekend). Matching is on exact amount, one-to-one, closest date "
        "first — nothing fuzzy, because a wrong match hides the transaction you were looking for. "
        "Returns matched pairs, unmatched_on_statement (the bank saw it and YNAB has no record), and "
        "unmatched_in_ynab (the reverse — where duplicates, never-posted card authorisations and "
        "bounced payments show up), each labelled with what it looks like. "
        "Costs two requests."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def transactions_match_statement(
    account_id: str,
    rows: list[dict[str, Any]],
    amounts_in: str = "milliunits",
    date_tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS,
    since_date: str | None = None,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    return await match_statement(
        ctx,
        resolved,
        account_id,
        rows,
        amounts_in=amounts_in,
        date_tolerance_days=date_tolerance_days,
        since_date=since_date,
    )


@write_tool(
    name="reconcile_apply",
    description=(
        "[WRITE] Finish a reconciliation: mark the agreed transactions reconciled and, if the "
        "account still does not match the statement, post the adjustment that closes the gap — as "
        "one journaled write. "
        "transaction_ids: which transactions to mark. Omit it to mark every transaction on this "
        "account that is cleared and dated on or before as_of_date, which is what reconciling in "
        "YNAB does. "
        "statement_balance: the closing balance from the statement, in milliunits (1000 = $1.00). "
        "The residual is statement_balance minus the cleared balance after marking; when it is not "
        "zero and create_adjustment is true, an adjustment transaction is created for exactly that "
        "amount, dated as_of_date, payee 'Reconciliation Balance Adjustment'. Pass "
        "adjustment_category_id to categorise it, or the money lands uncategorized. "
        "COST: four requests at most, whatever the number of transactions — the marking is one bulk "
        "call, not one per transaction. "
        "IMPORTANT: this does NOT update the account's last_reconciled_at. YNAB's API has no route "
        "that does, so the app will still show the old date; the transactions themselves are "
        "genuinely reconciled. Tell the user that rather than reporting the account as reconciled."
    ),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
)
@tool_handler
async def reconcile_apply(
    account_id: str,
    statement_balance: int,
    transaction_ids: list[str] | None = None,
    as_of_date: str | None = None,
    create_adjustment: bool = True,
    adjustment_category_id: str | None = None,
    adjustment_memo: str | None = None,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    as_of = as_of_or_today(as_of_date)

    account, register = await account_and_register(ctx, resolved, account_id)
    to_mark = resolve_marks(register, as_of=as_of, transaction_ids=transaction_ids)

    # The register is already in hand, so the before-state costs nothing: no
    # per-transaction read, which is what made this workflow expensive when it
    # was done by hand.
    before = [capture._slice(txn, capture.TRANSACTION_FIELDS) for txn in to_mark]

    marked: list[str] = []
    not_marked: list[str] = []
    failure: str | None = None

    if to_mark:
        try:
            result = await ctx.transactions.bulk_update(
                resolved,
                UpdateTransactionsWrapper(
                    transactions=[UpdateTransaction(id=txn.id, cleared=ClearedStatus.RECONCILED) for txn in to_mark]
                ),
            )
            marked = list(result.data.transaction_ids)
            not_marked = sorted({txn.id for txn in to_mark} - set(marked))
        except Exception as exc:
            failure = f"Marking transactions reconciled failed: {exc}"

    # Recomputed against what the account now looks like: a transaction that was
    # uncleared and named explicitly has just joined the cleared balance, so
    # taking the figure from before the write would post an adjustment for an
    # amount that is no longer owed.
    marked_ids = set(marked)
    cleared_balance = sum(
        txn.amount
        for txn in register
        if txn.date <= as_of and (txn.cleared != ClearedStatus.UNCLEARED or txn.id in marked_ids)
    )
    residual = statement_balance - cleared_balance

    adjustment: dict[str, Any] | None = None
    if residual != 0 and create_adjustment and failure is None:
        try:
            created = await ctx.transactions.create(
                resolved,
                SaveTransactionWrapper(
                    transaction=SaveTransaction(
                        account_id=account_id,
                        date=as_of,
                        amount=residual,
                        payee_name=ADJUSTMENT_PAYEE,
                        category_id=adjustment_category_id,
                        memo=adjustment_memo or f"Reconciled to statement balance on {as_of}.",
                        cleared=ClearedStatus.RECONCILED,
                        approved=True,
                    )
                ),
            )
            txn = created.data.transaction
            adjustment = {
                "transaction_id": txn.id,
                "date": txn.date,
                "amount": txn.amount,
                "amount_display": milliunits_to_display(txn.amount),
                "category_id": txn.category_id,
                "payee_name": txn.payee_name,
            }
        except Exception as exc:
            failure = f"The transactions were marked reconciled but the adjustment failed: {exc}"

    # Journaled even when a step failed — that is precisely when a revert is
    # needed, and the before-states are the only way back.
    entry = journal.record(
        operation="reconcile_apply",
        tool="reconcile_apply",
        plan_id=resolved,
        entity_id=account_id,
        before={"transactions": before},
        after={
            "account_id": account_id,
            "as_of_date": as_of,
            "marked": marked,
            "adjustment_transaction_id": adjustment["transaction_id"] if adjustment else None,
        },
        note=(
            f"{len(marked)} of {len(to_mark)} transactions reconciled on {account.name} as of {as_of}"
            + (f", adjustment {milliunits_to_display(residual)}." if adjustment else ".")
        ),
    )

    final_balance = cleared_balance + (residual if adjustment else 0)
    verification: dict[str, Any] = {
        "requested_count": len(to_mark),
        "marked_count": len(marked),
        "adjustment_created": adjustment is not None,
        "cleared_balance_after": final_balance,
        "cleared_balance_after_display": milliunits_to_display(final_balance),
        "matches_statement": final_balance == statement_balance,
        "verified": failure is None and not not_marked and final_balance == statement_balance,
    }
    if not_marked:
        verification["not_marked"] = not_marked
        verification["warning"] = "YNAB did not return these ids as updated. They are still not reconciled."
    if failure:
        verification["failure"] = failure
        verification["warning"] = f"Revert history entry {entry.id} to undo what was written, then retry."
    if residual != 0 and not create_adjustment:
        verification["residual_left_open"] = residual
        verification["residual_note"] = (
            "create_adjustment was false, so the account still differs from the statement by this "
            "amount. Find it with transactions_match_statement rather than posting it blind."
        )

    return {
        "scope": "reconcile_apply",
        "plan_id": resolved,
        "account_id": account_id,
        "account_name": account.name,
        "as_of_date": as_of,
        "amounts": "milliunits (1000 = $1.00)",
        "statement_balance": statement_balance,
        "statement_balance_display": milliunits_to_display(statement_balance),
        "cleared_balance_before_adjustment": cleared_balance,
        "cleared_balance_before_adjustment_display": milliunits_to_display(cleared_balance),
        "residual": residual,
        "residual_display": milliunits_to_display(residual),
        "marked_reconciled_count": len(marked),
        "adjustment": adjustment,
        "history_entry_id": entry.id,
        "verification": verification,
        "last_reconciled_at": account.last_reconciled_at,
        "last_reconciled_note": LAST_RECONCILED_NOTE,
    }
