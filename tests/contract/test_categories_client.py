"""Contract tests: CategoriesClient routes and payloads.

Every assertion here corresponds to a way the category write tools failed
against the live API:

- create_group and update_group used a hyphen in the path segment, and YNAB
  answered "Invalid URI" for every call
- creating a category requires category_group_id, which the payload could not
  carry, so every create was rejected
- the create and update routes return a group without its categories, which the
  response model required
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from mcp_server_for_ynab.models.ynab.categories import (
    CategoryGroupResponse,
    SaveCategory,
    SaveCategoryGroup,
    SaveCategoryGroupWrapper,
    SaveCategoryWrapper,
)
from mcp_server_for_ynab.ynab_client.categories import CategoriesClient


def _group_response() -> dict[str, Any]:
    """A create/update group response: no categories key at all."""
    return {
        "data": {
            "category_group": {
                "id": "group-1",
                "name": "Sweep Group",
                "hidden": False,
                "internal": False,
                "deleted": False,
            },
            "server_knowledge": 48,
        }
    }


def _category_response() -> dict[str, Any]:
    return {
        "data": {
            "category": {
                "id": "cat-1",
                "category_group_id": "group-1",
                "category_group_name": "Sweep Group",
                "name": "Sweep Category",
                "hidden": False,
                "note": None,
                "budgeted": 0,
                "activity": 0,
                "balance": 0,
                "deleted": False,
            },
            "server_knowledge": 52,
        }
    }


def _client(response: dict[str, Any]) -> tuple[CategoriesClient, MagicMock]:
    http = MagicMock()
    http.post = AsyncMock(return_value=response)
    http.patch = AsyncMock(return_value=response)
    return CategoriesClient(http), http


async def test_create_group_uses_underscore_path() -> None:
    client, http = _client(_group_response())
    await client.create_group("plan-abc", SaveCategoryGroupWrapper(category_group=SaveCategoryGroup(name="G")))
    path = http.post.call_args.args[0]
    assert path == "/budgets/plan-abc/category_groups"
    assert "category-groups" not in path


async def test_update_group_uses_underscore_path() -> None:
    client, http = _client(_group_response())
    await client.update_group(
        "plan-abc",
        "group-1",
        SaveCategoryGroupWrapper(category_group=SaveCategoryGroup(name="G")),
    )
    path = http.patch.call_args.args[0]
    assert path == "/budgets/plan-abc/category_groups/group-1"
    assert "category-groups" not in path


async def test_group_response_parses_without_categories() -> None:
    """Create and update return the group alone; only the list route embeds categories."""
    parsed = CategoryGroupResponse.model_validate(_group_response())
    assert parsed.data.category_group.id == "group-1"
    assert parsed.data.category_group.categories == []


async def test_create_sends_category_group_id() -> None:
    client, http = _client(_category_response())
    payload = SaveCategoryWrapper(category=SaveCategory(name="Groceries", category_group_id="group-1"))
    await client.create("plan-abc", payload)
    body = http.post.call_args.kwargs["json"]
    assert body["category"]["category_group_id"] == "group-1"


async def test_update_for_month_targets_the_month_route() -> None:
    client, http = _client(
        {
            "data": {
                "category": _category_response()["data"]["category"],
                "server_knowledge": 1,
            }
        }
    )
    await client.update_for_month(
        "plan-abc",
        "2026-07-01",
        "cat-1",
        SaveCategoryWrapper(category=SaveCategory(budgeted=50000)),
    )
    assert http.patch.call_args.args[0] == "/budgets/plan-abc/months/2026-07-01/categories/cat-1"
    assert http.patch.call_args.kwargs["json"]["category"]["budgeted"] == 50000
