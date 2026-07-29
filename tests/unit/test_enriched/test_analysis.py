"""Unit tests: enriched analysis tools."""

from __future__ import annotations

from mcp_server_for_ynab.enriched.analysis import overspent_categories, target_funding_gaps, upcoming_scheduled_risks
from tests.unit.test_enriched.builders import (
    categories_response,
    category,
    days_from_today,
    make_ctx,
    month,
    scheduled,
    scheduled_response,
)


async def test_overspent_lists_only_negative_balances() -> None:
    ctx = make_ctx(
        month_response=month(
            categories=[
                category("Groceries", id="c1", balance=-25_000),
                category("Rent", id="c2", balance=100_000),
                category("Gas", id="c3", balance=-5_000),
            ]
        )
    )
    result = await overspent_categories(ctx, "plan-1", "2026-07-01")

    assert result["overspent_count"] == 2
    assert [c["name"] for c in result["categories"]] == ["Groceries", "Gas"]  # most negative first
    assert result["total_overspent"] == -30_000


async def test_overspent_excludes_hidden_and_deleted() -> None:
    ctx = make_ctx(
        month_response=month(
            categories=[
                category("Visible", id="c1", balance=-1_000),
                category("Hidden", id="c2", balance=-99_000, hidden=True),
                category("Deleted", id="c3", balance=-99_000, deleted=True),
            ]
        )
    )
    result = await overspent_categories(ctx, "plan-1", "2026-07-01")

    assert result["overspent_count"] == 1
    assert result["total_overspent"] == -1_000


async def test_overspent_is_empty_when_nothing_is_negative() -> None:
    ctx = make_ctx(month_response=month(categories=[category("Rent", balance=10_000)]))
    result = await overspent_categories(ctx, "plan-1", "2026-07-01")

    assert result["overspent_count"] == 0
    assert result["categories"] == []
    assert result["total_overspent"] == 0


async def test_funding_gaps_treats_goal_under_funded_as_positive() -> None:
    """YNAB reports goal_under_funded as a positive shortfall.

    This filtered for negative values, so it reported zero gaps for every plan
    while appearing to succeed.
    """
    ctx = make_ctx(
        month_response=month(
            categories=[
                category("Vacation", id="c1", goal_under_funded=35_388_340),
                category("Car", id="c2", goal_under_funded=50_000),
                category("Funded", id="c3", goal_under_funded=0),
                category("No goal", id="c4", goal_under_funded=None),
            ]
        )
    )
    result = await target_funding_gaps(ctx, "plan-1", "2026-07-01")

    assert result["underfunded_count"] == 2
    assert result["total_gap"] == 35_438_340


async def test_funding_gaps_puts_the_largest_shortfall_first() -> None:
    ctx = make_ctx(
        month_response=month(
            categories=[
                category("Small", id="c1", goal_under_funded=1_000),
                category("Large", id="c2", goal_under_funded=900_000),
                category("Medium", id="c3", goal_under_funded=50_000),
            ]
        )
    )
    result = await target_funding_gaps(ctx, "plan-1", "2026-07-01")

    assert [c["name"] for c in result["categories"]] == ["Large", "Medium", "Small"]


async def test_funding_gaps_excludes_hidden_and_deleted() -> None:
    ctx = make_ctx(
        month_response=month(
            categories=[
                category("Visible", id="c1", goal_under_funded=1_000),
                category("Hidden", id="c2", goal_under_funded=900_000, hidden=True),
                category("Deleted", id="c3", goal_under_funded=900_000, deleted=True),
            ]
        )
    )
    result = await target_funding_gaps(ctx, "plan-1", "2026-07-01")

    assert result["underfunded_count"] == 1
    assert result["total_gap"] == 1_000


async def test_scheduled_risk_flags_insufficient_category_balance() -> None:
    ctx = make_ctx(
        scheduled_transactions=scheduled_response(scheduled(id="s1", amount=-50_000, category_id="c1")),
        categories=categories_response(category("Groceries", id="c1", balance=10_000)),
    )
    result = await upcoming_scheduled_risks(ctx, "plan-1", lookahead_days=3650)

    risk = result["scheduled_transactions"][0]
    assert risk["is_risk"] is True
    assert risk["shortfall"] == -40_000
    assert result["at_risk_count"] == 1


async def test_scheduled_not_at_risk_when_balance_covers_it() -> None:
    ctx = make_ctx(
        scheduled_transactions=scheduled_response(scheduled(id="s1", amount=-50_000, category_id="c1")),
        categories=categories_response(category("Groceries", id="c1", balance=80_000)),
    )
    result = await upcoming_scheduled_risks(ctx, "plan-1", lookahead_days=3650)

    assert result["at_risk_count"] == 0
    assert result["scheduled_transactions"][0]["shortfall"] == 30_000


async def test_scheduled_ignores_inflows() -> None:
    """Only outflows can overdraw a category."""
    ctx = make_ctx(
        scheduled_transactions=scheduled_response(scheduled(id="s1", amount=250_000)),
        categories=categories_response(category("Salary", id="c1", balance=0)),
    )
    result = await upcoming_scheduled_risks(ctx, "plan-1", lookahead_days=3650)

    assert result["upcoming_count"] == 0


async def test_scheduled_ignores_deleted() -> None:
    ctx = make_ctx(
        scheduled_transactions=scheduled_response(scheduled(id="s1", amount=-50_000, deleted=True)),
        categories=categories_response(category("Groceries", id="c1", balance=0)),
    )
    result = await upcoming_scheduled_risks(ctx, "plan-1", lookahead_days=3650)

    assert result["upcoming_count"] == 0


async def test_scheduled_outside_the_lookahead_window_is_excluded() -> None:
    ctx = make_ctx(
        scheduled_transactions=scheduled_response(
            scheduled(id="past", amount=-50_000, date_next=days_from_today(-1)),
            scheduled(id="inside", amount=-50_000, date_next=days_from_today(10)),
            scheduled(id="beyond", amount=-50_000, date_next=days_from_today(60)),
        ),
        categories=categories_response(category("Groceries", id="c1", balance=0)),
    )
    result = await upcoming_scheduled_risks(ctx, "plan-1", lookahead_days=30)

    assert [s["scheduled_transaction_id"] for s in result["scheduled_transactions"]] == ["inside"]


async def test_scheduled_due_today_is_included() -> None:
    ctx = make_ctx(
        scheduled_transactions=scheduled_response(scheduled(id="today", amount=-50_000, date_next=days_from_today(0))),
        categories=categories_response(category("Groceries", id="c1", balance=0)),
    )
    result = await upcoming_scheduled_risks(ctx, "plan-1", lookahead_days=30)

    assert result["upcoming_count"] == 1


async def test_scheduled_without_category_is_not_flagged() -> None:
    """An uncategorized scheduled transaction has no balance to compare against."""
    ctx = make_ctx(
        scheduled_transactions=scheduled_response(scheduled(id="s1", amount=-50_000, category_id=None)),
        categories=categories_response(category("Groceries", id="c1", balance=0)),
    )
    result = await upcoming_scheduled_risks(ctx, "plan-1", lookahead_days=3650)

    risk = result["scheduled_transactions"][0]
    assert risk["is_risk"] is False
    assert risk["category_balance"] is None
