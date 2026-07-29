"""Exercise every write tool against a disposable plan and report failures.

Write tools cannot be swept against a real budget, so this script is separate
from live_read_sweep.py and takes an explicit --plan-id. It refuses to run
against a plan whose name does not look disposable, and it never falls back to
YNAB_PLAN_ID: pointing this at a real budget should take deliberate effort.

The sweep builds its own scaffolding (account, category group, category, payee),
exercises each write tool in dependency order, and deletes what the YNAB API
allows deleting. Accounts, categories, category groups, and payees have no
delete endpoint in the v1 API, so they accumulate in the test plan by design.

Usage:
    uv run python scripts/live_write_sweep.py --plan-id <uuid>

Exits 0 when every write tool succeeds, 1 otherwise.
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
SAFE_NAME_MARKERS = ("test", "sandbox", "scratch", "demo", "disposable")


class WriteSweep:
    def __init__(self, session: ClientSession, plan_id: str) -> None:
        self._session = session
        self._plan = plan_id
        self.results: list[tuple[str, str, str]] = []

    async def call(self, name: str, arguments: dict[str, Any], *, record: bool = True) -> Any:
        arguments = {"plan_id": self._plan, **arguments}
        try:
            result = await asyncio.wait_for(
                self._session.call_tool(name, arguments),
                timeout=CALL_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            if record:
                self.results.append((name, "TIMEOUT", f"no response in {CALL_TIMEOUT_SECONDS}s"))
            return None
        except Exception as exc:
            if record:
                self.results.append((name, "EXCEPTION", f"{type(exc).__name__}: {exc}"))
            return None

        body = "\n".join(getattr(block, "text", str(block)) for block in result.content)
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            if record:
                self.results.append((name, "BAD_JSON", body[:200]))
            return None

        if isinstance(parsed, dict) and "error" in parsed:
            if record:
                message = str(parsed["error"].get("message", parsed["error"]))
                self.results.append((name, "ERROR", message.replace("\n", " ")[:250]))
            return None

        if record:
            self.results.append((name, "ok", ""))
        return parsed


def _dig(payload: Any, *keys: str) -> Any:
    for key in keys:
        if payload is None:
            return None
        payload = payload.get(key) if isinstance(payload, dict) else None
    return payload


async def confirm_disposable(sweep: WriteSweep, force: bool) -> str | None:
    """Return the plan name, or None if it should not be written to."""
    plan = await sweep.call("plans_get", {}, record=False)
    name = _dig(plan, "data", "budget", "name")
    if not name:
        print("ERROR: could not read the plan. Check the plan id and token.", file=sys.stderr)
        return None

    looks_disposable = any(marker in name.lower() for marker in SAFE_NAME_MARKERS)
    if not looks_disposable and not force:
        print(
            f'ERROR: plan "{name}" does not look disposable. This sweep creates and deletes\n'
            f"data. Rename the plan to include one of {', '.join(SAFE_NAME_MARKERS)}, or pass\n"
            "--force if you are certain.",
            file=sys.stderr,
        )
        return None
    return str(name)


async def run(plan_id: str, force: bool) -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ynab_mcp.cli.main", "stdio"],
        env=dict(os.environ),
        cwd=str(REPO_ROOT),
    )

    today = date.today().isoformat()
    month = date.today().replace(day=1).isoformat()
    stamp = date.today().strftime("%Y%m%d-%H%M%S")

    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        sweep = WriteSweep(session, plan_id)

        plan_name = await confirm_disposable(sweep, force)
        if plan_name is None:
            return 1
        print(f'Sweeping write tools against "{plan_name}" ({plan_id})\n')

        # --- scaffolding -------------------------------------------------
        account = await sweep.call(
            "accounts_create",
            {"name": f"Sweep Account {stamp}", "type": "checking", "balance": 100000},
        )
        account_id = _dig(account, "data", "account", "id")

        group = await sweep.call("category_groups_create", {"name": f"Sweep Group {stamp}"})
        group_id = _dig(group, "data", "category_group", "id")

        category_id = None
        if group_id:
            category = await sweep.call(
                "categories_create",
                {"name": f"Sweep Category {stamp}", "category_group_id": group_id},
            )
            category_id = _dig(category, "data", "category", "id")

        payee = await sweep.call("payees_create", {"name": f"Sweep Payee {stamp}"})
        payee_id = _dig(payee, "data", "payee", "id")

        # --- updates on the scaffolding ----------------------------------
        if group_id:
            await sweep.call(
                "category_groups_update", {"category_group_id": group_id, "name": f"Sweep Group {stamp} v2"}
            )
        if category_id:
            await sweep.call("categories_update", {"category_id": category_id, "name": f"Sweep Category {stamp} v2"})
            await sweep.call(
                "categories_update_for_month",
                {"month": month, "category_id": category_id, "budgeted": 50000},
            )
        if payee_id:
            await sweep.call("payees_update", {"payee_id": payee_id, "name": f"Sweep Payee {stamp} v2"})

        # --- transactions -------------------------------------------------
        transaction_id = None
        if account_id:
            created = await sweep.call(
                "transactions_create",
                {
                    "account_id": account_id,
                    "date": today,
                    "amount": -12340,
                    "payee_name": "Sweep Payee Inline",
                    "category_id": category_id,
                    "memo": "created by live_write_sweep",
                    "cleared": "uncleared",
                    "approved": True,
                },
            )
            transaction_id = _dig(created, "data", "transaction", "id")

        if transaction_id and account_id:
            await sweep.call(
                "transactions_update",
                {
                    "transaction_id": transaction_id,
                    "account_id": account_id,
                    "date": today,
                    "amount": -23450,
                    "memo": "updated by live_write_sweep",
                },
            )
            await sweep.call(
                "transactions_bulk_update",
                {"transactions": [{"id": transaction_id, "memo": "bulk updated by live_write_sweep"}]},
            )

        # --- scheduled transactions ---------------------------------------
        scheduled_id = None
        if account_id:
            scheduled = await sweep.call(
                "scheduled_transactions_create",
                {
                    "account_id": account_id,
                    "date": today,
                    "frequency": "monthly",
                    "amount": -5000,
                    "memo": "created by live_write_sweep",
                },
            )
            scheduled_id = _dig(scheduled, "data", "scheduled_transaction", "id")

        if scheduled_id and account_id:
            await sweep.call(
                "scheduled_transactions_update",
                {
                    "scheduled_transaction_id": scheduled_id,
                    "account_id": account_id,
                    "date": today,
                    "frequency": "monthly",
                    "amount": -6000,
                    "memo": "updated by live_write_sweep",
                },
            )
            await sweep.call("scheduled_transactions_delete", {"scheduled_transaction_id": scheduled_id})

        # --- import trigger and cleanup ------------------------------------
        await sweep.call("transactions_trigger_import", {})

        if transaction_id:
            await sweep.call("transactions_delete", {"transaction_id": transaction_id})

    failures = [r for r in sweep.results if r[1] != "ok"]
    for name, status, detail in sweep.results:
        print(f"{status:10} {name}")
        if detail:
            print(f"           {detail}")

    print(f"\n{len(sweep.results) - len(failures)} ok, {len(failures)} failed")
    print("Note: YNAB has no delete endpoint for accounts, categories, groups, or payees,")
    print("so the scaffolding this sweep created remains in the plan.")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan-id", required=True, help="Plan to write to. Must be disposable.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Write to a plan whose name does not look disposable.",
    )
    args = parser.parse_args()

    if not os.environ.get("YNAB_API_KEY"):
        print("ERROR: YNAB_API_KEY is not set. Load your .env first.", file=sys.stderr)
        sys.exit(1)

    sys.exit(asyncio.run(run(args.plan_id, args.force)))


if __name__ == "__main__":
    main()
