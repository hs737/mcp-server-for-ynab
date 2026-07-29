"""Integration tests: server startup and tool registration."""

from __future__ import annotations

import pytest

from mcp_server_for_ynab.server.registry import tool_registry


@pytest.fixture(autouse=True)
def _setup_app(ynab_env: None) -> None:
    """Initialize the full app so all tools get registered."""
    from mcp_server_for_ynab.server.app import create_app

    create_app()


def test_app_creates_without_error(ynab_env: None) -> None:
    from mcp_server_for_ynab.server.app import create_app, mcp

    create_app()
    assert mcp is not None


def test_registry_has_enriched_tools() -> None:
    names = {t.name for t in tool_registry.all()}
    assert "overview_available_tools" in names
    assert "overview_budget_snapshot" in names
    assert "triage_uncategorized" in names
    assert "analysis_upcoming_scheduled_risks" in names


def test_registry_has_raw_read_tools() -> None:
    names = {t.name for t in tool_registry.all()}
    assert "transactions_list" in names
    assert "categories_list" in names
    assert "scheduled_transactions_list" in names


def test_registry_tool_count_is_reasonable() -> None:
    total = len(tool_registry.all())
    assert total >= 40, f"Expected >= 40 tools, got {total}"


def test_registry_families_present() -> None:
    families = set(tool_registry.by_family().keys())
    expected = {
        "meta",
        "overview",
        "triage",
        "bookkeeping",
        "analysis",
        "transactions",
        "categories",
        "accounts",
        "months",
        "payees",
        "scheduled_transactions",
        "money_movements",
        "plans",
    }
    missing = expected - families
    assert not missing, f"Missing families: {missing}"


def test_all_enriched_tools_are_read_only() -> None:
    enriched = [t for t in tool_registry.all() if t.tool_type == "enriched"]
    non_read = [t.name for t in enriched if t.classification != "read"]
    assert not non_read, f"Enriched tools should all be read: {non_read}"


def test_no_write_tools_are_registered_by_default() -> None:
    """Read-only is the default, and the test suite runs without the opt-in.

    Write tools are gated at import time, so this asserts the state of a server
    a user gets when they have not set YNAB_ALLOW_WRITES: the write tools are
    absent from the catalog, not merely refused when called.
    """
    writes = [t.name for t in tool_registry.all() if t.classification == "write"]
    assert writes == []
