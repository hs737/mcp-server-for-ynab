"""Shared test fixtures."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from ynab_mcp.config.settings import reset_settings


@pytest.fixture(autouse=True)
def _reset_settings() -> None:
    """Reset the settings singleton between tests."""
    reset_settings()


@pytest.fixture
def ynab_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set minimum required env vars for Settings to initialize."""
    monkeypatch.setenv("YNAB_API_KEY", "test-pat-key-abc123")
    monkeypatch.delenv("YNAB_PLAN_ID", raising=False)


@pytest.fixture
def ynab_env_with_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set env vars including a default plan ID."""
    monkeypatch.setenv("YNAB_API_KEY", "test-pat-key-abc123")
    monkeypatch.setenv("YNAB_PLAN_ID", "plan-default-uuid")


def make_mock_ctx(**overrides: Any) -> MagicMock:
    """Build a minimal AppContext mock.

    Each ynab_client attribute is an AsyncMock so tests can control
    return values per-test without creating a real HTTP client.
    """
    ctx = MagicMock()
    ctx.settings.resolve_plan_id = lambda p: p or "plan-test-uuid"

    for attr in (
        "user",
        "plans",
        "accounts",
        "categories",
        "months",
        "payees",
        "transactions",
        "scheduled_transactions",
        "money_movements",
    ):
        client = MagicMock()
        for method in (
            "list",
            "get",
            "create",
            "update",
            "delete",
            "list_by_account",
            "list_by_category",
            "list_by_payee",
            "list_by_month",
            "bulk_update",
            "trigger_import",
            "list_groups",
            "list_by_month",
            "list_groups_by_month",
        ):
            setattr(client, method, AsyncMock())
        setattr(ctx, attr, client)

    for key, val in overrides.items():
        setattr(ctx, key, val)

    return ctx
