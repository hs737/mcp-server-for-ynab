"""Helpers for stateless MCP-side pagination."""

from __future__ import annotations

from typing import Any

from mcp_server_for_ynab.config.settings import ConfigError
from mcp_server_for_ynab.server.tools.projection import EMPTY_FIELDS_NOTE, project_item

DEFAULT_PAGE_LIMIT = 100
MAX_PAGE_LIMIT = 500


def _serialize_item(item: Any) -> Any:
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return item


def paginate_items(
    items: list[Any],
    *,
    limit: int = DEFAULT_PAGE_LIMIT,
    offset: int = 0,
    server_knowledge: int | None = None,
    fields: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Return a standard MCP pagination envelope for a list payload.

    Items are projected onto `fields` where given, and empty values are dropped
    either way — see `projection`. Only the page is projected, never the count:
    `total_available` still describes the whole filtered list.
    """
    if limit <= 0:
        raise ConfigError("limit must be a positive integer.")
    if limit > MAX_PAGE_LIMIT:
        raise ConfigError(f"limit must be less than or equal to {MAX_PAGE_LIMIT}.")
    if offset < 0:
        raise ConfigError("offset must be zero or greater.")

    total_available = len(items)
    page_items = [project_item(_serialize_item(item), fields) for item in items[offset : offset + limit]]
    count = len(page_items)
    has_more = offset + count < total_available

    payload: dict[str, Any] = {
        "items": page_items,
        "count": count,
        "offset": offset,
        "limit": limit,
        "total_available": total_available,
        "has_more": has_more,
    }

    if has_more:
        payload["next_offset"] = offset + count
    if server_knowledge is not None:
        payload["server_knowledge"] = server_knowledge
    if fields is not None:
        payload["fields"] = list(fields)
    if page_items and isinstance(page_items[0], dict):
        payload["item_note"] = EMPTY_FIELDS_NOTE

    return payload
