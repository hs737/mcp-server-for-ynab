"""Unit tests: recurring-charge detection.

The design claim under test is that this needs no fuzzy name matching. YNAB
resolves a merchant to one payee record regardless of how the bank spelled the
descriptor, so grouping on payee_id is exact — and these tests pin that a
differing payee_name never splits or merges a series.
"""

from __future__ import annotations

from datetime import date, timedelta

from mcp_server_for_ynab.enriched.analysis import recurring_charges
from tests.unit.test_enriched.builders import make_ctx, transaction, transactions_response


def _monthly(payee_id: str, count: int, amount: int = -9_990, *, payee_name: str = "Netflix", start_days_ago: int = 0):
    """A charge repeating roughly every 30 days, newest last."""
    out = []
    for index in range(count):
        when = date.today() - timedelta(days=start_days_ago + 30 * (count - 1 - index))
        out.append(
            transaction(
                id=f"{payee_id}-{index}",
                date=when.isoformat(),
                amount=amount,
                payee_id=payee_id,
                payee_name=payee_name,
            )
        )
    return out


async def test_a_monthly_series_is_found_with_its_cadence() -> None:
    ctx = make_ctx(transactions=transactions_response(*_monthly("p1", 6)))

    result = await recurring_charges(ctx, "plan-1")

    assert result["recurring_count"] == 1
    charge = result["charges"][0]
    assert charge["cadence"] == "monthly"
    assert charge["occurrences"] == 6
    assert charge["payee_name"] == "Netflix"


async def test_annual_cost_extrapolates_from_the_cadence() -> None:
    ctx = make_ctx(transactions=transactions_response(*_monthly("p1", 6, amount=-10_000)))

    charge = (await recurring_charges(ctx, "plan-1"))["charges"][0]

    assert charge["typical_amount"] == 10_000
    assert charge["estimated_annual_cost"] == 120_000


async def test_two_charges_are_not_enough_to_call_it_recurring() -> None:
    """Two of anything is a coincidence as often as a subscription."""
    ctx = make_ctx(transactions=transactions_response(*_monthly("p1", 2)))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 0


async def test_irregular_charges_are_not_reported() -> None:
    """A payee visited often but at no rhythm is not a subscription."""
    days = [0, 3, 41, 44, 47, 100]
    txns = [
        transaction(id=f"t{i}", date=(date.today() - timedelta(days=d)).isoformat(), amount=-4_000, payee_id="p1")
        for i, d in enumerate(days)
    ]
    ctx = make_ctx(transactions=transactions_response(*txns))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 0


async def test_grouping_survives_a_payee_name_that_varies() -> None:
    """The whole point of keying on payee_id rather than the name."""
    charges = _monthly("p1", 5)
    for index, txn in enumerate(charges):
        txn.payee_name = f"NETFLIX.COM {index}"
    ctx = make_ctx(transactions=transactions_response(*charges))

    result = await recurring_charges(ctx, "plan-1")

    assert result["recurring_count"] == 1
    assert result["charges"][0]["occurrences"] == 5


async def test_same_name_under_two_payee_ids_stays_two_series() -> None:
    """Over-reporting is the safer failure: never silently merge distinct payees."""
    ctx = make_ctx(transactions=transactions_response(*_monthly("p1", 4), *_monthly("p2", 4)))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 2


async def test_inflows_are_ignored() -> None:
    """A recurring paycheck is not a subscription."""
    ctx = make_ctx(transactions=transactions_response(*_monthly("p1", 5, amount=250_000)))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 0


async def test_transfers_are_excluded() -> None:
    """Moving money between your own accounts is not a charge."""
    charges = _monthly("p1", 5)
    for txn in charges:
        txn.transfer_account_id = "acct-2"
    ctx = make_ctx(transactions=transactions_response(*charges))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 0


