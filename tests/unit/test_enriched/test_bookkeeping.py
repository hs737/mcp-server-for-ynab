"""Unit tests: enriched bookkeeping tools."""

from __future__ import annotations

from tests.unit.test_enriched.builders import make_ctx, transaction, transactions_response
from ynab_mcp.enriched.bookkeeping import (
    categorization_suggestions,
    memo_annotation_suggestions,
    transaction_history,
)


async def test_suggestion_confidence_reflects_payee_history() -> None:
    """Four of five past transactions for this payee were Groceries: 0.8 is high."""
    history = transactions_response(
        *[transaction(id=f"h{i}", payee_id="p1", category_name="Groceries") for i in range(4)],
        transaction(id="h5", payee_id="p1", category_name="Household"),
    )
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(transaction(id="u1", payee_id="p1", category_id=None)),
            None: history,
        }
    )
    result = await categorization_suggestions(ctx, "plan-1")

    suggestion = result["suggestions"][0]
    assert suggestion["suggested_category"] == "Groceries"
    assert suggestion["confidence"] == "high"
    assert suggestion["alternatives"] == [{"category_name": "Household", "count": 1}]
    assert result["actionable_count"] == 1


async def test_suggestion_confidence_is_low_when_history_is_split() -> None:
    history = transactions_response(
        transaction(id="h1", payee_id="p1", category_name="Groceries"),
        transaction(id="h2", payee_id="p1", category_name="Household"),
        transaction(id="h3", payee_id="p1", category_name="Gifts"),
    )
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(transaction(id="u1", payee_id="p1", category_id=None)),
            None: history,
        }
    )
    result = await categorization_suggestions(ctx, "plan-1")

    assert result["suggestions"][0]["confidence"] == "low"


async def test_unknown_payee_yields_no_suggestion() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(transaction(id="u1", payee_id="p-new", category_id=None)),
            None: transactions_response(transaction(id="h1", payee_id="p1", category_name="Groceries")),
        }
    )
    result = await categorization_suggestions(ctx, "plan-1")

    suggestion = result["suggestions"][0]
    assert suggestion["suggested_category"] is None
    assert suggestion["confidence"] == "none"
    assert result["actionable_count"] == 0


async def test_memo_candidates_flag_large_transactions_without_memos() -> None:
    ctx = make_ctx(
        transactions=transactions_response(
            transaction(id="t1", amount=-75_000, memo=None),
            transaction(id="t2", amount=-10_000, memo=None),
            transaction(id="t3", amount=-90_000, memo="already noted"),
        )
    )
    result = await memo_annotation_suggestions(ctx, "plan-1")

    assert result["candidate_count"] == 1
    assert result["candidates"][0]["transaction_id"] == "t1"
    assert result["candidates"][0]["reason"] == "large"


async def test_memo_threshold_is_inclusive_at_fifty_dollars() -> None:
    ctx = make_ctx(
        transactions=transactions_response(
            transaction(id="at", amount=-50_000, memo=None),
            transaction(id="below", amount=-49_999, memo=None),
        )
    )
    result = await memo_annotation_suggestions(ctx, "plan-1")

    assert [c["transaction_id"] for c in result["candidates"]] == ["at"]


async def test_memo_candidates_sort_by_absolute_amount() -> None:
    ctx = make_ctx(
        transactions=transactions_response(
            transaction(id="small", amount=-60_000, memo=None),
            transaction(id="big_inflow", amount=500_000, memo=None),
            transaction(id="big_outflow", amount=-300_000, memo=None),
        )
    )
    result = await memo_annotation_suggestions(ctx, "plan-1")

    assert [c["transaction_id"] for c in result["candidates"]] == ["big_inflow", "big_outflow", "small"]


async def test_history_totals_split_inflow_from_outflow() -> None:
    ctx = make_ctx(
        transactions=transactions_response(
            transaction(id="t1", amount=250_000),
            transaction(id="t2", amount=-80_000),
            transaction(id="t3", amount=-20_000),
        )
    )
    result = await transaction_history(ctx, "plan-1")

    assert result["total_inflow"] == 250_000
    assert result["total_outflow"] == -100_000
    assert result["net"] == 150_000


async def test_history_excludes_deleted_transactions() -> None:
    ctx = make_ctx(
        transactions=transactions_response(
            transaction(id="t1", amount=-10_000),
            transaction(id="t2", amount=-999_000, deleted=True),
        )
    )
    result = await transaction_history(ctx, "plan-1")

    assert result["count"] == 1
    assert result["total_outflow"] == -10_000


async def test_history_scopes_to_payee_when_given_one() -> None:
    ctx = make_ctx(transactions=transactions_response(transaction(id="t1")))
    await transaction_history(ctx, "plan-1", payee_id="p1")

    ctx.transactions.list_by_payee.assert_awaited_once()
    ctx.transactions.list.assert_not_awaited()


async def test_history_returns_newest_first() -> None:
    ctx = make_ctx(
        transactions=transactions_response(
            transaction(id="older", date="2026-07-01"),
            transaction(id="newer", date="2026-07-20"),
        )
    )
    result = await transaction_history(ctx, "plan-1")

    assert [t["id"] for t in result["transactions"]] == ["newer", "older"]
