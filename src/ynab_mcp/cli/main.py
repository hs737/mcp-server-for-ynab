"""CLI entrypoint: ynab-mcp stdio"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ynab-mcp",
        description="AI-first MCP server for YNAB budget management.",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("stdio", help="Start the MCP server on stdio (default transport).")
    subparsers.add_parser("smoke", help="Run a startup smoke test and exit.")

    args = parser.parse_args()

    if args.command == "smoke":
        from ynab_mcp.cli.smoke import run_smoke

        run_smoke()
        return

    # Default (no subcommand) and explicit 'stdio' both start the server.
    if args.command not in (None, "stdio"):
        parser.print_help()
        sys.exit(1)

    _run_stdio()


def _run_stdio() -> None:
    from ynab_mcp.server.app import create_app

    app = create_app()
    app.run(transport="stdio")
