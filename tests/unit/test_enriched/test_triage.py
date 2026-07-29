"""Unit tests: enriched triage tools."""

from __future__ import annotations

from mcp_server_for_ynab.enriched.triage import triage_summary, triage_unapproved, triage_uncategorized
from tests.unit.test_enriched.builders import make_ctx, transaction, transactions_response


async def test_uncategorized_requests_the_right_queue() -> None:
    ctx = make_ctx(
        transactions_by_type={"uncategorized": transactions_response(transaction(id="u1", category_id=None))}
    )
    result = await triage_uncategorized(ctx, "plan-1")

    assert result["count"] == 1
    assert ctx.transactions.list.await_args.kwargs["type"] == "uncategorized"


async def test_unapproved_requests_the_right_queue() -> None:
    ctx = make_ctx(transactions_by_type={"unapproved": transactions_response(transaction(id="a1"))})
    result = await triage_unapproved(ctx, "plan-1")

    assert result["count"] == 1
    assert ctx.transactions.list.await_args.kwargs["type"] == "unapproved"


async def test_triage_excludes_deleted() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(
                transaction(id="u1"),
                transaction(id="u2", deleted=True),
            )
        }
    )
    result = await triage_uncategorized(ctx, "plan-1")

    assert result["count"] == 1


async def test_triage_returns_newest_first() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(
                transaction(id="older", date="2026-06-01"),
                transaction(id="newer", date="2026-07-25"),
            )
        }
    )
    result = await triage_uncategorized(ctx, "plan-1")

    assert [t["id"] for t in result["transactions"]] == ["newer", "older"]


async def test_summary_totals_both_queues() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(transaction(id="u1"), transaction(id="u2")),
            "unapproved": transactions_response(transaction(id="a1")),
        }
    )
    result = await triage_summary(ctx, "plan-1")

    assert result["uncategorized_count"] == 2
    assert result["unapproved_count"] == 1
    assert result["total_pending"] == 3
    assert result["needs_attention"] is True


async def test_summary_reports_a_clean_plan() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(),
            "unapproved": transactions_response(),
        }
    )
    result = await triage_summary(ctx, "plan-1")

    assert result["total_pending"] == 0
    assert result["needs_attention"] is False


async def test_slimmed_transactions_keep_the_fields_an_agent_acts_on() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(
                transaction(id="u1", amount=-12_340, payee_name="Corner Store", memo="note")
            )
        }
    )
    result = await triage_uncategorized(ctx, "plan-1")

    txn = result["transactions"][0]
    assert txn["id"] == "u1"
    assert txn["amount"] == -12_340
    assert txn["amount_display"] == "-$12.34"
    assert txn["payee_name"] == "Corner Store"
    assert txn["memo"] == "note"
