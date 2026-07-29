"""CLI entrypoint for mcp-server-for-ynab.

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
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mcp-server-for-ynab",
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
        default=None,
        help="Bind host. Falls back to FASTMCP_HOST, then 127.0.0.1. Use 0.0.0.0 with caution.",
    )
    http_parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Bind port. Falls back to FASTMCP_PORT, then 8000.",
    )

    subparsers.add_parser("smoke", help="Validate configuration and tool registration, then exit.")

    history_parser = subparsers.add_parser(
        "history",
        help="Inspect, export, or delete the local write history. Needs no credentials.",
    )
    history_group = history_parser.add_mutually_exclusive_group(required=True)
    history_group.add_argument(
        "--show",
        action="store_true",
        help="Print where the history is stored and how many entries it holds.",
    )
    history_group.add_argument(
        "--export",
        metavar="PATH",
        help="Write the full history to PATH as JSON. Use - for stdout.",
    )
    history_group.add_argument(
        "--delete",
        action="store_true",
        help="Delete the history file. This also removes the ability to revert past writes.",
    )
    history_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt for --delete.",
    )

    args = parser.parse_args()

    if args.command == "smoke":
        from mcp_server_for_ynab.cli.smoke import run_smoke

        run_smoke()
        return

    if args.command == "history":
        _run_history(show=args.show, export=args.export, delete=args.delete, assume_yes=args.yes)
        return

    if args.command == "http":
        _run_http(host=args.host, port=args.port)
        return

    if args.command not in (None, "stdio"):
        parser.print_help()
        sys.exit(1)

    _run_stdio()


def _run_stdio() -> None:
    from mcp_server_for_ynab.server.app import create_app

    app = create_app()
    app.run(transport="stdio")


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _run_history(*, show: bool, export: str | None, delete: bool, assume_yes: bool) -> None:
    """Inspect, export, or delete the local write history.

    This server stores exactly one thing: the record of writes it performed, on
    the machine that ran it. Exporting and deleting it needs no credentials and
    no agent, because someone who wants their data back or gone should not have
    to run an LLM to get it.
    """
    import json

    from mcp_server_for_ynab.history import journal

    path = journal.history_path()

    if show:
        entries = journal.load()
        print(f"history file: {path}")
        print(f"exists: {path.exists()}")
        print(f"entries: {len(entries)}")
        if entries:
            print(f"oldest: {entries[0].at}")
            print(f"newest: {entries[-1].at}")
        print("\nThis file is the only data this server stores. It never leaves your machine.")
        return

    if export is not None:
        payload = json.dumps([entry.detail() for entry in journal.load()], indent=2)
        if export == "-":
            print(payload)
        else:
            destination = Path(export).expanduser()
            destination.write_text(payload + "\n")
            print(f"Exported {len(journal.load())} entries to {destination}")
        return

    if delete:
        if not path.exists():
            print(f"Nothing to delete: {path} does not exist.")
            return
        if not assume_yes:
            print(f"This deletes {path} and with it the ability to revert past writes.")
            answer = input("Type 'delete' to confirm: ").strip()
            if answer != "delete":
                print("Cancelled. Nothing was deleted.")
                return
        path.unlink()
        print(f"Deleted {path}")


def resolve_bind(host: str | None, port: int | None) -> tuple[str, int]:
    """Resolve the HTTP bind address: CLI flag, then env var, then default.

    FastMCP takes host and port as constructor arguments that default to
    127.0.0.1:8000, and those arguments win over FASTMCP_HOST / FASTMCP_PORT.
    Because the shared FastMCP instance in server.app is built without them,
    setting the env vars here would do nothing — the caller must assign the
    resolved values onto app.settings before run().
    """
    import os

    resolved_host = host or os.environ.get("FASTMCP_HOST") or DEFAULT_HOST

    if port is not None:
        resolved_port = port
    else:
        env_port = os.environ.get("FASTMCP_PORT")
        resolved_port = int(env_port) if env_port else DEFAULT_PORT

    return resolved_host, resolved_port


def _run_http(host: str | None, port: int | None) -> None:
    """Start the MCP server over streamable-HTTP.

    The MCP JSON-RPC endpoint is served at http://{host}:{port}/mcp.
    This is the MCP protocol over HTTP, not a REST API.
    YNAB tools are invoked the same way as over stdio — the only difference
    is the transport layer.
    """
    resolved_host, resolved_port = resolve_bind(host, port)

    from mcp_server_for_ynab.server.app import create_app

    app = create_app()
    app.settings.host = resolved_host
    app.settings.port = resolved_port
    app.run(transport="streamable-http")


if __name__ == "__main__":
    main()
