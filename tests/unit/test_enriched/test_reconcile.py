"""Unit tests: reconciling an account against a statement.

Reconciliation is arithmetic with a lot of ways to be quietly wrong — a balance
taken as of today rather than as of the statement, a match made on a date rather
than an amount, an adjustment posted for a residual that was already covered.
Each test below is one of those, written against the judgement rather than the
field names.
"""

from __future__ import annotations

import pytest

from mcp_server_for_ynab.enriched.reconcile import match_statement, preview, resolve_marks
from mcp_server_for_ynab.models.errors import YnabMcpException
from tests.unit.test_enriched.builders import (
    account,
    account_response,
    make_ctx,
    transaction,
    transactions_response,
)


def _ctx(*txns, **kwargs):
    return make_ctx(
        account=account_response(account(name="Ally Spending", **kwargs)),
        transactions=transactions_response(*txns),
    )


async def test_balanced_when_the_statement_matches_the_cleared_balance() -> None:
    ctx = _ctx(
        transaction(id="a", date="2026-08-01", amount=-30_000, cleared="reconciled"),
        transaction(id="b", date="2026-08-02", amount=-20_000, cleared="cleared"),
    )

    result = await preview(ctx, "plan-1", "acct-1", -50_000, as_of_date="2026-08-31")

    assert result["balanced"] is True
    assert result["difference"] == 0
    assert result["to_mark_count"] == 1  # the cleared one still needs reconciling


async def test_uncleared_transactions_are_not_part_of_the_cleared_balance() -> None:
    ctx = _ctx(
        transaction(id="a", date="2026-08-01", amount=-30_000, cleared="cleared"),
        transaction(id="b", date="2026-08-02", amount=-5_000, cleared="uncleared"),
    )

    result = await preview(ctx, "plan-1", "acct-1", -30_000, as_of_date="2026-08-31")

    assert result["balanced"] is True
    assert result["uncleared_count"] == 1


async def test_the_cleared_balance_is_as_of_the_statement_date_not_today() -> None:
    """A transaction that cleared after the closing date is not on the statement."""
    ctx = _ctx(
        transaction(id="a", date="2026-08-01", amount=-30_000, cleared="cleared"),
        transaction(id="later", date="2026-09-05", amount=-70_000, cleared="cleared"),
    )

    result = await preview(ctx, "plan-1", "acct-1", -30_000, as_of_date="2026-08-31")

    assert result["balanced"] is True
    assert result["dated_after_as_of_count"] == 1


async def test_the_queues_that_explain_a_difference_are_separated() -> None:
    ctx = _ctx(
        transaction(id="hold", date="2026-07-01", amount=-7_900, cleared="uncleared", import_id="YNAB:P:abc"),
        transaction(id="byhand", date="2026-07-02", amount=-1_000, cleared="uncleared", import_id=None),
        transaction(id="fresh", date="2026-08-30", amount=-2_000, cleared="uncleared", import_id="YNAB:123"),
    )

    result = await preview(ctx, "plan-1", "acct-1", 0, as_of_date="2026-08-31", stale_after_days=7)

    assert result["pending_import_count"] == 1
    assert result["pending_import_total"] == -7_900
    assert result["manual_uncleared_count"] == 1
    # Stale is about age, so the hold and the hand-entered one qualify and the
    # transaction from yesterday does not.
    assert result["stale_uncleared_count"] == 2


async def test_difference_points_at_the_work_rather_than_declaring_success() -> None:
    ctx = _ctx(transaction(id="a", date="2026-08-01", amount=-30_000, cleared="cleared"))

    result = await preview(ctx, "plan-1", "acct-1", -37_900, as_of_date="2026-08-31")

    assert result["balanced"] is False
    assert result["difference"] == -7_900
    assert "match_statement" in result["next_step"]


async def test_every_response_says_the_reconciled_date_will_not_move() -> None:
    ctx = _ctx(transaction(id="a", cleared="cleared"))

    result = await preview(ctx, "plan-1", "acct-1", 0)

    assert "last_reconciled_at" in result["last_reconciled_note"]


async def test_an_unparseable_statement_date_names_the_argument() -> None:
    """Otherwise it surfaces as an internal error from a date comparison."""
    ctx = _ctx(transaction(id="a"))

    with pytest.raises(YnabMcpException) as excinfo:
        await preview(ctx, "plan-1", "acct-1", 0, as_of_date="August 31")

    assert "as_of_date" in excinfo.value.error.message


# ---------------------------------------------------------------------------
# Matching a bank export
# ---------------------------------------------------------------------------