async def test_deleted_transactions_are_excluded() -> None:
    charges = _monthly("p1", 5)
    for txn in charges:
        txn.deleted = True
    ctx = make_ctx(transactions=transactions_response(*charges))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 0


async def test_a_price_rise_is_surfaced_rather_than_averaged_away() -> None:
    charges = _monthly("p1", 5, amount=-9_990)
    charges[-1].amount = -12_990
    ctx = make_ctx(transactions=transactions_response(*charges))

    charge = (await recurring_charges(ctx, "plan-1"))["charges"][0]

    assert charge["amount_changed"] is True
    assert charge["last_amount"] == 12_990


async def test_a_lapsed_charge_reports_how_long_since_it_was_seen() -> None:
    ctx = make_ctx(transactions=transactions_response(*_monthly("p1", 5, start_days_ago=200)))

    charge = (await recurring_charges(ctx, "plan-1"))["charges"][0]

    assert charge["days_since_last"] >= 200


async def test_results_are_ordered_by_annual_cost() -> None:
    ctx = make_ctx(
        transactions=transactions_response(
            *_monthly("cheap", 4, amount=-1_000),
            *_monthly("dear", 4, amount=-50_000),
        )
    )

    result = await recurring_charges(ctx, "plan-1")

    assert [c["payee_id"] for c in result["charges"]] == ["dear", "cheap"]
    assert result["estimated_annual_total"] == result["charges"][0]["estimated_annual_cost"] + (1_000 * 12)


async def test_transactions_without_a_payee_are_skipped() -> None:
    charges = _monthly("p1", 5)
    for txn in charges:
        txn.payee_id = None
    ctx = make_ctx(transactions=transactions_response(*charges))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 0


async def test_a_regularly_visited_shop_is_not_a_subscription() -> None:
    """The failure that cadence alone cannot catch.

    Someone who buys groceries most weeks produces a textbook weekly cadence
    at a different amount every time. Against a real plan, accepting that
    turned 58 reported "subscriptions" into mostly ordinary shopping.
    """
    amounts = [-4_210, -18_940, -7_330, -23_110, -6_050, -31_770]
    txns = [
        transaction(
            id=f"g{index}",
            date=(date.today() - timedelta(days=7 * (len(amounts) - index))).isoformat(),
            amount=amount,
            payee_id="grocer",
            payee_name="Publix",
        )
        for index, amount in enumerate(amounts)
    ]
    ctx = make_ctx(transactions=transactions_response(*txns))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 0


async def test_a_steady_amount_on_the_same_cadence_still_counts() -> None:
    """The control for the test above: same rhythm, consistent amount."""
    ctx = make_ctx(transactions=transactions_response(*_monthly("p1", 6, amount=-14_99)))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 1


async def test_small_price_drift_does_not_disqualify_a_subscription() -> None:
    """A few percent of movement is a price change, not a different kind of charge."""
    charges = _monthly("p1", 6, amount=-10_000)
    charges[-1].amount = -10_400
    ctx = make_ctx(transactions=transactions_response(*charges))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 1


async def test_uneven_gaps_are_rejected_even_when_the_median_fits() -> None:
    """Gaps of 2, 6 and 40 days have a weekly median and no rhythm at all."""
    offsets = [48, 46, 40, 0]
    txns = [
        transaction(
            id=f"u{index}",
            date=(date.today() - timedelta(days=offset)).isoformat(),
            amount=-5_000,
            payee_id="p1",
        )
        for index, offset in enumerate(offsets)
    ]
    ctx = make_ctx(transactions=transactions_response(*txns))

    assert (await recurring_charges(ctx, "plan-1"))["recurring_count"] == 0


async def test_confidence_signals_are_reported() -> None:
    ctx = make_ctx(transactions=transactions_response(*_monthly("p1", 8)))

    charge = (await recurring_charges(ctx, "plan-1"))["charges"][0]

    assert charge["amount_consistency"] == 1.0
    assert charge["cadence_regularity"] == 1.0
