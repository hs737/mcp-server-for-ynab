"""Unit tests: the multi-month audit tools.

Each of these encodes a judgement that is easy to get subtly wrong — which
overspending comes out of next month's Ready to Assign, what counts as a
copied-forward month, which categories belong in the balance identity — so the
tests are written against the judgement rather than the field names.
"""

from __future__ import annotations

from mcp_server_for_ynab.enriched.audit import (
    balance_identity,
    copied_forward_months,
    flow_trace,
    group_parity,
    overspent_history,
)
from tests.unit.test_enriched.builders import (
    account,
    accounts_response,
    categories_response,
    category,
    category_group,
    groups_response,
    make_ctx,
    money_movement,
    money_movements_response,
    month,
    transaction,
    transactions_response,
)


async def test_overspending_charged_to_a_card_is_credit_not_cash() -> None:
    months = {
        "2026-06-01": month(
            month="2026-06-01",
            categories=[category(id="c1", budgeted=10_000, activity=-30_000, balance=-20_000)],
        )
    }
    ctx = make_ctx(
        months_by_month=months,  # type: ignore[arg-type]
        accounts=accounts_response(account(id="card", type="creditCard")),
        transactions=transactions_response(
            transaction(id="t1", date="2026-06-10", amount=-30_000, account_id="card", category_id="c1")
        ),
    )

    result = await overspent_history(ctx, "plan-1", "2026-06", "2026-06")

    row = result["months"][0]["categories"][0]
    assert row["kind"] == "credit"
    assert row["credit_overspend"] == 20_000
    # Nothing was taken out of the next month's Ready to Assign.
    assert result["absorbed_into_ready_to_assign"] == 0


async def test_overspending_from_a_bank_account_is_absorbed_by_ready_to_assign() -> None:
    months = {
        "2026-06-01": month(
            month="2026-06-01",
            categories=[category(id="c1", budgeted=10_000, activity=-30_000, balance=-20_000)],
        )
    }
    ctx = make_ctx(
        months_by_month=months,  # type: ignore[arg-type]
        accounts=accounts_response(account(id="acct-1", type="checking")),
        transactions=transactions_response(transaction(id="t1", date="2026-06-10", amount=-30_000, category_id="c1")),
    )

    result = await overspent_history(ctx, "plan-1", "2026-06", "2026-06")

    row = result["months"][0]["categories"][0]
    assert row["kind"] == "cash"
    assert result["absorbed_into_ready_to_assign"] == 20_000


async def test_a_split_charged_to_a_card_is_attributed_to_its_parts() -> None:
    """The parent of a split has no category; counting it would credit nothing."""
    split = transaction(
        id="t1",
        date="2026-06-10",
        amount=-30_000,
        account_id="card",
        category_id=None,
        subtransactions=[
            {
                "id": "s1",
                "transaction_id": "t1",
                "amount": -20_000,
                "category_id": "c1",
                "deleted": False,
            }
        ],
    )
    months = {
        "2026-06-01": month(
            month="2026-06-01",
            categories=[category(id="c1", budgeted=0, activity=-20_000, balance=-20_000)],
        )
    }
    ctx = make_ctx(
        months_by_month=months,  # type: ignore[arg-type]
        accounts=accounts_response(account(id="card", type="creditCard")),
        transactions=transactions_response(split),
    )

    result = await overspent_history(ctx, "plan-1", "2026-06", "2026-06")

    assert result["months"][0]["categories"][0]["kind"] == "credit"


async def test_a_month_repeating_the_previous_one_is_flagged() -> None:
    same = [category(id="c1", budgeted=10_000), category(id="c2", name="Fuel", budgeted=5_000)]
    months = {
        "2026-05-01": month(month="2026-05-01", categories=same),
        "2026-06-01": month(month="2026-06-01", categories=same),
    }
    ctx = make_ctx(months_by_month=months)  # type: ignore[arg-type]

    result = await copied_forward_months(ctx, "plan-1", "2026-06", "2026-06")

    assert result["copied_forward_months"] == ["2026-06-01"]
    carried = result["months"][0]["largest_assignments_carried_forward"]
    assert carried[0]["budgeted"] == 10_000


async def test_one_changed_assignment_is_enough_to_clear_the_flag() -> None:
    months = {
        "2026-05-01": month(month="2026-05-01", categories=[category(id="c1", budgeted=10_000)]),
        "2026-06-01": month(month="2026-06-01", categories=[category(id="c1", budgeted=10_001)]),
    }
    ctx = make_ctx(months_by_month=months)  # type: ignore[arg-type]

    result = await copied_forward_months(ctx, "plan-1", "2026-06", "2026-06")

    assert result["copied_forward_months"] == []
    assert result["months"][0]["categories_differing"] == 1


