"""Unit tests: split transactions and bulk create.

The description of transactions_create promised split support for a long time
while the signature had no subtransactions parameter, so splits were impossible
to create through this server. These tests pin the parameter's behaviour and the
arithmetic YNAB will not check for you clearly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_server_for_ynab.models.errors import ErrorType
from mcp_server_for_ynab.models.ynab.transactions import SaveTransaction, SaveTransactionsWrapper


@pytest.fixture(autouse=True)
def _isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_HISTORY_PATH", str(tmp_path / "history.jsonl"))


@pytest.fixture
def ctx() -> MagicMock:
    context = MagicMock()
    context.settings.resolve_plan_id = lambda p: p or "plan-1"

    created = MagicMock()
    created.data.transaction.id = "txn-new"
    created.model_dump.return_value = {"data": {"transaction": {"id": "txn-new"}}}
    context.transactions.create = AsyncMock(return_value=created)

    bulk = MagicMock()
    bulk.data.transaction_ids = ["a", "b"]
    bulk.data.duplicate_import_ids = []
    bulk.model_dump.return_value = {"data": {"transaction_ids": ["a", "b"]}}
    context.transactions.create_many = AsyncMock(return_value=bulk)

    return context


def _tools(ctx: MagicMock) -> Any:
    """Import the tool functions with writes enabled and a stubbed context."""
    import mcp_server_for_ynab.server.tools.raw.transactions as module

    return patch.object(module, "get_app_context", return_value=ctx)


async def _create(ctx: MagicMock, **kwargs: Any) -> dict[str, Any]:
    import mcp_server_for_ynab.server.tools.raw.transactions as module

    with _tools(ctx):
        return await module.transactions_create(**kwargs)


async def _create_many(ctx: MagicMock, **kwargs: Any) -> dict[str, Any]:
    import mcp_server_for_ynab.server.tools.raw.transactions as module

    with _tools(ctx):
        return await module.transactions_create_many(**kwargs)


async def test_a_split_is_sent_to_ynab(ctx: MagicMock) -> None:
    await _create(
        ctx,
        account_id="a1",
        date="2026-07-01",
        amount=-50_000,
        subtransactions=[
            {"amount": -30_000, "category_id": "groceries"},
            {"amount": -20_000, "category_id": "household"},
        ],
    )

    sent = ctx.transactions.create.await_args.args[1].transaction
    assert len(sent.subtransactions) == 2
    assert [s.amount for s in sent.subtransactions] == [-30_000, -20_000]
    assert [s.category_id for s in sent.subtransactions] == ["groceries", "household"]


async def test_a_split_clears_the_parent_category(ctx: MagicMock) -> None:
    """On a split, each part carries its own category; a parent category is meaningless."""
    await _create(
        ctx,
        account_id="a1",
        date="2026-07-01",
        amount=-50_000,
        category_id="should-be-dropped",
        subtransactions=[
            {"amount": -30_000, "category_id": "groceries"},
            {"amount": -20_000, "category_id": "household"},
        ],
    )

    sent = ctx.transactions.create.await_args.args[1].transaction
    assert sent.category_id is None


async def test_mismatched_split_reports_both_numbers(ctx: MagicMock) -> None:
    """The tool boundary returns errors as a payload rather than raising."""
    result = await _create(
        ctx,
        account_id="a1",
        date="2026-07-01",
        amount=-50_000,
        subtransactions=[{"amount": -30_000}, {"amount": -15_000}],
    )

    error = result["error"]
    assert error["error_type"] == ErrorType.VALIDATION_ERROR
    assert "-45000" in error["message"] and "-50000" in error["message"]
    assert "Difference: -5000" in error["message"]
    ctx.transactions.create.assert_not_awaited()  # nothing was sent


async def test_a_non_split_still_keeps_its_category(ctx: MagicMock) -> None:
    await _create(ctx, account_id="a1", date="2026-07-01", amount=-50_000, category_id="groceries")

    sent = ctx.transactions.create.await_args.args[1].transaction
    assert sent.category_id == "groceries"
    assert sent.subtransactions is None


async def test_inflow_splits_are_allowed(ctx: MagicMock) -> None:
    await _create(
        ctx,
        account_id="a1",
        date="2026-07-01",
        amount=100_000,
        subtransactions=[{"amount": 60_000}, {"amount": 40_000}],
    )

    sent = ctx.transactions.create.await_args.args[1].transaction
    assert sum(s.amount for s in sent.subtransactions) == 100_000


async def test_bulk_create_sends_every_transaction(ctx: MagicMock) -> None:
    await _create_many(
        ctx,
        transactions=[
            {"account_id": "a1", "date": "2026-07-01", "amount": -1_000},
            {"account_id": "a1", "date": "2026-07-02", "amount": -2_000},
        ],
    )

    payload = ctx.transactions.create_many.await_args.args[1]
    assert isinstance(payload, SaveTransactionsWrapper)
    assert [t.amount for t in payload.transactions] == [-1_000, -2_000]


async def test_bulk_create_reports_what_was_created(ctx: MagicMock) -> None:
    result = await _create_many(
        ctx,
        transactions=[
            {"account_id": "a1", "date": "2026-07-01", "amount": -1_000},
            {"account_id": "a1", "date": "2026-07-02", "amount": -2_000},
        ],
    )

    assert result["verification"]["requested_count"] == 2
    assert result["verification"]["created_count"] == 2
    assert result["verification"]["verified"] is True


async def test_bulk_create_flags_skipped_duplicates(ctx: MagicMock) -> None:
    ctx.transactions.create_many.return_value.data.transaction_ids = ["a"]
    ctx.transactions.create_many.return_value.data.duplicate_import_ids = ["dup-1"]

    result = await _create_many(
        ctx,
        transactions=[
            {"account_id": "a1", "date": "2026-07-01", "amount": -1_000, "import_id": "dup-1"},
            {"account_id": "a1", "date": "2026-07-02", "amount": -2_000},
        ],
    )

    verification = result["verification"]
    assert verification["verified"] is False
    assert verification["duplicate_import_ids"] == ["dup-1"]
    assert "already existed" in verification["warning"]


async def test_bulk_create_rejects_an_empty_list(ctx: MagicMock) -> None:
    result = await _create_many(ctx, transactions=[])

    assert "empty" in result["error"]["message"]
    ctx.transactions.create_many.assert_not_awaited()


async def test_bulk_create_names_the_transaction_with_a_bad_split(ctx: MagicMock) -> None:
    """One bad split rejects the whole batch, and says which entry to fix."""
    result = await _create_many(
        ctx,
        transactions=[
            {"account_id": "a1", "date": "2026-07-01", "amount": -1_000},
            {
                "account_id": "a1",
                "date": "2026-07-02",
                "amount": -2_000,
                "subtransactions": [{"amount": -500}],
            },
        ],
    )

    assert "index 1" in result["error"]["message"]
    ctx.transactions.create_many.assert_not_awaited()


def test_the_client_wrapper_posts_to_the_collection() -> None:
    """create_many existed on the client but no tool exposed it until now."""
    from mcp_server_for_ynab.ynab_client.transactions import TransactionsClient

    http = MagicMock()
    http.post = AsyncMock(return_value={"data": {"transaction_ids": [], "duplicate_import_ids": []}})
    client = TransactionsClient(http)

    payload = SaveTransactionsWrapper(transactions=[SaveTransaction(account_id="a1", date="2026-07-01", amount=-1_000)])

    import asyncio

    asyncio.run(client.create_many("plan-1", payload))
    assert http.post.call_args.args[0] == "/budgets/plan-1/transactions"
