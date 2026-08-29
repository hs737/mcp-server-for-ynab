"""Detect when the generated assets have gone stale.

The README GIF and the social card assert things about the server: how many
tools it registers, which tools answer which question, and how money is
formatted. Those claims are baked into pixels, so a reviewer reading a diff
cannot see them go wrong — an image is the one artefact nobody proofreads.

So the facts are recorded next to the assets when they are rendered, and this
compares them against the live code. It deliberately does not compare pixels:
the renderers are deterministic but ImageMagick and font rendering are not
stable across machines, and a check that fails for the wrong reason gets muted.

Usage:
    uv run python scripts/check_assets.py --write   # record current facts
    uv run python scripts/check_assets.py           # fail if they have drifted
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "assets" / "manifest.json"

# Tools whose output appears in the GIF. If one is renamed or removed, the demo
# is showing something that no longer exists.
TOOLS_SHOWN = [
    "overview_month_health",
    "overview_cash_position",
    "triage_summary",
    "analysis_recurring_charges",
    "analysis_overspent_categories",
]

# The GIF renders whatever the tools put in their *_display fields, so a change
# to money formatting changes every figure on screen.
FORMAT_SAMPLE_MILLIUNITS = 14_840_360


def _registered_tools() -> list[str]:
    """Every tool name, writes included.

    Out of process because tool modules read the write gate at import time, so
    an interpreter that has already imported them read-only cannot see the
    write tools regardless of the environment.
    """
    script = (
        "import json;"
        "from mcp_server_for_ynab.server.app import create_app;"
        "from mcp_server_for_ynab.server.registry import tool_registry;"
        "create_app();"
        "print(json.dumps(sorted(m.name for m in tool_registry.all())))"
    )
    env = {**os.environ, "YNAB_API_KEY": "check-only", "YNAB_ALLOW_WRITES": "1"}
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, check=True, env=env)
    names: list[str] = json.loads(result.stdout.strip().splitlines()[-1])
    return names


def current_facts() -> dict[str, Any]:
    from mcp_server_for_ynab.models.amounts import milliunits_to_display

    names = _registered_tools()
    return {
        "tool_count": len(names),
        "tools_shown": TOOLS_SHOWN,
        "tools_shown_all_exist": sorted(set(TOOLS_SHOWN) - set(names)) == [],
        "money_format_sample": {
            "milliunits": FORMAT_SAMPLE_MILLIUNITS,
            "display": milliunits_to_display(FORMAT_SAMPLE_MILLIUNITS),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Record the current facts instead of checking them.")
    args = parser.parse_args()

    facts = current_facts()

    missing = sorted(set(TOOLS_SHOWN) - set(_registered_tools()))
    if missing:
        print(f"ERROR: the demo shows tools that no longer exist: {missing}", file=sys.stderr)
        return 1

    if args.write:
        MANIFEST.parent.mkdir(exist_ok=True)
        MANIFEST.write_text(json.dumps(facts, indent=2) + "\n")
        print(f"Recorded asset facts: {facts['tool_count']} tools, sample {facts['money_format_sample']['display']}")
        return 0

    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST.relative_to(REPO_ROOT)} is missing. Run: make assets", file=sys.stderr)
        return 1

    recorded = json.loads(MANIFEST.read_text())
    drift = [key for key in ("tool_count", "tools_shown", "money_format_sample") if recorded.get(key) != facts[key]]

    if drift:
        print("ERROR: the generated assets are out of date. They still claim:", file=sys.stderr)
        for key in drift:
            print(f"  {key}: {recorded.get(key)!r}  ->  now {facts[key]!r}", file=sys.stderr)
        print("\nRe-render them with: make assets", file=sys.stderr)
        return 1

    print(f"OK: assets are current. ({facts['tool_count']} tools, sample {facts['money_format_sample']['display']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