async def test_a_month_that_assigned_nothing_is_not_a_copy() -> None:
    """Two empty months match exactly and mean nothing; flagging them is noise."""
    months = {
        "2026-05-01": month(month="2026-05-01", categories=[category(id="c1", budgeted=0)]),
        "2026-06-01": month(month="2026-06-01", categories=[category(id="c1", budgeted=0)]),
    }
    ctx = make_ctx(months_by_month=months)  # type: ignore[arg-type]

    result = await copied_forward_months(ctx, "plan-1", "2026-06", "2026-06")

    assert result["copied_forward_months"] == []


async def test_group_parity_reports_the_gap_as_a_minus_b() -> None:
    months = {
        "2026-06-01": month(
            month="2026-06-01",
            categories=[
                category(id="a1", group_id="ga", group_name="Alex", budgeted=50_000, activity=-40_000),
                category(id="b1", group_id="gb", group_name="Sam", budgeted=20_000, activity=-10_000),
            ],
        )
    }
    ctx = make_ctx(months_by_month=months)  # type: ignore[arg-type]

    result = await group_parity(ctx, "plan-1", "ga", "gb", "2026-06", "2026-06")

    assert result["total_budgeted_gap"] == 30_000
    assert result["group_a"]["name"] == "Alex"
    assert result["months"][0]["activity_gap"] == -30_000


async def test_group_parity_warns_when_a_group_id_matches_nothing() -> None:
    months = {"2026-06-01": month(month="2026-06-01", categories=[category(id="a1", group_id="ga", group_name="Alex")])}
    ctx = make_ctx(months_by_month=months)  # type: ignore[arg-type]

    result = await group_parity(ctx, "plan-1", "ga", "missing", "2026-06", "2026-06")

    assert "warning" in result
    assert "missing" in result["warning"]


async def test_flow_trace_separates_assigned_from_moved_and_spent() -> None:
    months = {
        "2026-06-01": month(
            month="2026-06-01",
            categories=[category(id="c1", budgeted=60_000, activity=-25_000, balance=35_000)],
        )
    }
    ctx = make_ctx(
        months_by_month=months,  # type: ignore[arg-type]
        money_movements=money_movements_response(
            money_movement(id="m1", month="2026-06-01", amount=10_000, to_category_id="c1"),
            money_movement(id="m2", month="2026-06-01", amount=4_000, from_category_id="c1", to_category_id="c2"),
        ),
        transactions=transactions_response(
            transaction(id="t1", date="2026-06-05", amount=-30_000, category_id="c1"),
            transaction(id="t2", date="2026-06-09", amount=5_000, category_id="c1"),
        ),
    )

    result = await flow_trace(ctx, "plan-1", "c1", "2026-06", "2026-06")

    row = result["months"][0]
    assert row["assigned"] == 60_000
    assert row["moved_in"] == 10_000
    assert row["moved_out"] == 4_000
    assert row["spent"] == 30_000
    assert row["refunds"] == 5_000
    assert result["category_name"] == "Groceries"


async def test_the_identity_ties_when_the_plan_is_consistent() -> None:
    """categories + Ready to Assign = on-budget accounts + card debt."""
    ctx = make_ctx(
        month_response=month(to_be_budgeted=5_000),
        categories=groups_response(
            category_group(categories=[category(id="c1", balance=100_000)]),
            category_group(
                "Credit Card Payments",
                id="ccp",
                hidden=True,
                categories=[category(id="cc", name="Visa", balance=30_000, group_id="ccp", group_name="CCP")],
            ),
        ),
        accounts=accounts_response(
            # Cash holds exactly what the categories and Ready to Assign claim:
            # 100,000 assigned + 30,000 held for the card + 5,000 unassigned.
            account(id="chk", balance=135_000),
            account(id="card", type="creditCard", balance=-30_000),
        ),
    )

    result = await balance_identity(ctx, "plan-1")

    assert result["ties"] is True
    assert result["difference"] == 0
    assert result["account_side"]["credit_card_debt"] == 30_000


async def test_the_identity_ignores_the_internal_inflow_category() -> None:
    """Its balance is cumulative income; counting it would inflate every plan."""
    ctx = make_ctx(
        month_response=month(to_be_budgeted=0),
        categories=groups_response(
            category_group(categories=[category(id="c1", balance=100_000)]),
            category_group(
                "Internal Master Category",
                id="imc",
                categories=[
                    category(
                        id="rta",
                        name="Inflow: Ready to Assign",
                        balance=9_000_000,
                        group_id="imc",
                        group_name="Internal Master Category",
                    )
                ],
            ),
        ),
        accounts=accounts_response(account(id="chk", balance=100_000)),
    )

    result = await balance_identity(ctx, "plan-1")

    assert result["ties"] is True
    assert result["excluded_internal_categories"][0]["balance"] == 9_000_000


async def test_a_mismatch_is_reported_rather_than_rounded_away() -> None:
    ctx = make_ctx(
        month_response=month(to_be_budgeted=0),
        categories=categories_response(category(id="c1", balance=100_000)),
        accounts=accounts_response(account(id="chk", balance=90_000)),
    )

    result = await balance_identity(ctx, "plan-1")

    assert result["ties"] is False
    assert result["difference"] == 10_000
