"""Build the MCPB bundle for one-click install in desktop MCP hosts.

An MCPB bundle is a zip holding a manifest that tells the host how to launch
the server and what to ask the user for. The host renders a form for the token
and stores it in the OS keychain, which is the whole point: the alternative is
telling someone to find claude_desktop_config.json and hand-edit JSON with a
credential in it.

The bundle carries no vendored dependencies. This package depends on pydantic,
whose core is a compiled extension, so a self-contained bundle would have to
ship per-platform wheels and be built once per OS. Launching through uvx keeps
one bundle correct everywhere and resolves the same artifact published to PyPI.

Requires Node, for `npx @anthropic-ai/mcpb`.

Usage:
    uv run python scripts/build_mcpb.py [--out-dir dist]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "packaging" / "mcpb" / "manifest.json"
MCPB_CLI = "@anthropic-ai/mcpb"

# Shipped alongside the manifest so the bundle carries its own terms; a host
# that surfaces bundle contents should not have to send someone to the repo.
EXTRA_FILES = ("README.md", "LICENSE", "NOTICE.md")


def _npx(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["npx", "--yes", MCPB_CLI, *args],
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="dist", help="Directory to write the .mcpb into (default: dist).")
    args = parser.parse_args()

    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST} is missing. Run: uv run python scripts/sync_packaging.py", file=sys.stderr)
        return 1

    if shutil.which("npx") is None:
        print("ERROR: npx not found. Node is required to build the MCPB bundle.", file=sys.stderr)
        return 1

    version = json.loads(MANIFEST.read_text())["version"]

    validation = _npx("validate", str(MANIFEST))
    if validation.returncode != 0:
        print(validation.stdout or validation.stderr, file=sys.stderr)
        return 1

    out_dir = (REPO_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"mcp-server-for-ynab-{version}.mcpb"

    with tempfile.TemporaryDirectory(prefix="mcpb-") as staging_name:
        staging = Path(staging_name)
        shutil.copy2(MANIFEST, staging / "manifest.json")
        for name in EXTRA_FILES:
            source = REPO_ROOT / name
            if source.exists():
                shutil.copy2(source, staging / name)

        packed = _npx("pack", str(staging), str(output))
        if packed.returncode != 0:
            print(packed.stdout or packed.stderr, file=sys.stderr)
            return 1

    print(f"Built {output.relative_to(REPO_ROOT)} ({output.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
