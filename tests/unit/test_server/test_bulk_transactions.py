"""Unit tests: what a bulk transaction write sends back.

The echo of every updated transaction was the largest part of these responses
and the part nobody read — eighty of them overflowed the client's tool-result
cap, so `applied_count` had to be parsed off disk. The counts and the ids are
what the caller acts on; the records are opt-in.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server_for_ynab.models.ynab.transactions import BulkTransactionData, BulkTransactionResponse
from tests.unit.test_enriched.builders import transaction, transactions_response


@pytest.fixture(autouse=True)
def _isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_HISTORY_PATH", str(tmp_path / "history.jsonl"))


def _ctx(*register: Any) -> MagicMock:
    ctx = MagicMock()
    ctx.settings.resolve_plan_id = lambda p: p or "plan-1"
    ctx.transactions.list = AsyncMock(return_value=transactions_response(*register))

    async def _get(_plan: str, txn_id: str) -> Any:
        response = MagicMock()
        response.data.transaction = transaction(id=txn_id)
        return response

    ctx.transactions.get = AsyncMock(side_effect=_get)
    ctx.transactions.bulk_update = AsyncMock(
        return_value=BulkTransactionResponse(
            data=BulkTransactionData(
                transaction_ids=[t.id for t in register],
                transactions=list(register),
            )
        )
    )
    return ctx


async def _bulk_update(ctx: MagicMock, **kwargs: Any) -> dict[str, Any]:
    import mcp_server_for_ynab.server.tools.raw.transactions as module

    with patch.object(module, "get_app_context", return_value=ctx):
        return await module.transactions_bulk_update(**kwargs)


async def test_the_full_records_are_left_out_unless_asked_for() -> None:
    register = [transaction(id=f"t{i}") for i in range(10)]
    ctx = _ctx(*register)

    result = await _bulk_update(
        ctx,
        transactions=[{"id": t.id, "cleared": "reconciled"} for t in register],
    )

    assert "transactions" not in result["data"]
    assert len(result["data"]["transaction_ids"]) == 10
    assert result["verification"]["applied_count"] == 10
    assert "return_transactions=true" in result["transactions_omitted"]


async def test_the_records_come_back_when_they_are_asked_for() -> None:
    register = [transaction(id="t1")]
    ctx = _ctx(*register)

    result = await _bulk_update(
        ctx,
        transactions=[{"id": "t1", "cleared": "reconciled"}],
        return_transactions=True,
    )

    assert result["data"]["transactions"][0]["id"] == "t1"
    assert "transactions_omitted" not in result


async def test_a_large_batch_reads_its_before_state_in_one_request() -> None:
    register = [transaction(id=f"t{i}") for i in range(40)]
    ctx = _ctx(*register)

    await _bulk_update(ctx, transactions=[{"id": t.id, "approved": True} for t in register])

    assert ctx.transactions.list.await_count == 1
    assert ctx.transactions.get.await_count == 0


async def test_missing_before_states_are_reported_as_a_limit_on_reverting() -> None:
    ctx = _ctx(transaction(id="t1"))
    ctx.transactions.list = AsyncMock(side_effect=RuntimeError("429"))
    ctx.transactions.get = AsyncMock(side_effect=RuntimeError("429"))

    result = await _bulk_update(ctx, transactions=[{"id": "t1", "approved": True}])

    assert result["verification"]["before_states_captured"] == 0
    assert "history_revert" in result["verification"]["revert_note"]
