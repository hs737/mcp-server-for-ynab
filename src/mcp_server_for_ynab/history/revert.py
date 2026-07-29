"""Putting a plan back the way it was.

Reverting one entry is the primitive. Reverting *to* a point in time is that
primitive applied to every entry after the target, newest first — order matters,
because two edits to the same transaction only compose correctly in reverse.

A revert is itself a write, so it is journaled too. Reverting a revert is
therefore a normal operation rather than a special case.

What cannot be undone is reported, never skipped silently. A rollback that
quietly leaves an account behind is worse than one that says so.
"""

from __future__ import annotations

from typing import Any

from mcp_server_for_ynab.history import journal
from mcp_server_for_ynab.models.ynab.categories import (
    SaveCategory,
    SaveCategoryGroup,
    SaveCategoryGroupWrapper,
    SaveCategoryWrapper,
)
from mcp_server_for_ynab.models.ynab.payees import SavePayee, SavePayeeWrapper
from mcp_server_for_ynab.models.ynab.scheduled_transactions import (
    Frequency,
    SaveScheduledTransaction,
    SaveScheduledTransactionWrapper,
)
from mcp_server_for_ynab.models.ynab.transactions import (
    SaveTransaction,
    SaveTransactionWrapper,
)
from mcp_server_for_ynab.server.context import AppContext


class RevertError(Exception):
    """A revert could not be performed. The message says why, in plain terms."""


def _transaction_payload(state: dict[str, Any]) -> SaveTransactionWrapper:
    return SaveTransactionWrapper(
        transaction=SaveTransaction(
            account_id=state["account_id"],
            date=state["date"],
            amount=state["amount"],
            payee_id=state.get("payee_id"),
            category_id=state.get("category_id"),
            memo=state.get("memo"),
            cleared=state.get("cleared"),
            approved=state.get("approved"),
            flag_color=state.get("flag_color"),
        )
    )


def _scheduled_payload(state: dict[str, Any]) -> SaveScheduledTransactionWrapper:
    return SaveScheduledTransactionWrapper(
        scheduled_transaction=SaveScheduledTransaction(
            account_id=state["account_id"],
            date=state.get("date_next") or state["date_first"],
            frequency=Frequency(state["frequency"]),
            amount=state["amount"],
            payee_id=state.get("payee_id"),
            category_id=state.get("category_id"),
            memo=state.get("memo"),
            flag_color=state.get("flag_color"),
        )
    )


