"""FastMCP application factory.

Creates the single FastMCP instance and registers all tools against it.
Imported by the CLI entrypoint and by integration tests.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ynab_mcp.config import get_settings
from ynab_mcp.server.context import AppContext, set_app_context

mcp = FastMCP(
    name="ynab-mcp",
    instructions=(
        "AI-first MCP server for YNAB budget management. "
        "Start with overview_available_tools to see the full tool catalog. "
        "Use enriched tools (overview_*, triage_*, bookkeeping_*, analysis_*) for "
        "orientation and investigation. Use raw tools for precise reads and all writes. "
        "All amounts are in milliunits: 1000 = $1.00."
    ),
)


def create_app() -> FastMCP:
    """Initialize the application context and register all tools.

    Called once at startup. Safe to call multiple times — subsequent calls
    return the same FastMCP instance after re-initializing the context.
    """
    settings = get_settings()
    settings.configure_logging()
    ctx = AppContext.from_settings(settings)
    set_app_context(ctx)

    # Import tool registration modules — each module registers tools against `mcp`
    # when imported. Order determines the order tools appear in the catalog.
    from ynab_mcp.server.tools import (
        enriched,  # noqa: F401
        raw,  # noqa: F401
    )

    return mcp
