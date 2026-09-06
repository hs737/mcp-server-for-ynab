"""Unit tests: projecting list items down to what was asked for."""

from __future__ import annotations

import pytest

from mcp_server_for_ynab.models.errors import YnabMcpException
from mcp_server_for_ynab.server.tools.projection import project_item, strip_empty, validate_fields

FIELDS = ("id", "date", "amount", "memo", "payee_name", "subtransactions")


def test_requested_fields_always_carry_the_id() -> None:
    """A row you cannot then act on is not worth returning."""
    assert validate_fields(["date", "amount"], FIELDS) == ("id", "date", "amount")


def test_an_unknown_field_is_refused_and_the_valid_ones_are_named() -> None:
    with pytest.raises(YnabMcpException) as excinfo:
        validate_fields(["date", "payee"], FIELDS)

    message = excinfo.value.error.message
    assert "payee" in message
    assert "payee_name" in message


def test_no_fields_means_no_projection() -> None:
    assert validate_fields(None, FIELDS) is None
    assert validate_fields([], FIELDS) is None
    assert validate_fields([" "], FIELDS) is None


def test_empty_members_are_dropped_at_every_level() -> None:
    item = {
        "id": "t1",
        "memo": None,
        "subtransactions": [{"id": "s1", "payee_name": None, "amount": -500}],
        "flag_color": None,
        "amount": -1000,
    }

    assert strip_empty(item) == {
        "id": "t1",
        "subtransactions": [{"id": "s1", "amount": -500}],
        "amount": -1000,
    }


def test_a_zero_is_not_an_empty_value() -> None:
    """Dropping a zero amount would change what the row says."""
    assert strip_empty({"amount": 0, "approved": False}) == {"amount": 0, "approved": False}


def test_projection_leaves_non_dict_items_alone() -> None:
    assert project_item(42, ("id",)) == 42
