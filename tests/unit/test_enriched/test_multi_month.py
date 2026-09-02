"""Unit tests: month ranges, compact projections, and the matrix shape.

The point of these tools is that one call answers a question that used to take
twenty-one, so the tests pin the two things that make that true: the range
expands correctly, and a category keeps one row across the whole range even
when it changes name or group part-way.
"""

from __future__ import annotations

import pytest

from mcp_server_for_ynab.enriched.multi_month import (
    MAX_RANGE_MONTHS,
    compact_category,
    group_series,
    month_sequence,
    month_series,
    normalize_month,
)
from mcp_server_for_ynab.models.errors import YnabMcpException
from tests.unit.test_enriched.builders import category, make_ctx, month


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("2025-03", "2025-03-01"),
        ("2025-03-01", "2025-03-01"),
        ("2025-03-17", "2025-03-01"),
        ("  2025-03  ", "2025-03-01"),
    ],
)
def test_month_forms_all_normalize(given: str, expected: str) -> None:
    assert normalize_month(given) == expected


def test_a_bad_month_says_what_is_accepted() -> None:
    with pytest.raises(YnabMcpException) as caught:
        normalize_month("March 2025")

    assert "YYYY-MM" in caught.value.error.message


def test_sequence_is_inclusive_and_crosses_the_year() -> None:
    assert month_sequence("2025-11", "2026-02") == [
        "2025-11-01",
        "2025-12-01",
        "2026-01-01",
        "2026-02-01",
    ]


def test_a_reversed_range_is_refused_rather_than_returning_nothing() -> None:
    with pytest.raises(YnabMcpException) as caught:
        month_sequence("2026-05", "2026-01")

    assert "after" in caught.value.error.message


def test_a_range_past_the_cap_is_refused_with_the_reason() -> None:
    with pytest.raises(YnabMcpException) as caught:
        month_sequence("2000-01", "2026-01")

    message = caught.value.error.message
    assert str(MAX_RANGE_MONTHS) in message
    assert "request" in message  # says why the cap exists, not just that it exists


def test_compact_keeps_six_fields_and_drops_the_goal_machinery() -> None:
    compact = compact_category(category(goal_under_funded=5_000, note="a note"))

    assert set(compact) == {"id", "group", "name", "budgeted", "activity", "balance"}


def _three_months() -> dict[str, object]:
    return {
        "2026-05-01": month(
            month="2026-05-01",
            categories=[category(id="c1", name="Groceries", budgeted=10_000, balance=1_000)],
        ),
        "2026-06-01": month(
            month="2026-06-01",
            categories=[category(id="c1", name="Groceries", budgeted=20_000, balance=2_000)],
        ),
        "2026-07-01": month(
            month="2026-07-01",
            # Renamed mid-range: still one row, named by the latest month.
            categories=[category(id="c1", name="Food", budgeted=30_000, balance=3_000)],
        ),
    }


async def test_matrix_gives_a_category_one_row_across_the_range() -> None:
    ctx = make_ctx(months_by_month=_three_months())  # type: ignore[arg-type]

    result = await month_series(ctx, "plan-1", "2026-05", "2026-07")

    assert result["month_count"] == 3
    assert result["category_count"] == 1
    row = result["categories"][0]
    assert row["name"] == "Food"
    assert [point["budgeted"] for point in row["series"]] == [10_000, 20_000, 30_000]


async def test_matrix_narrows_to_the_categories_asked_for() -> None:
    months = {
        "2026-06-01": month(
            month="2026-06-01",
            categories=[category(id="c1"), category(id="c2", name="Fuel")],
        )
    }
    ctx = make_ctx(months_by_month=months)  # type: ignore[arg-type]

    result = await month_series(ctx, "plan-1", "2026-06", "2026-06", category_ids=["c2"])

    assert [row["id"] for row in result["categories"]] == ["c2"]


async def test_hidden_categories_stay_out_unless_asked_for() -> None:
    months = {
        "2026-06-01": month(
            month="2026-06-01",
            categories=[category(id="c1"), category(id="cc", name="Visa", hidden=True)],
        )
    }

    without = await month_series(
        make_ctx(months_by_month=months),  # type: ignore[arg-type]
        "plan-1",
        "2026-06",
        "2026-06",
    )
    with_hidden = await month_series(
        make_ctx(months_by_month=months),  # type: ignore[arg-type]
        "plan-1",
        "2026-06",
        "2026-06",
        include_hidden=True,
    )

    assert without["category_count"] == 1
    assert with_hidden["category_count"] == 2


async def test_group_summary_totals_each_group_per_month() -> None:
    months = {
        "2026-06-01": month(
            month="2026-06-01",
            categories=[
                category(id="c1", budgeted=10_000, activity=-4_000, balance=6_000),
                category(id="c2", budgeted=5_000, activity=-1_000, balance=4_000),
                category(id="c3", group_id="group-2", group_name="Fun", budgeted=2_000, balance=2_000),
            ],
        )
    }
    ctx = make_ctx(months_by_month=months)  # type: ignore[arg-type]

    result = await group_series(ctx, "plan-1", "2026-06", "2026-06")

    everyday = next(g for g in result["groups"] if g["group"] == "Everyday")
    assert everyday["series"][0]["budgeted"] == 15_000
    assert everyday["series"][0]["activity"] == -5_000
    assert everyday["series"][0]["category_count"] == 2
