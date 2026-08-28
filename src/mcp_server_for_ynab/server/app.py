"""FastMCP application factory.

Creates the single FastMCP instance and registers all tools against it.
Imported by the CLI entrypoint and by integration tests.

SDK note: FastMCP ships inside the official Anthropic `mcp` package (>=1.0).
The import path `mcp.server.fastmcp` is the correct, locked path — this is NOT
the standalone `fastmcp` PyPI package. pyproject.toml pins `mcp>=1.28.1,<2`.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_server_for_ynab import package_version
from mcp_server_for_ynab.config import get_settings
from mcp_server_for_ynab.server.context import AppContext, set_app_context

__all__ = ["create_app", "create_embedded_app", "mcp", "package_version"]

mcp = FastMCP(
    # YNAB's OAuth application requirements: an application name may not include
    # "YNAB" unless the word is preceded by "for". Keep this compliant.
    name="mcp-for-ynab",
    instructions=(
        "AI-first MCP server for YNAB budget management. "
        "Start with overview_available_tools to see the full tool catalog. "
        "Use enriched tools (overview_*, triage_*, bookkeeping_*, analysis_*) for "
        "orientation and investigation. Use raw tools for precise reads and all writes. "
        "All amounts are in milliunits: 1000 = $1.00."
    ),
)

# FastMCP takes no version argument, and the low-level server falls back to the
# mcp SDK's own version when its version is unset — so without this, initialize
# reports the SDK version as the server's version. Assigning it here is the only
# hook the SDK offers.
mcp._mcp_server.version = package_version()


def _register_tools() -> None:
    """Import tool modules so they register themselves against the shared app."""
    from mcp_server_for_ynab.server.tools import (
        enriched,  # noqa: F401
        history,  # noqa: F401
        raw,  # noqa: F401
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
    _register_tools()

    return mcp


def create_embedded_app() -> FastMCP:
    """Return the shared FastMCP app for hosted runtimes that inject auth."""
    _register_tools()

    return mcp