async def test_rows_match_on_amount_within_the_date_tolerance() -> None:
    ctx = _ctx(transaction(id="t1", date="2026-08-14", amount=-42_500, cleared="cleared"))

    result = await match_statement(
        ctx,
        "plan-1",
        "acct-1",
        [{"date": "2026-08-16", "amount": -42_500, "description": "LYFT *RIDE"}],
    )

    assert result["matched_count"] == 1
    assert result["matched"][0]["transaction"]["id"] == "t1"
    assert result["matched"][0]["date_gap_days"] == 2
    assert result["unmatched_in_ynab_count"] == 0


async def test_a_row_outside_the_tolerance_does_not_match() -> None:
    ctx = _ctx(transaction(id="t1", date="2026-08-01", amount=-42_500))

    result = await match_statement(
        ctx,
        "plan-1",
        "acct-1",
        [{"date": "2026-08-14", "amount": -42_500}],
        date_tolerance_days=3,
    )

    assert result["matched_count"] == 0
    assert result["unmatched_on_statement_count"] == 1


async def test_one_statement_row_cannot_claim_two_transactions() -> None:
    """Two identical charges and one statement line leaves one in YNAB."""
    ctx = _ctx(
        transaction(id="t1", date="2026-08-14", amount=-9_990),
        transaction(id="t2", date="2026-08-14", amount=-9_990),
    )

    result = await match_statement(ctx, "plan-1", "acct-1", [{"date": "2026-08-14", "amount": -9_990}])

    assert result["matched_count"] == 1
    assert result["unmatched_in_ynab_count"] == 1


async def test_the_closest_date_wins_when_several_could_match() -> None:
    ctx = _ctx(
        transaction(id="far", date="2026-08-11", amount=-5_000),
        transaction(id="near", date="2026-08-14", amount=-5_000),
    )

    result = await match_statement(ctx, "plan-1", "acct-1", [{"date": "2026-08-13", "amount": -5_000}])

    assert result["matched"][0]["transaction"]["id"] == "near"


async def test_dollar_amounts_are_converted_when_asked_for() -> None:
    ctx = _ctx(transaction(id="t1", date="2026-08-14", amount=-42_500))

    result = await match_statement(
        ctx,
        "plan-1",
        "acct-1",
        [{"date": "2026-08-14", "amount": -42.50}],
        amounts_in="dollars",
    )

    assert result["matched_count"] == 1


async def test_what_is_left_in_ynab_is_labelled_with_what_it_looks_like() -> None:
    ctx = _ctx(
        transaction(id="hold", date="2026-08-14", amount=-7_900, import_id="YNAB:P:xyz"),
        transaction(id="byhand", date="2026-08-14", amount=-1_100, import_id=None),
    )

    result = await match_statement(ctx, "plan-1", "acct-1", [{"date": "2026-08-14", "amount": -55_000}])

    labels = {row["id"]: row["looks_like"] for row in result["unmatched_in_ynab"]}
    assert "never posted" in labels["hold"]
    assert "by hand" in labels["byhand"]
    assert result["unmatched_on_statement_count"] == 1


async def test_a_statement_row_without_a_date_is_refused_by_index() -> None:
    ctx = _ctx(transaction(id="t1"))

    with pytest.raises(YnabMcpException) as excinfo:
        await match_statement(ctx, "plan-1", "acct-1", [{"amount": -100}])

    assert "rows[0]" in excinfo.value.error.message


# ---------------------------------------------------------------------------
# Choosing what to mark
# ---------------------------------------------------------------------------


def test_marking_defaults_to_everything_cleared_up_to_the_date() -> None:
    register = [
        transaction(id="a", date="2026-08-01", cleared="cleared"),
        transaction(id="b", date="2026-08-02", cleared="uncleared"),
        transaction(id="c", date="2026-08-03", cleared="reconciled"),
        transaction(id="d", date="2026-09-02", cleared="cleared"),
    ]

    chosen = resolve_marks(register, as_of="2026-08-31", transaction_ids=None)

    assert [t.id for t in chosen] == ["a"]


def test_an_id_from_another_account_is_named_rather_than_ignored() -> None:
    register = [transaction(id="a", cleared="cleared")]

    with pytest.raises(YnabMcpException) as excinfo:
        resolve_marks(register, as_of="2026-08-31", transaction_ids=["a", "not-here"])

    assert "not-here" in excinfo.value.error.message


def test_explicit_ids_may_include_uncleared_transactions() -> None:
    """Reconciling from a matched statement confirms transactions the bank shows."""
    register = [
        transaction(id="a", date="2026-08-01", cleared="uncleared"),
        transaction(id="b", date="2026-08-02", cleared="reconciled"),
    ]

    chosen = resolve_marks(register, as_of="2026-08-31", transaction_ids=["a", "b"])

    # The already-reconciled one is left out: there is nothing to write.
    assert [t.id for t in chosen] == ["a"]
