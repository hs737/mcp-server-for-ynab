"""MCP tools for reading write history and rolling it back."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.history import journal
from mcp_server_for_ynab.history.revert import RevertError, revert_entry, revert_to
from mcp_server_for_ynab.server.app import mcp
from mcp_server_for_ynab.server.context import get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler
from mcp_server_for_ynab.server.tools.registration import write_tool

tool_registry.register(
    "history_list", "history", "read", "enriched", "List recent writes, newest first, with revertibility."
)
tool_registry.register(
    "history_show", "history", "read", "enriched", "Show one history entry including its before and after state."
)
tool_registry.register("history_revert", "history", "write", "enriched", "Undo one journaled write. [WRITE]")
tool_registry.register(
    "history_revert_to", "history", "write", "enriched", "Roll the plan back to a point in history. [WRITE]"
)


@mcp.tool(
    name="history_list",
    description=(
        "[READ] List writes this server has made, newest first. Each entry says whether it can be "
        "reverted and how. Use this before history_revert or history_revert_to to choose an entry. "
        "Entries are recorded even when writes are later disabled, so history survives a restart."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def history_list(limit: int = 25, plan_id: str | None = None) -> dict[str, Any]:
    entries = journal.load()
    if plan_id:
        entries = [e for e in entries if e.plan_id == plan_id]

    newest_first = list(reversed(entries))
    window = newest_first[: max(1, min(limit, 200))]

    return {
        "scope": "history_list",
        "total_entries": len(entries),
        "returned": len(window),
        "revertible_count": sum(1 for e in window if e.revertible),
        "history_file": str(journal.history_path()),
        "entries": [e.summary() for e in window],
    }


@mcp.tool(
    name="history_show",
    description=(
        "[READ] Show one history entry in full, including the before and after state. "
        "The before state is what a revert would restore."
    ),
    annotations=ToolAnnotations(read_only_hint=True),
)
@tool_handler
async def history_show(entry_id: str) -> dict[str, Any]:
    entry = journal.get(entry_id)
    if entry is None:
        return {"error": {"error_type": "not_found", "message": f"No history entry with id {entry_id!r}."}}
    return {"scope": "history_show", **entry.detail()}


@write_tool(
    name="history_revert",
    description=(
        "[WRITE] Undo one journaled write, restoring the state recorded before it. "
        "Reverting is itself journaled, so it can be reverted in turn. "
        "Creating an account, category, category group, or payee cannot be undone — YNAB has no "
        "delete route for them — and attempting it returns an explanation rather than a partial change. "
        "A recreated transaction gets a new id and loses any bank-import link."
    ),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True),
)
@tool_handler
async def history_revert(entry_id: str) -> dict[str, Any]:
    ctx = get_app_context()
    entry = journal.get(entry_id)
    if entry is None:
        return {"error": {"error_type": "not_found", "message": f"No history entry with id {entry_id!r}."}}

    try:
        result = await revert_entry(ctx, entry)
    except RevertError as exc:
        return {"error": {"error_type": "validation_error", "message": str(exc)}}

    return {"scope": "history_revert", **result}


@write_tool(
    name="history_revert_to",
    description=(
        "[WRITE] Roll the plan back to its state at a given history entry, undoing everything "
        "after it, newest first. The named entry is kept — it is the state you want back. "
        "Pass plan_id to limit the rollback to one plan. "
        "Operations that cannot be undone are reported under 'blocked' rather than skipped silently, "
        "and 'complete' tells you whether the rollback fully succeeded. "
        "Call history_list first, and prefer reverting a few entries over a long rollback."
    ),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True),
)
@tool_handler
async def history_revert_to(entry_id: str, plan_id: str | None = None) -> dict[str, Any]:
    ctx = get_app_context()
    try:
        result = await revert_to(ctx, entry_id, plan_id=plan_id)
    except RevertError as exc:
        return {"error": {"error_type": "validation_error", "message": str(exc)}}
    return {"scope": "history_revert_to", **result}
