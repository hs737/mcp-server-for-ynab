"""Unit tests: matching credit accounts to their payment categories.

The match is by name because YNAB offers no identifier, so the naming edge
cases are the substance of this: a trailing space in an account name, a closed
account, a category with no account left to pay.
"""

from __future__ import annotations

from mcp_server_for_ynab.enriched.credit import credit_position
from mcp_server_for_ynab.enriched.overview import budget_snapshot
from tests.unit.test_enriched.builders import (
    account,
    accounts_response,
    category,
    category_group,
    groups_response,
    make_ctx,
    month,
)


def _payments(*categories: object) -> list[object]:
    return [
        category_group("Everyday", categories=[category(id="c1")]),
        category_group("Credit Card Payments", id="ccp", hidden=True, categories=list(categories)),  # type: ignore[arg-type]
    ]


def test_debt_beyond_the_payment_category_is_reported_as_unfunded() -> None:
    groups = _payments(category(id="pay", name="Visa", balance=30_000, group_id="ccp"))
    accounts = [account(id="card", name="Visa", type="creditCard", balance=-100_000)]

    result = credit_position(accounts, groups)  # type: ignore[arg-type]

    row = result["accounts"][0]
    assert row["debt"] == 100_000
    assert row["funded"] == 30_000
    assert row["unfunded"] == 70_000
    assert row["fully_funded"] is False
    assert result["total_unfunded_debt"] == 70_000


def test_a_name_differing_only_by_a_trailing_space_still_matches() -> None:
    """Live plans really do have these; an exact-only match would report the
    account unmatched and the category stranded, which is two wrong answers."""
    groups = _payments(category(id="pay", name="Sapphire Credit (Joint)", balance=1_000, group_id="ccp"))
    accounts = [account(id="card", name="Sapphire Credit (Joint) ", type="creditCard", balance=-1_000)]

    result = credit_position(accounts, groups)  # type: ignore[arg-type]

    assert result["accounts"][0]["payment_category_id"] == "pay"
    assert result["unmatched_payment_categories"] == []


def test_money_left_in_a_closed_account_payment_category_is_trapped() -> None:
    groups = _payments(category(id="pay", name="Old Card", balance=45_000, group_id="ccp"))
    accounts = [account(id="card", name="Old Card", type="creditCard", balance=0, closed=True)]

    result = credit_position(accounts, groups)  # type: ignore[arg-type]

    assert result["trapped_funds"] == 45_000
    assert "closed" in result["accounts"][0]["note"]


def test_a_payment_category_with_no_account_is_reported_not_dropped() -> None:
    groups = _payments(category(id="orphan", name="Deleted Card", balance=12_000, group_id="ccp"))

    result = credit_position([], groups)  # type: ignore[arg-type]

    assert result["unmatched_payment_categories"][0]["category_id"] == "orphan"
    assert result["trapped_funds"] == 12_000


def test_an_overpaid_card_is_not_counted_as_debt() -> None:
    groups = _payments(category(id="pay", name="Visa", balance=0, group_id="ccp"))
    accounts = [account(id="card", name="Visa", type="creditCard", balance=5_000)]

    result = credit_position(accounts, groups)  # type: ignore[arg-type]

    assert result["accounts"][0]["debt"] == 0
    assert result["total_unfunded_debt"] == 0


def test_a_plan_with_no_payment_group_says_so_instead_of_failing() -> None:
    result = credit_position(
        [account(id="card", name="Visa", type="creditCard", balance=-1_000)],
        [category_group("Everyday")],  # type: ignore[arg-type]
    )

    assert result["payment_group_found"] is False
    assert result["accounts"][0]["unfunded"] is None
    assert "No payment category" in result["accounts"][0]["note"]


async def test_the_snapshot_carries_unfunded_debt_and_trapped_funds() -> None:
    ctx = make_ctx(
        month_response=month(),
        accounts=accounts_response(
            account(id="card", name="Visa", type="creditCard", balance=-100_000),
            account(id="old", name="Old Card", type="creditCard", balance=0, closed=True),
        ),
        categories=groups_response(
            category_group("Everyday", categories=[category(id="c1")]),
            category_group(
                "Credit Card Payments",
                id="ccp",
                hidden=True,
                categories=[
                    category(id="pay", name="Visa", balance=30_000, group_id="ccp"),
                    category(id="pay2", name="Old Card", balance=45_000, group_id="ccp"),
                ],
            ),
        ),
    )

    result = await budget_snapshot(ctx, "plan-1")

    assert result["unfunded_card_debt"] == 70_000
    assert result["trapped_funds"] == 45_000
