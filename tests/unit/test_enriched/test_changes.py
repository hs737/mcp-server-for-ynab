"""Unit tests: delta sync made usable.

The two behaviours that matter are the baseline call, which must not pretend a
full plan is a change set, and carrying the right knowledge value forward.
"""

from __future__ import annotations

from mcp_server_for_ynab.enriched.changes import changes_since
from tests.unit.test_enriched.builders import (
    categories_response,
    category,
    make_ctx,
    month_summary,
    months_list_response,
    transaction,
    transactions_response,
)


def _ctx(knowledge: int = 42):
    return make_ctx(
        categories=categories_response(category(id="c1"), server_knowledge=knowledge),
        months_list=months_list_response(month_summary(), server_knowledge=knowledge - 2),
        transactions=transactions_response(transaction(id="t1"), server_knowledge=knowledge - 1),
    )


async def test_the_first_call_is_a_baseline_not_a_change_set() -> None:
    result = await changes_since(_ctx(), "plan-1")

    assert result["baseline"] is True
    assert "categories" not in result  # the whole plan is not a list of changes
    assert "not a change set" in result["note"]


async def test_the_highest_knowledge_value_is_the_one_carried_forward() -> None:
    """The counter is plan-wide but the three routes answer at different points;
    handing back the lowest would re-deliver changes already seen."""
    result = await changes_since(_ctx(knowledge=42), "plan-1")

    assert result["server_knowledge"] == 42


async def test_a_later_call_returns_what_moved() -> None:
    ctx = _ctx()

    result = await changes_since(ctx, "plan-1", 30)

    assert result["baseline"] is False
    assert result["changed_category_count"] == 1
    assert result["changed_transaction_count"] == 1
    assert result["categories"][0]["id"] == "c1"
    assert ctx.categories.list.await_args.kwargs["last_knowledge_of_server"] == 30
