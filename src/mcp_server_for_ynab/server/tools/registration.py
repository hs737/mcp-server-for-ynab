"""Tool registration helpers.

Read tools register with `@mcp.tool(...)` directly. Write tools must go through
`@write_tool(...)`, which registers them only when writes are enabled.

The difference matters: a disabled write tool never reaches FastMCP, so it does
not appear in tools/list and an agent has no way to invoke it. Refusing a call
at execution time would still advertise the capability and still depend on the
refusal being correct every time.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mcp_server_for_ynab.config.settings import writes_enabled
from mcp_server_for_ynab.server.app import mcp


def write_tool(**kwargs: Any) -> Callable[[Any], Any]:
    """Register a write tool, or skip registration when writes are disabled."""
    if not writes_enabled():

        def skip(fn: Any) -> Any:
            return fn

        return skip

    registered: Callable[[Any], Any] = mcp.tool(**kwargs)
    return registered
