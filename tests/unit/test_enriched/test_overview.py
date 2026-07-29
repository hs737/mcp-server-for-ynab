"""Unit tests: enriched orientation tools."""

from __future__ import annotations

from tests.unit.test_enriched.builders import (
    account,
    accounts_response,
    categories_response,
    category,
    make_ctx,
    month,
)
from ynab_mcp.enriched.overview import budget_snapshot, cash_position, month_health


async def test_snapshot_passes_month_totals_through_unchanged() -> None:
    """Totals are YNAB's own numbers; the snapshot must not reinterpret them."""
    ctx = make_ctx(
        month_response=month(income=17_257_340, budgeted=-21_866_360, activity=-13_884_450, to_be_budgeted=-40_240)
    )
    result = await budget_snapshot(ctx, "plan-1")

    assert result["income"] == 17_257_340
    assert result["budgeted"] == -21_866_360
    assert result["activity"] == -13_884_450
    assert result["to_be_budgeted"] == -40_240


async def test_snapshot_counts_accounts_by_budget_status() -> None:
    ctx = make_ctx(
        accounts=accounts_response(
            account("Checking", id="a1", on_budget=True),
            account("Savings", id="a2", on_budget=True),
            account("Brokerage", id="a3", on_budget=False),
            account("Closed", id="a4", on_budget=True, closed=True),
            account("Deleted", id="a5", on_budget=True, deleted=True),
        )
    )
    result = await budget_snapshot(ctx, "plan-1")

    assert result["on_budget_account_count"] == 2
    assert result["off_budget_account_count"] == 1


async def test_snapshot_caps_overspent_list_at_ten() -> None:
    cats = [category(f"Cat {i}", id=f"c{i}", balance=-1_000 * (i + 1)) for i in range(15)]
    ctx = make_ctx(categories=categories_response(*cats))
    result = await budget_snapshot(ctx, "plan-1")

    assert result["overspent_category_count"] == 15
    assert len(result["overspent_categories"]) == 10


async def test_month_health_treats_goal_under_funded_as_positive() -> None:
    """Same sign bug as target_funding_gaps: this reported zero for every plan."""
    ctx = make_ctx(
        month_response=month(
            categories=[
                category("Vacation", id="c1", goal_under_funded=900_000),
                category("Car", id="c2", goal_under_funded=1_000),
                category("Funded", id="c3", goal_under_funded=0),
            ]
        )
    )
    result = await month_health(ctx, "plan-1", "2026-07-01")

    assert result["underfunded_goal_count"] == 2
    assert [g["name"] for g in result["underfunded_goals"]] == ["Vacation", "Car"]  # largest first


async def test_month_health_separates_overspent_from_underfunded() -> None:
    """A negative balance and an unmet goal are different problems."""
    ctx = make_ctx(
        month_response=month(
            categories=[
                category("Overspent", id="c1", balance=-5_000),
                category("Underfunded", id="c2", balance=1_000, goal_under_funded=20_000),
            ]
        )
    )
    result = await month_health(ctx, "plan-1", "2026-07-01")

    assert result["overspent_count"] == 1
    assert result["overspent_categories"][0]["name"] == "Overspent"
    assert result["underfunded_goal_count"] == 1
    assert result["underfunded_goals"][0]["name"] == "Underfunded"


async def test_cash_position_sums_net_worth_across_budget_status() -> None:
    ctx = make_ctx(
        accounts=accounts_response(
            account("Checking", id="a1", balance=250_000, on_budget=True),
            account("Card", id="a2", balance=-100_000, on_budget=True),
            account("Brokerage", id="a3", balance=1_000_000, on_budget=False),
        )
    )
    result = await cash_position(ctx, "plan-1")

    assert result["on_budget_total"] == 150_000
    assert result["off_budget_total"] == 1_000_000
    assert result["net_worth"] == 1_150_000


async def test_cash_position_excludes_closed_and_deleted() -> None:
    ctx = make_ctx(
        accounts=accounts_response(
            account("Open", id="a1", balance=100_000),
            account("Closed", id="a2", balance=999_000, closed=True),
            account("Deleted", id="a3", balance=999_000, deleted=True),
        )
    )
    result = await cash_position(ctx, "plan-1")

    assert result["net_worth"] == 100_000
    assert len(result["on_budget_accounts"]) == 1


async def test_cash_position_of_an_empty_plan() -> None:
    ctx = make_ctx(accounts=accounts_response())
    result = await cash_position(ctx, "plan-1")

    assert result["net_worth"] == 0
    assert result["on_budget_accounts"] == []
    assert result["off_budget_accounts"] == []
