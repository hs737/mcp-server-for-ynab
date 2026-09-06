"""Unit tests: finishing a reconciliation as one journaled write.

Two things make this write worth testing beyond its arithmetic. It costs a fixed
number of requests however many transactions it marks, which is the whole reason
it exists rather than a loop over transactions_update. And it makes two kinds of
change — statuses and a new transaction — which have to undo together, because
restoring the statuses alone would leave the account off by exactly the amount
the adjustment settled.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server_for_ynab.history import journal, revert
from mcp_server_for_ynab.models.ynab.transactions import (
    BulkTransactionData,
    BulkTransactionResponse,
    TransactionData,
    TransactionResponse,
)
from tests.unit.test_enriched.builders import account, account_response, transaction, transactions_response


@pytest.fixture(autouse=True)
def _isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_HISTORY_PATH", str(tmp_path / "history.jsonl"))


def _ctx(*register: Any, marked: list[str] | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.settings.resolve_plan_id = lambda p: p or "plan-1"
    ctx.accounts.get = AsyncMock(return_value=account_response(account(name="Ally Spending")))
    ctx.transactions.list_by_account = AsyncMock(return_value=transactions_response(*register))
    ctx.transactions.get = AsyncMock()
    ctx.transactions.bulk_update = AsyncMock(
        return_value=BulkTransactionResponse(
            data=BulkTransactionData(transaction_ids=marked if marked is not None else [t.id for t in register])
        )
    )
    ctx.transactions.create = AsyncMock(
        return_value=TransactionResponse(
            data=TransactionData(
                transaction=transaction(id="adj-1", date="2026-08-31", amount=-7_900, payee_name="Adjustment")
            )
        )
    )
    return ctx


async def _apply(ctx: MagicMock, **kwargs: Any) -> dict[str, Any]:
    import mcp_server_for_ynab.server.tools.reconcile as module

    with patch.object(module, "get_app_context", return_value=ctx):
        return await module.reconcile_apply(**kwargs)


async def test_a_whole_account_is_marked_in_one_bulk_call() -> None:
    register = [transaction(id=f"t{i}", date="2026-08-01", amount=-1_000, cleared="cleared") for i in range(40)]
    ctx = _ctx(*register)

    result = await _apply(
        ctx,
        account_id="acct-1",
        statement_balance=-40_000,
        as_of_date="2026-08-31",
    )

    assert result["marked_reconciled_count"] == 40
    assert ctx.transactions.bulk_update.await_count == 1
    # The before-state comes out of the register that was already read, so no
    # per-transaction request is made for it either.
    assert ctx.transactions.get.await_count == 0


async def test_a_residual_becomes_an_adjustment_for_exactly_the_difference() -> None:
    ctx = _ctx(transaction(id="t1", date="2026-08-01", amount=-30_000, cleared="cleared"))

    result = await _apply(
        ctx,
        account_id="acct-1",
        statement_balance=-37_900,
        as_of_date="2026-08-31",
    )

    assert result["residual"] == -7_900
    assert ctx.transactions.create.await_args.args[1].transaction.amount == -7_900
    assert result["adjustment"]["transaction_id"] == "adj-1"
    assert result["verification"]["matches_statement"] is True


async def test_no_adjustment_when_the_account_already_agrees() -> None:
    ctx = _ctx(transaction(id="t1", date="2026-08-01", amount=-30_000, cleared="cleared"))

    result = await _apply(
        ctx,
        account_id="acct-1",
        statement_balance=-30_000,
        as_of_date="2026-08-31",
    )

    assert result["residual"] == 0
    assert result["adjustment"] is None
    assert ctx.transactions.create.await_count == 0


async def test_an_uncleared_transaction_named_explicitly_joins_the_cleared_balance() -> None:
    """Otherwise the adjustment would be posted for money that just arrived."""
    ctx = _ctx(
        transaction(id="t1", date="2026-08-01", amount=-30_000, cleared="cleared"),
        transaction(id="t2", date="2026-08-02", amount=-5_000, cleared="uncleared"),
    )

    result = await _apply(
        ctx,
        account_id="acct-1",
        statement_balance=-35_000,
        as_of_date="2026-08-31",
        transaction_ids=["t1", "t2"],
    )

    assert result["residual"] == 0
    assert ctx.transactions.create.await_count == 0


async def test_leaving_the_residual_open_says_so_instead_of_claiming_success() -> None:
    ctx = _ctx(transaction(id="t1", date="2026-08-01", amount=-30_000, cleared="cleared"))

    result = await _apply(
        ctx,
        account_id="acct-1",
        statement_balance=-37_900,
        as_of_date="2026-08-31",
        create_adjustment=False,
    )

    assert result["adjustment"] is None
    assert result["verification"]["residual_left_open"] == -7_900
    assert result["verification"]["verified"] is False


async def test_a_failed_marking_still_journals_and_names_the_entry_to_revert() -> None:
    ctx = _ctx(transaction(id="t1", date="2026-08-01", amount=-30_000, cleared="cleared"))
    ctx.transactions.bulk_update = AsyncMock(side_effect=RuntimeError("429"))

    result = await _apply(
        ctx,
        account_id="acct-1",
        statement_balance=-30_000,
        as_of_date="2026-08-31",
    )

    assert result["verification"]["verified"] is False
    assert "429" in result["verification"]["failure"]
    assert journal.get(result["history_entry_id"]) is not None


async def test_the_reconciled_date_caveat_is_on_the_response() -> None:
    ctx = _ctx(transaction(id="t1", cleared="cleared"))

    result = await _apply(ctx, account_id="acct-1", statement_balance=-10_000)

    assert "last_reconciled_at" in result["last_reconciled_note"]


async def test_reverting_restores_the_statuses_and_removes_the_adjustment() -> None:
    ctx = _ctx(transaction(id="t1", date="2026-08-01", amount=-30_000, cleared="cleared"))
    applied = await _apply(
        ctx,
        account_id="acct-1",
        statement_balance=-37_900,
        as_of_date="2026-08-31",
    )

    ctx.transactions.update = AsyncMock()
    ctx.transactions.delete = AsyncMock()
    entry = journal.get(applied["history_entry_id"])
    assert entry is not None

    outcome = await revert.revert_entry(ctx, entry)

    assert outcome["restored"] == ["t1"]
    # The status the transaction had before this write, not the one it was given.
    assert ctx.transactions.update.await_args.args[2].transaction.cleared == "cleared"
    assert ctx.transactions.delete.await_args.args[1] == "adj-1"
