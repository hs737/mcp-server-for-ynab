from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from tests.conftest import make_mock_ctx
from ynab_mcp.models.errors import ErrorType
from ynab_mcp.models.ynab.transactions import TransactionsResponse


def _transaction(idx: int, *, with_subtransaction: bool = False) -> dict[str, Any]:
    transaction = {
        "id": f"txn-{idx}",
        "date": "2026-05-01",
        "amount": -1000 - idx,
        "memo": f"memo-{idx}",
        "cleared": "cleared",
        "approved": True,
        "flag_color": None,
        "flag_name": None,
        "account_id": "account-1",
        "account_name": "Checking",
        "payee_id": "payee-1",
        "payee_name": "Payee",
        "category_id": "category-1",
        "category_name": "Category",
        "transfer_account_id": None,
        "transfer_transaction_id": None,
        "matched_transaction_id": None,
        "import_id": None,
        "import_payee_name": None,
        "import_payee_name_original": None,
        "debt_transaction_type": None,
        "deleted": False,
        "subtransactions": [],
    }
    if with_subtransaction:
        transaction["subtransactions"] = [
            {
                "id": f"sub-{idx}",
                "transaction_id": f"txn-{idx}",
                "amount": -500,
                "memo": "split",
                "payee_id": None,
                "payee_name": None,
                "category_id": "category-2",
                "category_name": "Split",
                "transfer_account_id": None,
                "transfer_transaction_id": None,
                "deleted": False,
            }
        ]
    return transaction


def _transactions_response(total: int) -> TransactionsResponse:
    return TransactionsResponse.model_validate(
        {
            "data": {
                "transactions": [_transaction(idx, with_subtransaction=(idx == 0)) for idx in range(total)],
                "server_knowledge": 1234,
            }
        }
    )


@pytest.fixture(autouse=True)
def _setup_app(ynab_env: None) -> None:
    from ynab_mcp.server.app import create_app

    create_app()


async def test_transactions_list_returns_paginated_envelope(ynab_env: None) -> None:
    mock_ctx = make_mock_ctx()
    mock_ctx.transactions.list.return_value = _transactions_response(135)

    from ynab_mcp.server.tools.raw.transactions import transactions_list

    with patch("ynab_mcp.server.tools.raw.transactions.get_app_context", return_value=mock_ctx):
        result = await transactions_list(plan_id="plan-123")

    assert "error" not in result
    assert result["count"] == 100
    assert result["offset"] == 0
    assert result["limit"] == 100
    assert result["total_available"] == 135
    assert result["has_more"] is True
    assert result["next_offset"] == 100
    assert result["server_knowledge"] == 1234
    assert len(result["items"]) == 100
    assert result["items"][0]["subtransactions"][0]["id"] == "sub-0"


async def test_transactions_list_supports_follow_up_pages(ynab_env: None) -> None:
    mock_ctx = make_mock_ctx()
    mock_ctx.transactions.list.return_value = _transactions_response(135)

    from ynab_mcp.server.tools.raw.transactions import transactions_list

    with patch("ynab_mcp.server.tools.raw.transactions.get_app_context", return_value=mock_ctx):
        result = await transactions_list(plan_id="plan-123", limit=25, offset=125)

    assert result == {
        "items": [_transaction(idx) for idx in range(125, 135)],
        "count": 10,
        "offset": 125,
        "limit": 25,
        "total_available": 135,
        "has_more": False,
        "server_knowledge": 1234,
    }


async def test_transactions_list_by_account_passes_filters_and_paginates(ynab_env: None) -> None:
    mock_ctx = make_mock_ctx()
    mock_ctx.transactions.list_by_account.return_value = _transactions_response(3)

    from ynab_mcp.server.tools.raw.transactions import transactions_list_by_account

    with patch("ynab_mcp.server.tools.raw.transactions.get_app_context", return_value=mock_ctx):
        result = await transactions_list_by_account(
            account_id="account-123",
            plan_id="plan-123",
            since_date="2026-05-01",
            type="uncategorized",
            last_knowledge_of_server=7,
            limit=2,
            offset=1,
        )

    mock_ctx.transactions.list_by_account.assert_awaited_once_with(
        "plan-123",
        "account-123",
        since_date="2026-05-01",
        type="uncategorized",
        last_knowledge_of_server=7,
    )
    assert [item["id"] for item in result["items"]] == ["txn-1", "txn-2"]
    assert result["count"] == 2
    assert result["offset"] == 1
    assert result["limit"] == 2
    assert result["has_more"] is False


async def test_invalid_limit_returns_validation_error(ynab_env: None) -> None:
    mock_ctx = make_mock_ctx()
    mock_ctx.transactions.list.return_value = _transactions_response(3)

    from ynab_mcp.server.tools.raw.transactions import transactions_list

    with patch("ynab_mcp.server.tools.raw.transactions.get_app_context", return_value=mock_ctx):
        result = await transactions_list(plan_id="plan-123", limit=0)

    assert result["error"]["error_type"] == ErrorType.VALIDATION_ERROR
    assert "limit must be a positive integer" in result["error"]["message"]
