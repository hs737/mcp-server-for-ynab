"""Integration tests: MCP tool error boundary.

These tests call tool handler functions directly (not through the MCP
transport) to verify that the @tool_handler decorator correctly converts
YnabMcpException, ConfigError, and unexpected exceptions into structured
{"error": YnabMcpError} dicts instead of letting raw exceptions propagate.

Each test patches get_app_context at the tool module level — the correct
target for functions that use `from ynab_mcp.server.context import get_app_context`.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ynab_mcp.models.errors import ErrorType, YnabMcpError, YnabMcpException


@pytest.fixture(autouse=True)
def _setup_app(ynab_env: None) -> None:
    """Initialize the app so all tool modules are imported and registered."""
    from ynab_mcp.server.app import create_app

    create_app()


# ---------------------------------------------------------------------------
# Missing plan_id → ConfigError → validation_error
# ---------------------------------------------------------------------------


async def test_missing_plan_id_returns_validation_error(ynab_env: None) -> None:
    """accounts_list with no plan_id and no YNAB_PLAN_ID returns a validation_error dict."""
    from ynab_mcp.server.tools.raw.accounts import accounts_list

    # ynab_env fixture does not set YNAB_PLAN_ID — resolve_plan_id raises ConfigError
    result = await accounts_list(plan_id=None)

    assert "error" in result
    err = result["error"]
    assert err["error_type"] == ErrorType.VALIDATION_ERROR
    assert err["message"]


async def test_missing_plan_id_on_enriched_tool_returns_validation_error(ynab_env: None) -> None:
    """Enriched tools are also wrapped and return validation_error when plan_id is absent."""
    from ynab_mcp.server.tools.enriched import overview_budget_snapshot_tool

    result = await overview_budget_snapshot_tool(plan_id=None)

    assert "error" in result
    assert result["error"]["error_type"] == ErrorType.VALIDATION_ERROR


# ---------------------------------------------------------------------------
# YnabMcpException from the YNAB client → structured error dict
# ---------------------------------------------------------------------------


async def test_auth_failure_returns_structured_error(ynab_env: None) -> None:
    mock_ctx = MagicMock()
    mock_ctx.plans.list = AsyncMock(side_effect=YnabMcpException(YnabMcpError.auth_failure("Token expired")))

    from ynab_mcp.server.tools.raw.plans import plans_list

    with patch("ynab_mcp.server.tools.raw.plans.get_app_context", return_value=mock_ctx):
        result = await plans_list()

    assert "error" in result
    err = result["error"]
    assert err["error_type"] == ErrorType.AUTH_FAILURE
    assert err["status_code"] == 401


async def test_not_found_returns_structured_error(ynab_env: None) -> None:
    mock_ctx = MagicMock()
    mock_ctx.settings.resolve_plan_id = MagicMock(return_value="plan-123")
    mock_ctx.accounts.get = AsyncMock(side_effect=YnabMcpException(YnabMcpError.not_found("account")))

    from ynab_mcp.server.tools.raw.accounts import accounts_get

    with patch("ynab_mcp.server.tools.raw.accounts.get_app_context", return_value=mock_ctx):
        result = await accounts_get(account_id="nonexistent", plan_id="plan-123")

    assert result["error"]["error_type"] == ErrorType.NOT_FOUND
    assert result["error"]["status_code"] == 404


async def test_rate_limited_preserves_retry_after(ynab_env: None) -> None:
    mock_ctx = MagicMock()
    mock_ctx.plans.list = AsyncMock(side_effect=YnabMcpException(YnabMcpError.rate_limited(retry_after=30)))

    from ynab_mcp.server.tools.raw.plans import plans_list

    with patch("ynab_mcp.server.tools.raw.plans.get_app_context", return_value=mock_ctx):
        result = await plans_list()

    err = result["error"]
    assert err["error_type"] == ErrorType.RATE_LIMITED
    assert err["retry_after"] == 30


# ---------------------------------------------------------------------------
# Unexpected exception → internal_error
# ---------------------------------------------------------------------------


async def test_unexpected_exception_returns_internal_error(ynab_env: None) -> None:
    mock_ctx = MagicMock()
    mock_ctx.plans.list = AsyncMock(side_effect=RuntimeError("DB exploded"))

    from ynab_mcp.server.tools.raw.plans import plans_list

    with patch("ynab_mcp.server.tools.raw.plans.get_app_context", return_value=mock_ctx):
        result = await plans_list()

    assert "error" in result
    err = result["error"]
    assert err["error_type"] == ErrorType.INTERNAL_ERROR
    assert "plans_list" in err["message"]


# ---------------------------------------------------------------------------
# Success path — no error key
# ---------------------------------------------------------------------------


async def test_success_returns_data_without_error_key(ynab_env: None) -> None:
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"budgets": [{"id": "abc", "name": "Test"}]}
    mock_ctx = MagicMock()
    mock_ctx.plans.list = AsyncMock(return_value=mock_result)

    from ynab_mcp.server.tools.raw.plans import plans_list

    with patch("ynab_mcp.server.tools.raw.plans.get_app_context", return_value=mock_ctx):
        result = await plans_list()

    assert "error" not in result
    assert result == {"budgets": [{"id": "abc", "name": "Test"}]}


async def test_success_with_default_plan_id(ynab_env: None) -> None:
    """When plan_id is resolved via mock, the tool succeeds without error."""
    mock_result = MagicMock()
    mock_result.model_dump.return_value = {"accounts": []}
    mock_ctx = MagicMock()
    mock_ctx.settings.resolve_plan_id = MagicMock(return_value="plan-default-uuid")
    mock_ctx.accounts.list = AsyncMock(return_value=mock_result)

    from ynab_mcp.server.tools.raw.accounts import accounts_list

    with patch("ynab_mcp.server.tools.raw.accounts.get_app_context", return_value=mock_ctx):
        result = await accounts_list(plan_id=None)

    assert "error" not in result
    assert result == {"accounts": []}
