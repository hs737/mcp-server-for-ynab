"""Contract tests: TransactionsClient against a mock HTTP layer."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from ynab_mcp.ynab_client.transactions import TransactionsClient


def _make_client(response_data: dict[str, Any]) -> TransactionsClient:
    http = MagicMock()
    http.get = AsyncMock(return_value=response_data)
    http.post = AsyncMock(return_value=response_data)
    http.put = AsyncMock(return_value=response_data)
    http.patch = AsyncMock(return_value=response_data)
    http.delete = AsyncMock(return_value=response_data)
    return TransactionsClient(http)


def _transactions_list_response(**extra: Any) -> dict[str, Any]:
    return {
        "data": {
            "transactions": [
                {
                    "id": "txn-1",
                    "date": "2024-01-15",
                    "amount": -25000,
                    "memo": None,
                    "cleared": "cleared",
                    "approved": True,
                    "flag_color": None,
                    "flag_name": None,
                    "account_id": "acct-1",
                    "account_name": "Checking",
                    "payee_id": "payee-1",
                    "payee_name": "Grocery Store",
                    "category_id": "cat-1",
                    "category_name": "Groceries",
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
            ],
            "server_knowledge": 1234,
            **extra,
        }
    }


async def test_list_returns_transactions() -> None:
    client = _make_client(_transactions_list_response())
    result = await client.list("plan-abc")
    assert len(result.data.transactions) == 1
    assert result.data.transactions[0].id == "txn-1"
    assert result.data.transactions[0].amount == -25000


async def test_list_passes_since_date() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_transactions_list_response())
    client = TransactionsClient(http)
    await client.list("plan-abc", since_date="2024-01-01")
    call_kwargs = http.get.call_args
    assert call_kwargs.kwargs["params"]["since_date"] == "2024-01-01"


async def test_list_passes_type_filter() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_transactions_list_response())
    client = TransactionsClient(http)
    await client.list("plan-abc", type="uncategorized")
    call_kwargs = http.get.call_args
    assert call_kwargs.kwargs["params"]["type"] == "uncategorized"


async def test_list_passes_delta_sync() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_transactions_list_response())
    client = TransactionsClient(http)
    await client.list("plan-abc", last_knowledge_of_server=500)
    call_kwargs = http.get.call_args
    assert call_kwargs.kwargs["params"]["last_knowledge_of_server"] == 500


async def test_list_no_params_when_not_set() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_transactions_list_response())
    client = TransactionsClient(http)
    await client.list("plan-abc")
    call_kwargs = http.get.call_args
    assert call_kwargs.kwargs.get("params") is None


async def test_server_knowledge_preserved() -> None:
    client = _make_client(_transactions_list_response())
    result = await client.list("plan-abc")
    assert result.data.server_knowledge == 1234


async def test_list_by_account_url() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=_transactions_list_response())
    client = TransactionsClient(http)
    await client.list_by_account("plan-abc", "acct-xyz")
    path = http.get.call_args.args[0]
    assert "accounts/acct-xyz" in path
