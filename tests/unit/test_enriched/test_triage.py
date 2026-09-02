"""Unit tests: enriched triage tools."""

from __future__ import annotations

from mcp_server_for_ynab.enriched.triage import (
    reconciliation,
    triage_summary,
    triage_unapproved,
    triage_uncategorized,
    unmatched_manual,
)
from tests.unit.test_enriched.builders import (
    account,
    accounts_response,
    days_from_today,
    make_ctx,
    transaction,
    transactions_response,
)


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


async def test_tracking_account_transactions_are_not_work() -> None:
    """A transaction on an off-budget account has no budget to categorize
    against, so it can never leave the uncategorized queue."""
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(
                transaction(id="real", account_id="acct-1", category_id=None),
                transaction(id="brokerage", account_id="tracking", category_id=None),
            )
        },
        accounts=accounts_response(
            account(id="acct-1"),
            account(id="tracking", name="Brokerage", on_budget=False),
        ),
    )

    result = await triage_uncategorized(ctx, "plan-1")

    assert result["count"] == 1
    assert result["raw_count"] == 2
    assert result["excluded"]["tracking_account"] == 1
    assert [t["id"] for t in result["transactions"]] == ["real"]


async def test_transfers_between_on_budget_accounts_are_not_work() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(
                transaction(id="real", category_id=None),
                transaction(id="transfer", category_id=None, transfer_account_id="acct-2"),
            )
        },
        accounts=accounts_response(account(id="acct-1"), account(id="acct-2", name="Savings")),
    )

    result = await triage_uncategorized(ctx, "plan-1")

    assert result["count"] == 1
    assert result["excluded"]["on_budget_transfer"] == 1


async def test_a_transfer_out_to_a_tracking_account_still_needs_a_category() -> None:
    """That money leaves the budget, so it is real work — the exclusion has to
    be narrower than 'anything with a transfer_account_id'."""
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(
                transaction(id="out", category_id=None, transfer_account_id="tracking")
            )
        },
        accounts=accounts_response(
            account(id="acct-1"),
            account(id="tracking", name="Brokerage", on_budget=False),
        ),
    )

    result = await triage_uncategorized(ctx, "plan-1")

    assert result["count"] == 1


async def test_the_excluded_can_be_asked_for_explicitly() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(
                transaction(id="real", category_id=None),
                transaction(id="transfer", category_id=None, transfer_account_id="acct-2"),
            )
        },
        accounts=accounts_response(account(id="acct-1"), account(id="acct-2", name="Savings")),
    )

    result = await triage_uncategorized(ctx, "plan-1", include_transfers=True)

    assert result["count"] == 2


async def test_the_queue_pages_without_losing_the_total() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(
                *(transaction(id=f"t{i}", date=f"2026-07-{i + 1:02d}", category_id=None) for i in range(5))
            )
        }
    )

    result = await triage_uncategorized(ctx, "plan-1", limit=2)

    assert result["count"] == 5
    assert result["returned"] == 2
    assert result["next_offset"] == 2


async def test_the_summary_counts_work_not_noise() -> None:
    ctx = make_ctx(
        transactions_by_type={
            "uncategorized": transactions_response(
                transaction(id="real", category_id=None),
                transaction(id="brokerage", account_id="tracking", category_id=None),
            ),
            "unapproved": transactions_response(transaction(id="a1")),
        },
        accounts=accounts_response(
            account(id="acct-1"),
            account(id="tracking", name="Brokerage", on_budget=False),
        ),
    )

    result = await triage_summary(ctx, "plan-1")

    assert result["uncategorized_count"] == 1
    assert result["uncategorized_raw_count"] == 2
    assert result["total_pending"] == 2


async def test_stale_manual_entries_on_a_linked_account_are_surfaced() -> None:
    ctx = make_ctx(
        accounts=accounts_response(account(id="acct-1", direct_import_linked=True)),
        transactions=transactions_response(
            transaction(id="stale", date="2026-01-05", amount=500_000, cleared="uncleared"),
            transaction(id="recent", date=days_from_today(-2), amount=100_000, cleared="uncleared"),
            transaction(id="imported", date="2026-01-05", cleared="uncleared", import_id="YNAB:1"),
            transaction(id="cleared", date="2026-01-05", cleared="cleared"),
        ),
    )

    result = await unmatched_manual(ctx, "plan-1", since_date="2025-12-01")

    assert [t["id"] for t in result["transactions"]] == ["stale"]
    assert result["net_amount"] == 500_000
    assert result["by_account"][0]["account_name"] == "Checking"


async def test_an_unlinked_account_is_left_alone() -> None:
    """Nothing clears itself there, so an uncleared entry is ordinary bookkeeping."""
    ctx = make_ctx(
        accounts=accounts_response(account(id="acct-1", direct_import_linked=False)),
        transactions=transactions_response(
            transaction(id="stale", date="2026-01-05", cleared="uncleared"),
        ),
    )

    result = await unmatched_manual(ctx, "plan-1", since_date="2025-12-01")

    assert result["count"] == 0


async def test_never_reconciled_accounts_come_first() -> None:
    ctx = make_ctx(
        accounts=accounts_response(
            account(id="a", name="Recent", last_reconciled_at=f"{days_from_today(-3)}T10:00:00Z"),
            account(id="b", name="Stale", last_reconciled_at="2025-01-01T10:00:00Z"),
            account(id="c", name="Never"),
        )
    )

    result = await reconciliation(ctx, "plan-1")

    assert [a["name"] for a in result["accounts"]] == ["Never", "Stale", "Recent"]
    assert result["accounts"][0]["warnings"] == ["Never reconciled."]
    assert result["flagged_count"] == 2


async def test_a_negative_cleared_balance_on_a_cash_account_is_flagged() -> None:
    ctx = make_ctx(
        accounts=accounts_response(
            account(
                id="a",
                name="Checking",
                balance=-5_000,
                cleared_balance=-5_000,
                last_reconciled_at=f"{days_from_today(-1)}T10:00:00Z",
            )
        )
    )

    result = await reconciliation(ctx, "plan-1")

    assert any("overdraft" in warning for warning in result["accounts"][0]["warnings"])
