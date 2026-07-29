"""Call every read-only tool against the live YNAB API and report failures.

Unit and contract tests use payloads we wrote ourselves, so a model that
disagrees with the real API passes them and still fails in production. This
script is the check that closes that gap: it drives the server as a real MCP
client over stdio, invokes every tool annotated read-only, and reports any tool
whose response does not parse.

Writes are never invoked. Tool selection comes from the readOnlyHint annotation
in tools/list, so new read tools are picked up automatically.

Usage:
    uv run python scripts/live_read_sweep.py [--month YYYY-MM-01]

Requires YNAB_API_KEY and YNAB_PLAN_ID in the environment.
Exits 0 when every read tool succeeds, 1 otherwise.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parent.parent
CALL_TIMEOUT_SECONDS = 120


def _first(payload: Any, key: str) -> Any:
    """Return the first value found for `key` anywhere in a nested payload."""
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = _first(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _first(item, key)
            if found is not None:
                return found
    return None


class Sweep:
    """Invokes read tools and records the outcome of each."""

    def __init__(self, session: ClientSession, month: str) -> None:
        self._session = session
        self._month = month
        self._ids: dict[str, str] = {"month": month}
        self.results: list[tuple[str, str, str]] = []

    async def call(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call one tool. Returns the parsed body, or None if it failed."""
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments),
                timeout=CALL_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            self.results.append((name, "TIMEOUT", f"no response in {CALL_TIMEOUT_SECONDS}s"))
            return None
        except Exception as exc:
            self.results.append((name, "EXCEPTION", f"{type(exc).__name__}: {exc}"))
            return None

        body = "\n".join(getattr(block, "text", str(block)) for block in result.content)
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            self.results.append((name, "BAD_JSON", body[:200]))
            return None

        # The tool boundary reports failures as a structured error payload
        # rather than an MCP protocol error, so inspect the body itself.
        if isinstance(parsed, dict) and "error" in parsed:
            message = str(parsed["error"].get("message", parsed["error"]))
            self.results.append((name, "ERROR", message.replace("\n", " ")[:200]))
            return None

        self.results.append((name, "ok", ""))
        return parsed

    async def discover_ids(self) -> None:
        """Fetch the identifiers that per-resource tools need as arguments."""
        accounts = await self.call("accounts_list", {})
        account = _first(accounts, "accounts")
        if account:
            self._ids["account_id"] = account[0]["id"]

        categories = await self.call("categories_list", {})
        groups = _first(categories, "category_groups") or []
        for group in groups:
            for category in group.get("categories", []):
                if not category.get("hidden"):
                    self._ids["category_id"] = category["id"]
                    break
            if "category_id" in self._ids:
                break

        payees = await self.call("payees_list", {})
        payee = _first(payees, "payees")
        if payee:
            self._ids["payee_id"] = payee[0]["id"]

        transactions = await self.call("transactions_list", {})
        items = _first(transactions, "items") or _first(transactions, "transactions") or []
        if items:
            self._ids["transaction_id"] = items[0]["id"]

        locations = await self.call("payee_locations_list", {})
        location = _first(locations, "payee_locations")
        if location:
            self._ids["payee_location_id"] = location[0]["id"]

        # A plan with no scheduled transactions leaves this unset, and the
        # per-record tool is reported as skipped rather than failed.
        scheduled = await self.call("scheduled_transactions_list", {})
        scheduled_items = _first(scheduled, "scheduled_transactions") or []
        if scheduled_items:
            self._ids["scheduled_transaction_id"] = scheduled_items[0]["id"]

    def arguments_for(self, schema: dict[str, Any]) -> dict[str, Any] | None:
        """Build arguments for a tool, or None if a required one is unavailable."""
        arguments: dict[str, Any] = {}
        required = schema.get("required", [])
        for name in required:
            if name not in self._ids:
                return None
            arguments[name] = self._ids[name]
        return arguments


async def run(month: str) -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ynab_mcp.cli.main", "stdio"],
        env=dict(os.environ),
        cwd=str(REPO_ROOT),
    )

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        tools = (await session.list_tools()).tools

        read_tools = [t for t in tools if getattr(t.annotations, "readOnlyHint", False)]
        print(f"Sweeping {len(read_tools)} read-only tools of {len(tools)} total, month={month}\n")

        sweep = Sweep(session, month)
        await sweep.discover_ids()
        already_called = {name for name, _, _ in sweep.results}

        skipped: list[str] = []
        for tool in read_tools:
            if tool.name in already_called:
                continue
            arguments = sweep.arguments_for(tool.inputSchema)
            if arguments is None:
                skipped.append(tool.name)
                continue
            await sweep.call(tool.name, arguments)

    failures = [r for r in sweep.results if r[1] != "ok"]

    for name, status, detail in sweep.results:
        print(f"{status:10} {name}")
        if detail:
            print(f"           {detail}")
    if skipped:
        print(f"\nSkipped (no value available for a required argument): {', '.join(skipped)}")

    print(f"\n{len(sweep.results) - len(failures)} ok, {len(failures)} failed")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--month",
        default=date.today().replace(day=1).isoformat(),
        help="Month to use for month-scoped tools, as the first day (default: current month).",
    )
    args = parser.parse_args()

    if not os.environ.get("YNAB_API_KEY"):
        print("ERROR: YNAB_API_KEY is not set. Load your .env first.", file=sys.stderr)
        sys.exit(1)
    if not os.environ.get("YNAB_PLAN_ID"):
        print("ERROR: YNAB_PLAN_ID is not set. The sweep needs a default plan.", file=sys.stderr)
        sys.exit(1)

    sys.exit(asyncio.run(run(args.month)))


if __name__ == "__main__":
    main()
