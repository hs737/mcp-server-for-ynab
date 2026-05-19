"""Smoke test helper: validates startup without running the full server loop.

Used by `make smoke-stdio` (ynab-mcp smoke). Exits 0 on success, 1 on failure.
Requires YNAB_API_KEY to be set; YNAB_PLAN_ID is optional.
"""

from __future__ import annotations

import sys


def run_smoke() -> None:
    print("smoke: checking environment and startup...")

    try:
        from ynab_mcp.config.settings import get_settings

        settings = get_settings()
        print(f"smoke: YNAB_API_KEY present (length={len(settings.ynab_api_key)})")
        if settings.ynab_plan_id:
            print(f"smoke: YNAB_PLAN_ID={settings.ynab_plan_id}")
        else:
            print("smoke: YNAB_PLAN_ID not set (plan_id required per-call)")
    except Exception as exc:
        print(f"smoke: FAILED — settings error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        from ynab_mcp.server.app import create_app, mcp

        create_app()
        tools = list(mcp._tool_manager._tools.keys()) if hasattr(mcp, "_tool_manager") else []
        print(f"smoke: app created, {len(tools)} tools registered")
    except Exception as exc:
        print(f"smoke: FAILED — app creation error: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        from ynab_mcp.server.registry import tool_registry

        total = len(tool_registry.all())
        families = list(tool_registry.by_family().keys())
        print(f"smoke: tool registry has {total} entries across families: {sorted(families)}")
    except Exception as exc:
        print(f"smoke: FAILED — registry error: {exc}", file=sys.stderr)
        sys.exit(1)

    print("smoke: OK")
