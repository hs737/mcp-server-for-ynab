"""Contract tests: MoneyMovementsClient against a mock HTTP layer.

The payloads here come from tests/fixtures, recorded from live YNAB responses.
An earlier version of these models was written by analogy with transactions —
it required `date` on a movement and `name`/`amount` on a group, none of which
the API sends — and every money movement tool failed at validation. Keep these
tests fixture-driven so that class of drift fails here first.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from mcp_server_for_ynab.models.ynab.money_movements import MoneyMovementsResponse
from mcp_server_for_ynab.ynab_client.money_movements import MoneyMovementsClient
from tests.conftest import load_fixture

MOVEMENTS = load_fixture("money_movements_list.json")
GROUPS = load_fixture("money_movement_groups_list.json")


def _make_client(response_data: dict[str, Any]) -> tuple[MoneyMovementsClient, MagicMock]:
    http = MagicMock()
    http.get = AsyncMock(return_value=response_data)
    return MoneyMovementsClient(http), http


async def test_list_parses_live_payload_shape() -> None:
    client, _ = _make_client(MOVEMENTS)
    result = await client.list("plan-abc")

    assert len(result.data.money_movements) == 3
    first = result.data.money_movements[0]
    assert first.id == "mm-1"
    assert first.month == "2026-06-01"
    assert first.moved_at == "2026-06-13T14:39:50Z"
    assert first.amount == 500000
    assert first.amount_formatted == "$500.00"
    assert first.amount_currency == 500.0
    assert first.performed_by_user_id == "user-1"
    assert first.deleted is False


async def test_null_category_endpoints_mean_ready_to_assign() -> None:
    client, _ = _make_client(MOVEMENTS)
    result = await client.list("plan-abc")
    movements = result.data.money_movements

    # Funds arriving from Ready to Assign.
    assert movements[0].from_category_id is None
    assert movements[0].to_category_id == "cat-groceries"
    # Funds returning to Ready to Assign.
    assert movements[2].from_category_id == "cat-dining"
    assert movements[2].to_category_id is None


async def test_group_membership_is_optional() -> None:
    client, _ = _make_client(MOVEMENTS)
    result = await client.list("plan-abc")
    movements = result.data.money_movements

    assert movements[0].money_movement_group_id is None
    assert movements[1].money_movement_group_id == "mmg-1"


async def test_negative_amounts_are_preserved() -> None:
    client, _ = _make_client(MOVEMENTS)
    result = await client.list("plan-abc")
    assert result.data.money_movements[1].amount == -35000
    assert result.data.money_movements[1].amount_currency == -35.0


async def test_note_is_optional() -> None:
    client, _ = _make_client(MOVEMENTS)
    result = await client.list("plan-abc")
    assert result.data.money_movements[0].note is None
    assert result.data.money_movements[1].note == "covering the overspend"


async def test_movement_rejects_transaction_shaped_payload() -> None:
    """A transaction-shaped record must not validate as a money movement."""
    payload = {
        "data": {
            "money_movements": [
                {
                    "id": "txn-1",
                    "date": "2024-01-15",
                    "amount": -25000,
                    "payee_name": "Grocery Store",
                    "account_name": "Checking",
                }
            ],
            "server_knowledge": 1,
        }
    }
    with pytest.raises(ValidationError):
        MoneyMovementsResponse.model_validate(payload)


async def test_groups_parse_live_payload_shape() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=GROUPS)
    client = MoneyMovementsClient(http)

    result = await client.list_groups("plan-abc")

    assert len(result.data.money_movement_groups) == 2
    first = result.data.money_movement_groups[0]
    assert first.id == "mmg-1"
    assert first.month == "2025-02-01"
    assert first.group_created_at == "2025-01-29T11:30:44Z"
    assert first.note is None
    assert first.deleted is False


async def test_server_knowledge_preserved() -> None:
    client, _ = _make_client(MOVEMENTS)
    result = await client.list("plan-abc")
    assert result.data.server_knowledge == 33730


async def test_list_url() -> None:
    client, http = _make_client(MOVEMENTS)
    await client.list("plan-abc")
    assert http.get.call_args.args[0] == "/budgets/plan-abc/money_movements"


async def test_list_by_month_url() -> None:
    client, http = _make_client(MOVEMENTS)
    await client.list_by_month("plan-abc", "2026-07-01")
    assert http.get.call_args.args[0] == "/budgets/plan-abc/months/2026-07-01/money_movements"


async def test_list_groups_url() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=GROUPS)
    client = MoneyMovementsClient(http)
    await client.list_groups("plan-abc")
    assert http.get.call_args.args[0] == "/budgets/plan-abc/money_movement_groups"


async def test_list_groups_by_month_url() -> None:
    http = MagicMock()
    http.get = AsyncMock(return_value=GROUPS)
    client = MoneyMovementsClient(http)
    await client.list_groups_by_month("plan-abc", "2026-07-01")
    assert http.get.call_args.args[0] == "/budgets/plan-abc/months/2026-07-01/money_movement_groups"


async def test_list_passes_delta_sync() -> None:
    client, http = _make_client(MOVEMENTS)
    await client.list("plan-abc", last_knowledge_of_server=500)
    assert http.get.call_args.kwargs["params"]["last_knowledge_of_server"] == 500


async def test_list_no_params_when_not_set() -> None:
    client, http = _make_client(MOVEMENTS)
    await client.list("plan-abc")
    assert http.get.call_args.kwargs.get("params") is None
