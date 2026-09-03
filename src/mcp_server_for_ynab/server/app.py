"""MCPServer application factory.

Creates the single MCPServer instance and registers all tools against it.
Imported by the CLI entrypoint and by integration tests.

SDK note: MCPServer ships inside the official Anthropic `mcp` package, and is
what v1 called FastMCP — renamed in mcp 2.0. The import path
`mcp.server.mcpserver` is the correct, locked path; this is NOT the standalone
`fastmcp` PyPI package. pyproject.toml pins `mcp>=2.1.1,<3`, and the floor is
2.x because `mcp.server.fastmcp` no longer exists.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from mcp_server_for_ynab import package_version
from mcp_server_for_ynab.config import get_settings
from mcp_server_for_ynab.server.context import AppContext, set_app_context

__all__ = ["create_app", "create_embedded_app", "mcp", "package_version"]

mcp = MCPServer(
    # YNAB's OAuth application requirements: an application name may not include
    # "YNAB" unless the word is preceded by "for". Keep this compliant.
    name="mcp-server-for-ynab",
    instructions=(
        "AI-first MCP server for YNAB budget management. "
        "Start with overview_available_tools to see the full tool catalog. "
        "Use enriched tools (overview_*, triage_*, bookkeeping_*, analysis_*) for "
        "orientation and investigation. Use raw tools for precise reads and all writes. "
        "All amounts are in milliunits: 1000 = $1.00."
    ),
    # v1 took no version argument, and the low-level server reported the SDK's
    # own version instead of ours, so this used to be set by assigning to a
    # private attribute after construction. 2.x takes it here.
    version=package_version(),
)


def _register_tools() -> None:
    """Import tool modules so they register themselves against the shared app.

    Prompts and resources come along here too. Prompts are how someone who has
    not read the tool catalogue finds a starting point — most clients surface
    them as slash commands — and resources carry the working knowledge that is
    too long to repeat in every tool description.
    """
    from mcp_server_for_ynab.server import (
        prompts,  # noqa: F401
        resources,  # noqa: F401
    )
    from mcp_server_for_ynab.server.tools import (
        audit,  # noqa: F401
        enriched,  # noqa: F401
        history,  # noqa: F401
        raw,  # noqa: F401
        writes,  # noqa: F401
    )
    from mcp_server_for_ynab.server.tools.presentation import apply_presentation

    apply_presentation(mcp)


def create_app() -> MCPServer:
    """Initialize the application context and register all tools.

    Called once at startup. Safe to call multiple times — subsequent calls
    return the same MCPServer instance after re-initializing the context.
    """
    settings = get_settings()
    settings.configure_logging()
    ctx = AppContext.from_settings(settings)
    set_app_context(ctx)
    _register_tools()

    return mcp


def create_embedded_app() -> MCPServer:
    """Return the shared MCPServer app for hosted runtimes that inject auth."""
    _register_tools()

    return mcp
