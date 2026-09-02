"""Unit tests: tool titles and behavioural hints.

Titles are derived rather than written on each tool, so the derivation is what
needs pinning: it has to stay readable for every naming shape in the surface,
and it must not undo the readOnlyHint that each call site sets and the live
sweep depends on.
"""

from __future__ import annotations

import pytest
from mcp.types import ToolAnnotations

from mcp_server_for_ynab.server.registry import ToolMeta
from mcp_server_for_ynab.server.tools import presentation


def _meta(name: str, family: str, classification: str = "read") -> ToolMeta:
    return ToolMeta(
        name=name,
        family=family,
        classification=classification,  # type: ignore[arg-type]
        tool_type="raw",
        summary="",
    )


@pytest.mark.parametrize(
    ("name", "family", "expected"),
    [
        ("transactions_list", "transactions", "Transactions — List"),
        ("transactions_list_by_account", "transactions", "Transactions — List by account"),
        ("user_get", "user", "User — Get"),
        ("scheduled_transactions_delete", "scheduled_transactions", "Scheduled transactions — Delete"),
    ],
)
def test_titles_read_as_english(name: str, family: str, expected: str) -> None:
    assert presentation.tool_title(_meta(name, family)) == expected


@pytest.mark.parametrize(
    ("name", "family", "expected"),
    [
        # The family and the tool's own prefix disagree in each of these, and
        # trusting the family produces "Payees — Payee locations get".
        ("payee_locations_get", "payees", "Payee locations — Get"),
        ("category_groups_create", "categories", "Category groups — Create"),
        ("money_movement_groups_list", "money_movements", "Money movement groups — List"),
        ("overview_available_tools", "meta", "Overview — Available tools"),
    ],
)
def test_the_prefix_comes_from_the_name_not_the_family(name: str, family: str, expected: str) -> None:
    assert presentation.tool_title(_meta(name, family)) == expected


def test_an_unknown_prefix_still_produces_a_title() -> None:
    """A tool added in a new family must not fall back to a crash or a blank."""
    assert presentation.tool_title(_meta("widgets_frobnicate", "widgets")) == "Widgets — Frobnicate"


@pytest.mark.parametrize(
    "name",
    ["transactions_delete", "scheduled_transactions_delete", "accounts_create", "transactions_trigger_import"],
)
def test_operations_ynab_cannot_undo_are_marked_destructive(name: str) -> None:
    assert presentation.is_irreversible(name)


@pytest.mark.parametrize("name", ["transactions_update", "transactions_create", "categories_update_for_month"])
def test_journalled_writes_are_not_marked_destructive(name: str) -> None:
    """These are recoverable from the journal; flagging them would cry wolf."""
    assert not presentation.is_irreversible(name)


def test_read_only_hint_from_the_call_site_is_never_overwritten() -> None:
    existing = ToolAnnotations(readOnlyHint=True)
    result = presentation._annotate(existing, _meta("transactions_list", "transactions"), "T")

    assert result.readOnlyHint is True
    assert result.destructiveHint is False


def test_a_write_tool_keeps_its_read_only_false() -> None:
    existing = ToolAnnotations(readOnlyHint=False)
    result = presentation._annotate(existing, _meta("transactions_delete", "transactions", "write"), "T")

    assert result.readOnlyHint is False
    assert result.destructiveHint is True


def test_ynab_is_reported_as_a_closed_system() -> None:
    result = presentation._annotate(None, _meta("user_get", "user"), "T")
    assert result.openWorldHint is False


def test_a_changed_sdk_layout_does_not_crash_startup() -> None:
    """Titles are worth losing; a server that will not start is not."""

    class Unrecognised:
        _tool_manager = object()

    presentation.apply_presentation(Unrecognised())


def test_a_reversible_write_says_the_journal_can_undo_it() -> None:
    note = presentation.journal_note(_meta("transactions_update", "transactions", "write"))

    assert "history_revert" in note


def test_a_create_says_plainly_that_it_cannot_be_undone() -> None:
    note = presentation.journal_note(_meta("categories_create", "categories", "write"))

    assert "cannot be undone" in note


def test_a_delete_promises_recreation_not_restoration() -> None:
    """The journal can put a deleted transaction back, but with a new id and no
    import link. Calling that 'revertible' would overstate what happens."""
    note = presentation.journal_note(_meta("transactions_delete", "transactions", "write"))

    assert "new id" in note


def test_reads_get_no_journal_sentence() -> None:
    assert presentation.journal_note(_meta("transactions_list", "transactions")) == ""


def test_the_history_tools_are_not_told_to_revert_themselves() -> None:
    assert presentation.journal_note(_meta("history_revert", "history", "write")) == ""


def test_the_two_awkward_names_get_readable_titles() -> None:
    assert presentation.tool_title(_meta("money_move", "money_movements", "write")).startswith("Money — Move")
    assert presentation.tool_title(_meta("changes_since", "changes")) == "Changes — Since last check"
