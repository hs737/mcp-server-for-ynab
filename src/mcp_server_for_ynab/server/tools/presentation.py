"""Titles and behavioural hints, applied to every registered tool at startup.

Clients render `title` in tool lists and permission dialogs, and fall back to
the raw tool name when it is unset. `transactions_list_by_account` is a
serviceable identifier and a poor thing to show someone deciding whether to
approve a call against their bank data.

These are derived rather than hand-written on each of the ~60 tools. A title
argument on every decorator is another copy of a fact the registry already
holds, and the copy that gets forgotten is the one on the tool added last.
Deriving them means a new tool is titled and hinted correctly for free.

The hints matter more than the titles. `readOnlyHint` is already set at each
call site and is load-bearing — the live sweep selects read tools by it — so it
is never overwritten here. What is missing is `destructiveHint`: a client that
treats "update a transaction" and "delete a transaction" identically cannot
warn proportionally, and only one of those is unrecoverable through this
server.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.server.registry import ToolMeta, tool_registry

logger = logging.getLogger(__name__)

# Words that naive capitalisation gets wrong.
_ACTION_WORDS = {"id": "ID", "csv": "CSV", "url": "URL"}

# The displayed prefix comes from the tool name, not the registry family,
# because several tools sit in a family whose name they do not carry:
# payee_locations_get lives in the payees family, and titling it
# "Payees — Payee locations get" says payee twice. Longest match wins, so
# money_movement_groups_list resolves to the group prefix rather than to
# money_movements.
_NAME_PREFIXES = (
    "money_movement_groups",
    "money_movements",
    "scheduled_transactions",
    "payee_locations",
    "category_groups",
    "transactions",
    "bookkeeping",
    "categories",
    "accounts",
    "analysis",
    "overview",
    "history",
    "payees",
    "months",
    "triage",
    "plans",
    "user",
)


def _humanize(segment: str) -> str:
    words = [_ACTION_WORDS.get(word, word) for word in segment.split("_")]
    first, *rest = words
    return " ".join([first.capitalize() if first.islower() else first, *rest])


def _split_name(name: str) -> tuple[str, str]:
    """Return (prefix, action) for a tool name, longest known prefix first."""
    for prefix in _NAME_PREFIXES:
        if name == prefix:
            return prefix, "overview"
        if name.startswith(f"{prefix}_"):
            return prefix, name[len(prefix) + 1 :]
    head, _, tail = name.partition("_")
    return head, tail or "overview"


def tool_title(meta: ToolMeta) -> str:
    """A human-readable label, e.g. "Transactions — List by account"."""
    prefix, action = _split_name(meta.name)
    return f"{_humanize(prefix)} — {_humanize(action)}"


# YNAB has no undo for these and this server cannot compensate: creating an
# account, category, group or payee is permanent, a delete removes data the API
# will not hand back, and YNAB owns imported transactions once an import runs.
# Everything else a write tool does is recoverable from the journal, so marking
# it destructive would cry wolf and train people to click through the warning.
_IRREVERSIBLE_SUFFIXES = ("_delete",)
_IRREVERSIBLE_NAMES = frozenset(
    {
        "accounts_create",
        "categories_create",
        "category_groups_create",
        "payees_create",
        "transactions_trigger_import",
    }
)


def is_irreversible(name: str) -> bool:
    return name in _IRREVERSIBLE_NAMES or name.endswith(_IRREVERSIBLE_SUFFIXES)


def _annotate(existing: ToolAnnotations | None, meta: ToolMeta, title: str) -> ToolAnnotations:
    read_only = existing.readOnlyHint if existing else None
    if read_only is None:
        read_only = meta.classification == "read"

    return ToolAnnotations(
        title=title,
        readOnlyHint=read_only,
        # A read never destroys anything, so state that rather than leaving it
        # unknown; for writes, only the genuinely unrecoverable ones say true.
        destructiveHint=False if read_only else is_irreversible(meta.name),
        idempotentHint=existing.idempotentHint if existing else None,
        # YNAB is a closed, bounded system: the tools reach one API the user
        # already owns, not the open internet.
        openWorldHint=False,
    )


def apply_presentation(mcp: Any) -> None:
    """Project registry metadata onto the tools FastMCP has registered.

    FastMCP exposes no public hook for amending a tool after registration, so
    this reaches into its tool manager. If a future SDK moves that, titles are
    worth losing but a crash at startup is not — the server still works without
    them, so this degrades quietly and says so in the log.
    """
    tools = getattr(getattr(mcp, "_tool_manager", None), "_tools", None)
    if not isinstance(tools, dict):
        logger.debug("Tool presentation skipped: FastMCP tool manager layout not recognised.")
        return

    for name, tool in tools.items():
        meta = tool_registry.get(name)
        if meta is None:
            continue

        title = tool_title(meta)
        try:
            tool.title = title
            tool.annotations = _annotate(tool.annotations, meta, title)
        except (AttributeError, ValueError):  # pragma: no cover - SDK shape change
            logger.debug("Tool presentation skipped for %s.", name)
            return
