"""Unit tests: client-side transaction filters.

They run before pagination, which is the whole point — a page of a filtered
list is a page of answers, and total_available counts matches rather than rows.
"""

from __future__ import annotations

import pytest

from mcp_server_for_ynab.models.errors import YnabMcpException
from mcp_server_for_ynab.server.tools.filters import apply_transaction_filters
from mcp_server_for_ynab.server.tools.pagination import paginate_items
from tests.unit.test_enriched.builders import transaction


def _mixed() -> list[object]:
    return [
        transaction(id="a", amount=-100_000, cleared="cleared", import_id="YNAB:1"),
        transaction(id="b", amount=-1_000, cleared="uncleared"),
        transaction(id="c", amount=250_000, cleared="reconciled", import_id="YNAB:2"),
    ]


def test_cleared_status_selects_one_state() -> None:
    kept = apply_transaction_filters(_mixed(), cleared="uncleared")

    assert [t.id for t in kept] == ["b"]


def test_manual_only_keeps_what_the_bank_did_not_import() -> None:
    kept = apply_transaction_filters(_mixed(), manual_only=True)

    assert [t.id for t in kept] == ["b"]


def test_min_amount_is_a_size_not_a_signed_threshold() -> None:
    """An outflow of $100 and an inflow of $250 are both larger than $50."""
    kept = apply_transaction_filters(_mixed(), min_amount=50_000)

    assert [t.id for t in kept] == ["a", "c"]


def test_filters_combine() -> None:
    kept = apply_transaction_filters(_mixed(), cleared="cleared", min_amount=50_000)

    assert [t.id for t in kept] == ["a"]


def test_an_unknown_cleared_value_names_the_ones_that_work() -> None:
    with pytest.raises(YnabMcpException) as caught:
        apply_transaction_filters(_mixed(), cleared="pending")

    assert "uncleared" in caught.value.error.message


def test_a_negative_min_amount_explains_the_convention() -> None:
    with pytest.raises(YnabMcpException) as caught:
        apply_transaction_filters(_mixed(), min_amount=-1)

    assert "absolute" in caught.value.error.message


def test_the_page_total_counts_matches_not_rows() -> None:
    page = paginate_items(apply_transaction_filters(_mixed(), manual_only=True), limit=10)

    assert page["total_available"] == 1
    assert page["has_more"] is False
