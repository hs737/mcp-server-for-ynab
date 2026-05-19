from __future__ import annotations

import pytest

from ynab_mcp.config.settings import ConfigError
from ynab_mcp.server.tools.pagination import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, paginate_items


def test_paginate_items_uses_defaults() -> None:
    result = paginate_items(list(range(135)), server_knowledge=42)

    assert result["count"] == DEFAULT_PAGE_LIMIT
    assert result["offset"] == 0
    assert result["limit"] == DEFAULT_PAGE_LIMIT
    assert result["total_available"] == 135
    assert result["has_more"] is True
    assert result["next_offset"] == DEFAULT_PAGE_LIMIT
    assert result["server_knowledge"] == 42
    assert result["items"][0] == 0
    assert result["items"][-1] == DEFAULT_PAGE_LIMIT - 1


def test_paginate_items_handles_final_partial_page() -> None:
    result = paginate_items(list(range(25)), limit=10, offset=20)

    assert result == {
        "items": [20, 21, 22, 23, 24],
        "count": 5,
        "offset": 20,
        "limit": 10,
        "total_available": 25,
        "has_more": False,
    }


def test_paginate_items_handles_empty_list() -> None:
    result = paginate_items([], limit=10, offset=0)

    assert result == {
        "items": [],
        "count": 0,
        "offset": 0,
        "limit": 10,
        "total_available": 0,
        "has_more": False,
    }


def test_paginate_items_allows_offset_past_end() -> None:
    result = paginate_items([1, 2, 3], limit=10, offset=50)

    assert result == {
        "items": [],
        "count": 0,
        "offset": 50,
        "limit": 10,
        "total_available": 3,
        "has_more": False,
    }


@pytest.mark.parametrize(
    ("limit", "offset", "message"),
    [
        (0, 0, "limit must be a positive integer."),
        (-1, 0, "limit must be a positive integer."),
        (MAX_PAGE_LIMIT + 1, 0, f"limit must be less than or equal to {MAX_PAGE_LIMIT}."),
        (10, -1, "offset must be zero or greater."),
    ],
)
def test_paginate_items_validates_inputs(limit: int, offset: int, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        paginate_items([1, 2, 3], limit=limit, offset=offset)
