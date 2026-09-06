"""Unit tests: capturing the before-state of a batch.

The cost of a batch write used to be hidden here rather than in the write: the
PATCH is one request and reading what preceded it was one per transaction, which
is how marking 312 transactions reconciled exhausted an hourly limit of 200.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from mcp_server_for_ynab.history import capture
from tests.unit.test_enriched.builders import transaction, transactions_response


def _ctx(*register: Any) -> MagicMock:
    ctx = MagicMock()
    ctx.transactions.list = AsyncMock(return_value=transactions_response(*register))

    async def _get(_plan: str, txn_id: str) -> Any:
        response = MagicMock()
        response.data.transaction = transaction(id=txn_id)
        return response

    ctx.transactions.get = AsyncMock(side_effect=_get)
    return ctx


async def test_a_batch_costs_one_request_not_one_per_transaction() -> None:
    register = [transaction(id=f"t{i}") for i in range(50)]
    ctx = _ctx(*register)

    captured = await capture.before_transactions(ctx, "plan-1", [t.id for t in register])

    assert len(captured) == 50
    assert ctx.transactions.list.await_count == 1
    assert ctx.transactions.get.await_count == 0


async def test_a_batch_of_two_already_costs_less_through_the_list() -> None:
    """One list call is one request; two direct reads are two."""
    ctx = _ctx(transaction(id="t1"), transaction(id="t2"))

    captured = await capture.before_transactions(ctx, "plan-1", ["t1", "t2"])

    assert len(captured) == 2
    assert ctx.transactions.list.await_count == 1
    assert ctx.transactions.get.await_count == 0


async def test_a_single_id_is_read_directly_rather_than_fetching_the_register() -> None:
    """One request either way, and the whole register is a large payload for one row."""
    ctx = _ctx(transaction(id="t1"))

    captured = await capture.before_transactions(ctx, "plan-1", ["t1"])

    assert len(captured) == 1
    assert ctx.transactions.list.await_count == 0
    assert ctx.transactions.get.await_count == 1


async def test_ids_the_register_does_not_hold_are_fetched_individually() -> None:
    """A scheduled transaction's instance carries a compound id the list omits."""
    register = [transaction(id=f"t{i}") for i in range(10)]
    ctx = _ctx(*register)

    captured = await capture.before_transactions(ctx, "plan-1", [*[t.id for t in register], "abc_2026-08-12"])

    assert len(captured) == 11
    assert ctx.transactions.get.await_count == 1


async def test_the_individual_fallback_does_not_spend_the_hour_it_saves() -> None:
    """Past a handful of misses, the honest failure beats the expensive one."""
    ctx = _ctx(transaction(id="t0"))
    requested = ["t0", *[f"missing-{i}" for i in range(30)]]

    captured = await capture.before_transactions(ctx, "plan-1", requested)

    assert [state["id"] for state in captured] == ["t0"]
    assert ctx.transactions.get.await_count == 0


async def test_a_failed_list_does_not_stop_the_write_it_precedes() -> None:
    ctx = _ctx()
    ctx.transactions.list = AsyncMock(side_effect=RuntimeError("429"))

    captured = await capture.before_transactions(ctx, "plan-1", [f"t{i}" for i in range(30)])

    assert captured == []
