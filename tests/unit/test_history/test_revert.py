"""Unit tests: reverting journaled writes."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_server_for_ynab.history import journal
from mcp_server_for_ynab.history.revert import RevertError, revert_entry, revert_to

BEFORE_TXN = {
    "id": "t1",
    "account_id": "a1",
    "date": "2026-07-01",
    "amount": -25_000,
    "payee_id": "p1",
    "category_id": "c1",
    "memo": "original memo",
    "cleared": "cleared",
    "approved": True,
    "flag_color": None,
}


@pytest.fixture(autouse=True)
def _isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_HISTORY_PATH", str(tmp_path / "history.jsonl"))


def _ctx() -> MagicMock:
    ctx = MagicMock()
    created = MagicMock()
    created.data.transaction.id = "t-new"
    ctx.transactions.create = AsyncMock(return_value=created)
    ctx.transactions.update = AsyncMock()
    ctx.transactions.delete = AsyncMock()
    ctx.categories.update = AsyncMock()
    ctx.categories.update_for_month = AsyncMock()
    ctx.categories.update_group = AsyncMock()
    ctx.payees.update = AsyncMock()
    return ctx


async def test_reverting_a_create_deletes_it() -> None:
    entry = journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="t1")
    ctx = _ctx()

    result = await revert_entry(ctx, entry)

    ctx.transactions.delete.assert_awaited_once_with("p1", "t1")
    assert result["reverted_entry_id"] == entry.id


async def test_reverting_an_update_restores_the_previous_values() -> None:
    entry = journal.record(operation="transaction_update", tool="t", plan_id="p1", entity_id="t1", before=BEFORE_TXN)
    ctx = _ctx()

    await revert_entry(ctx, entry)

    payload = ctx.transactions.update.await_args.args[2]
    assert payload.transaction.memo == "original memo"
    assert payload.transaction.amount == -25_000


async def test_reverting_a_delete_recreates_and_says_the_id_changed() -> None:
    entry = journal.record(operation="transaction_delete", tool="t", plan_id="p1", entity_id="t1", before=BEFORE_TXN)
    ctx = _ctx()

    result = await revert_entry(ctx, entry)

    assert result["new_transaction_id"] == "t-new"
    assert "new id" in result["note"]


async def test_reverting_a_budget_change_restores_the_month_amount() -> None:
    entry = journal.record(
        operation="category_month_budget",
        tool="t",
        plan_id="p1",
        entity_id="c1",
        before={"id": "c1", "month": "2026-07-01", "budgeted": 40_000},
    )
    ctx = _ctx()

    result = await revert_entry(ctx, entry)

    month, category_id = ctx.categories.update_for_month.await_args.args[1:3]
    assert (month, category_id) == ("2026-07-01", "c1")
    assert result["budgeted"] == 40_000


async def test_an_irreversible_operation_explains_itself() -> None:
    entry = journal.record(operation="account_create", tool="t", plan_id="p1", entity_id="a1")

    with pytest.raises(RevertError) as exc:
        await revert_entry(_ctx(), entry)

    assert "no route to delete an account" in str(exc.value)


async def test_an_entry_cannot_be_reverted_twice() -> None:
    entry = journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="t1")
    ctx = _ctx()
    await revert_entry(ctx, entry)

    reloaded = journal.get(entry.id)
    with pytest.raises(RevertError) as exc:
        await revert_entry(ctx, reloaded)

    assert "already reverted" in str(exc.value)


async def test_a_revert_is_itself_journaled() -> None:
    entry = journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="t1")
    await revert_entry(_ctx(), entry)

    operations = [e.operation for e in journal.load()]
    assert "revert:transaction_create" in operations


async def test_bulk_revert_restores_each_and_reports_failures() -> None:
    second = {**BEFORE_TXN, "id": "t2"}
    entry = journal.record(operation="transaction_bulk_update", tool="t", plan_id="p1", before=[BEFORE_TXN, second])
    ctx = _ctx()
    ctx.transactions.update = AsyncMock(side_effect=[None, RuntimeError("nope")])

    result = await revert_entry(ctx, entry)

    assert result["restored"] == ["t1"]
    assert result["failed"][0]["transaction_id"] == "t2"
    assert "Partially reverted" in result["note"]


async def test_revert_to_undoes_everything_after_the_target_newest_first() -> None:
    target = journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="t0")
    journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="t1")
    journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="t2")
    ctx = _ctx()

    result = await revert_to(ctx, target.id)

    deleted = [call.args[1] for call in ctx.transactions.delete.await_args_list]
    assert deleted == ["t2", "t1"]  # newest first
    assert result["reverted_count"] == 2
    assert result["complete"] is True


async def test_revert_to_keeps_the_target_entry_itself() -> None:
    target = journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="keep")
    journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="undo")
    ctx = _ctx()

    await revert_to(ctx, target.id)

    deleted = [call.args[1] for call in ctx.transactions.delete.await_args_list]
    assert deleted == ["undo"]


async def test_revert_to_reports_what_it_could_not_undo() -> None:
    target = journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="t0")
    journal.record(operation="account_create", tool="t", plan_id="p1", entity_id="a1")
    ctx = _ctx()

    result = await revert_to(ctx, target.id)

    assert result["complete"] is False
    assert result["blocked"][0]["operation"] == "account_create"
    assert "incomplete" in result["note"]


async def test_revert_to_can_scope_to_one_plan() -> None:
    target = journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="t0")
    journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="mine")
    journal.record(operation="transaction_create", tool="t", plan_id="p2", entity_id="other")
    ctx = _ctx()

    await revert_to(ctx, target.id, plan_id="p1")

    deleted = [call.args[1] for call in ctx.transactions.delete.await_args_list]
    assert deleted == ["mine"]


async def test_revert_to_an_unknown_entry_fails_clearly() -> None:
    with pytest.raises(RevertError) as exc:
        await revert_to(_ctx(), "nosuchid")

    assert "No history entry" in str(exc.value)


async def test_a_batch_assignment_restores_every_line() -> None:
    """months_assign_many is one entry so a month's plan can be undone as one
    decision; the revert still has to touch each category individually."""
    ctx = _ctx()
    entry = journal.record(
        operation="category_month_budget_batch",
        tool="months_assign_many",
        plan_id="plan-1",
        before=[
            {"id": "c1", "month": "2026-07-01", "budgeted": 10_000},
            {"id": "c2", "month": "2026-07-01", "budgeted": 25_000},
        ],
    )

    result = await revert_entry(ctx, entry)

    assert result["restored"] == ["c1", "c2"]
    restored = [call.args[3].category.budgeted for call in ctx.categories.update_for_month.await_args_list]
    assert restored == [10_000, 25_000]
    assert journal.get(entry.id).reverted_by == result["revert_entry_id"]


async def test_a_batch_revert_reports_the_lines_it_could_not_put_back() -> None:
    ctx = _ctx()
    ctx.categories.update_for_month = AsyncMock(side_effect=[MagicMock(), RuntimeError("YNAB said no")])
    entry = journal.record(
        operation="category_month_budget_batch",
        tool="months_assign_many",
        plan_id="plan-1",
        before=[
            {"id": "c1", "month": "2026-07-01", "budgeted": 10_000},
            {"id": "c2", "month": "2026-07-01", "budgeted": 25_000},
        ],
    )

    result = await revert_entry(ctx, entry)

    assert result["restored"] == ["c1"]
    assert result["failed"][0]["category_id"] == "c2"
    assert "Partially reverted" in result["note"]