async def revert_entry(ctx: AppContext, entry: journal.HistoryEntry) -> dict[str, Any]:
    """Undo one journaled write. Returns what was done."""
    if entry.reverted_by:
        raise RevertError(f"Entry {entry.id} was already reverted by {entry.reverted_by}.")

    reason = journal.IRREVERSIBLE.get(entry.operation)
    if reason:
        raise RevertError(f"Cannot revert {entry.operation}: {reason}.")

    if entry.operation not in journal.REVERT_STRATEGIES:
        raise RevertError(f"No revert strategy for operation {entry.operation!r}.")

    plan = entry.plan_id
    outcome: dict[str, Any]

    if entry.operation == "transaction_create":
        await ctx.transactions.delete(plan, str(entry.entity_id))
        outcome = {"action": "deleted the created transaction", "transaction_id": entry.entity_id}

    elif entry.operation == "transaction_update":
        await ctx.transactions.update(plan, str(entry.entity_id), _transaction_payload(entry.before))
        outcome = {"action": "restored previous values", "transaction_id": entry.entity_id}

    elif entry.operation == "transaction_delete":
        created = await ctx.transactions.create(plan, _transaction_payload(entry.before))
        new_id = created.data.transaction.id
        outcome = {
            "action": "recreated the transaction",
            "original_transaction_id": entry.entity_id,
            "new_transaction_id": new_id,
            "note": (
                "A recreated transaction gets a new id, and any bank-import link from the original is not restored."
            ),
        }

    elif entry.operation == "transaction_bulk_update":
        restored, failed = [], []
        for state in entry.before or []:
            try:
                await ctx.transactions.update(plan, state["id"], _transaction_payload(state))
                restored.append(state["id"])
            except Exception as exc:  # one failure must not abandon the rest
                failed.append({"transaction_id": state["id"], "error": str(exc)})
        outcome = {"action": "restored previous values", "restored": restored, "failed": failed}
        if failed:
            outcome["note"] = "Partially reverted. The listed transactions still hold their updated values."

    elif entry.operation == "scheduled_create":
        await ctx.scheduled_transactions.delete(plan, str(entry.entity_id))
        outcome = {"action": "deleted the created scheduled transaction", "scheduled_transaction_id": entry.entity_id}

    elif entry.operation == "scheduled_update":
        await ctx.scheduled_transactions.update(plan, str(entry.entity_id), _scheduled_payload(entry.before))
        outcome = {"action": "restored previous values", "scheduled_transaction_id": entry.entity_id}

    elif entry.operation == "scheduled_delete":
        recreated = await ctx.scheduled_transactions.create(plan, _scheduled_payload(entry.before))
        outcome = {
            "action": "recreated the scheduled transaction",
            "original_scheduled_transaction_id": entry.entity_id,
            "new_scheduled_transaction_id": recreated.data.scheduled_transaction.id,
        }

    elif entry.operation == "category_update":
        category_payload = SaveCategoryWrapper(
            category=SaveCategory(name=entry.before.get("name"), note=entry.before.get("note"))
        )
        await ctx.categories.update(plan, str(entry.entity_id), category_payload)
        outcome = {"action": "restored previous name and note", "category_id": entry.entity_id}

    elif entry.operation == "category_month_budget":
        month_payload = SaveCategoryWrapper(category=SaveCategory(budgeted=entry.before["budgeted"]))
        await ctx.categories.update_for_month(plan, entry.before["month"], str(entry.entity_id), month_payload)
        outcome = {
            "action": "restored previous budgeted amount",
            "category_id": entry.entity_id,
            "month": entry.before["month"],
            "budgeted": entry.before["budgeted"],
        }

    elif entry.operation == "category_group_update":
        group_payload = SaveCategoryGroupWrapper(category_group=SaveCategoryGroup(name=entry.before["name"]))
        await ctx.categories.update_group(plan, str(entry.entity_id), group_payload)
        outcome = {"action": "restored previous name", "category_group_id": entry.entity_id}

    elif entry.operation == "payee_update":
        payee_payload = SavePayeeWrapper(payee=SavePayee(name=entry.before["name"]))
        await ctx.payees.update(plan, str(entry.entity_id), payee_payload)
        outcome = {"action": "restored previous name", "payee_id": entry.entity_id}

    else:  # pragma: no cover - guarded above
        raise RevertError(f"Unhandled operation {entry.operation!r}.")

    revert_record = journal.record(
        operation=f"revert:{entry.operation}",
        tool="history_revert",
        plan_id=plan,
        entity_id=entry.entity_id,
        before=entry.after,
        after=entry.before,
        note=f"Reverted history entry {entry.id}.",
    )
    journal.mark_reverted(entry.id, revert_record.id)

    return {"reverted_entry_id": entry.id, "revert_entry_id": revert_record.id, **outcome}


async def revert_to(ctx: AppContext, entry_id: str, *, plan_id: str | None = None) -> dict[str, Any]:
    """Undo every write made after `entry_id`, newest first.

    The named entry is the state you want back, so it is preserved and
    everything after it is undone.
    """
    entries = journal.load()
    index = next((i for i, e in enumerate(entries) if e.id == entry_id), None)
    if index is None:
        raise RevertError(f"No history entry with id {entry_id!r}.")

    after = entries[index + 1 :]
    if plan_id:
        after = [e for e in after if e.plan_id == plan_id]

    pending = [e for e in after if e.reverted_by is None]

    reverted, blocked, failed = [], [], []
    for entry in reversed(pending):  # newest first, so overlapping edits unwind correctly
        if entry.operation.startswith("revert:"):
            continue
        if entry.operation in journal.IRREVERSIBLE:
            blocked.append(
                {"id": entry.id, "operation": entry.operation, "reason": journal.IRREVERSIBLE[entry.operation]}
            )
            continue
        try:
            result = await revert_entry(ctx, entry)
            reverted.append(result)
        except Exception as exc:
            failed.append({"id": entry.id, "operation": entry.operation, "error": str(exc)})

    complete = not blocked and not failed
    return {
        "target_entry_id": entry_id,
        "reverted_count": len(reverted),
        "reverted": reverted,
        "blocked": blocked,
        "failed": failed,
        "complete": complete,
        "note": (
            "The plan is back to its state at the target entry."
            if complete
            else "Rollback is incomplete. The blocked and failed entries below still stand."
        ),
    }
