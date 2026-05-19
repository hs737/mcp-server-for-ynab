"""Raw MCP tools: user resource."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ynab_mcp.server.app import mcp
from ynab_mcp.server.context import get_app_context
from ynab_mcp.server.registry import tool_registry
from ynab_mcp.server.tools.boundary import tool_handler


def _reg(name: str, summary: str) -> None:
    tool_registry.register(name, "user", "read", "raw", summary)


_reg("user_get", "Get the authenticated YNAB user.")


@mcp.tool(
    name="user_get",
    description="[READ] Get the authenticated YNAB user. Returns the user ID.",
    annotations=ToolAnnotations(readOnlyHint=True),
)
@tool_handler
async def user_get() -> dict[str, Any]:
    ctx = get_app_context()
    result = await ctx.user.get()
    return result.model_dump()
