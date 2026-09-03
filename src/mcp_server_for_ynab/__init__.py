"""AI-first MCP server for YNAB.

Kept free of heavy imports: `cli.main` reads the version from here to answer
--version without importing MCPServer and the whole tool surface.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

__all__ = ["package_version"]


def package_version() -> str:
    """Return this package's version, as clients see it during initialize."""
    try:
        return version("mcp-server-for-ynab")
    except PackageNotFoundError:  # running from a source tree without an install
        return "0.0.0+unknown"
