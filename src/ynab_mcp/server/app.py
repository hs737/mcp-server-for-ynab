"""FastMCP application factory.

Creates the single FastMCP instance and registers all tools against it.
Imported by the CLI entrypoint and by integration tests.

SDK note: FastMCP ships inside the official Anthropic `mcp` package (>=1.0).
The import path `mcp.server.fastmcp` is the correct, locked path — this is NOT
the standalone `fastmcp` PyPI package. pyproject.toml pins `mcp>=1.27.1`.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from mcp.server.fastmcp import FastMCP

from ynab_mcp.config import get_settings
from ynab_mcp.server.context import AppContext, set_app_context


def package_version() -> str:
    """Return this package's version, as clients see it during initialize."""
    try:
        return version("ynab-mcp")
    except PackageNotFoundError:  # running from a source tree without an install
        return "0.0.0+unknown"


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

# FastMCP takes no version argument, and the low-level server falls back to the
# mcp SDK's own version when its version is unset — so without this, initialize
# reports the SDK version as the server's version. Assigning it here is the only
# hook the SDK offers.
mcp._mcp_server.version = package_version()


def _register_tools() -> None:
    """Import tool modules so they register themselves against the shared app."""
    from ynab_mcp.server.tools import (
        enriched,  # noqa: F401
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
