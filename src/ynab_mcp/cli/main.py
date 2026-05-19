"""CLI entrypoint for ynab-mcp.

Subcommands:
  stdio   Start the MCP server on stdio (production transport for LLM clients).
  http    Start the MCP server on HTTP/streamable-http (development/testing transport).
  smoke   Run a startup smoke test and exit.

The same FastMCP application instance serves all transports — the transport is
purely a delivery mechanism. stdio is the standard for LLM client integration
(e.g. Claude Desktop). http exposes the MCP JSON-RPC protocol over HTTP,
which is useful for development, debugging, and the MCP Inspector tool.

Do NOT add a separate web framework (FastAPI, Flask, etc.) alongside FastMCP.
If you need HTTP access, use the built-in 'http' subcommand. Mixing web
frameworks creates two separate server processes with conflicting lifecycles.
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ynab-mcp",
        description="AI-first MCP server for YNAB budget management.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser(
        "stdio",
        help="Start the MCP server on stdio (default; for LLM clients like Claude Desktop).",
    )

    http_parser = subparsers.add_parser(
        "http",
        help=(
            "Start the MCP server over HTTP/streamable-http. "
            "For development, debugging, and MCP Inspector. "
            "Not a REST API — uses MCP JSON-RPC protocol at /mcp."
        ),
    )
    http_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind host. Default: 127.0.0.1. Use 0.0.0.0 with caution.",
    )
    http_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Bind port. Default: 8000.",
    )

    subparsers.add_parser("smoke", help="Validate configuration and tool registration, then exit.")

    args = parser.parse_args()

    if args.command == "smoke":
        from ynab_mcp.cli.smoke import run_smoke

        run_smoke()
        return

    if args.command == "http":
        _run_http(host=args.host, port=args.port)
        return

    if args.command not in (None, "stdio"):
        parser.print_help()
        sys.exit(1)

    _run_stdio()


def _run_stdio() -> None:
    from ynab_mcp.server.app import create_app

    app = create_app()
    app.run(transport="stdio")


def _run_http(host: str, port: int) -> None:
    """Start the MCP server over streamable-HTTP.

    The MCP JSON-RPC endpoint is served at http://{host}:{port}/mcp.
    This is the MCP protocol over HTTP, not a REST API.
    YNAB tools are invoked the same way as over stdio — the only difference
    is the transport layer.

    Configuration: FASTMCP_HOST and FASTMCP_PORT env vars override CLI flags.
    """
    import os

    # FastMCP reads host/port from FASTMCP_* env vars; CLI flags are the fallback.
    os.environ.setdefault("FASTMCP_HOST", host)
    os.environ.setdefault("FASTMCP_PORT", str(port))

    from ynab_mcp.server.app import create_app

    app = create_app()
    app.run(transport="streamable-http")


if __name__ == "__main__":
    main()
