"""Run the real tools against the synthetic backend and save what they return.

Nothing in the GIF is hand-written: this captures genuine tool output, which the
frame renderer then formats. If a tool changes shape, the demo changes with it.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import backend  # noqa: E402

os.environ["YNAB_API_KEY"] = "demo-token"
os.environ["YNAB_PLAN_ID"] = backend.PLAN_ID

base = backend.serve()

from mcp_server_for_ynab.http_client import client as http_client  # noqa: E402

http_client.YNAB_BASE_URL = base

from mcp_server_for_ynab.server.app import create_app  # noqa: E402


async def main() -> None:
    app = create_app()
    manager = app._tool_manager

    calls = [
        ("overview_month_health", {}),
        ("overview_cash_position", {}),
        ("triage_summary", {}),
        ("analysis_recurring_charges", {"months": 12}),
        ("analysis_overspent_categories", {}),
    ]

    out = {}
    for name, args in calls:
        # The registered function is invoked directly rather than through
        # ToolManager.call_tool, which needs a request Context this script has
        # no way to build and whose signature has already changed once across an
        # SDK major. The function is the same object the manager would call, so
        # the capture is still genuine tool output.
        result = await manager.get_tool(name).fn(**args)
        payload = result if isinstance(result, dict) else json.loads(str(result))
        if "error" in payload:
            print(f"{name}: ERROR {payload['error']}", file=sys.stderr)
        out[name] = payload
        print(f"captured {name}", file=sys.stderr)

    (HERE / ".captured.json").write_text(json.dumps(out, indent=2))
    print(f"wrote {HERE / '.captured.json'}", file=sys.stderr)


asyncio.run(main())
