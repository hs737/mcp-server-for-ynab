"""Generate the packaging manifests that carry a version number.

Four files describe this server to install surfaces that never read
pyproject.toml: the Claude Code plugin and its marketplace, the MCP client
config they point at, and the MCPB bundle manifest. Each one repeats the
version, the description, and the launch command.

Hand-maintained copies of the same facts drift, and the failure is silent —
a plugin that installs the previous release, or a bundle whose manifest
disagrees with the package it launches. So they are generated from
pyproject.toml, and `--check` fails CI when a committed file no longer matches
what this script would write.

Usage:
    uv run python scripts/sync_packaging.py            # write the files
    uv run python scripts/sync_packaging.py --check    # fail if out of date
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# The env block is shared by the plugin config and the bundle manifest, minus
# the bundle's user_config templating. Writes stay off: this server holds a
# credential that can modify real financial records, and an install surface is
# the last place to quietly opt someone in.
DESCRIPTION = (
    "Connect your AI assistant to YNAB. Read-only by default, with opt-in writes that are recorded and reversible."
)


def project() -> dict[str, Any]:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    return dict(data["project"])


def marketplace_manifest(version: str) -> dict[str, Any]:
    return {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": "mcp-server-for-ynab",
        "version": version,
        "description": "MCP Server for YNAB",
        "owner": {"name": "Harsh S", "url": "https://github.com/hs737"},
        "plugins": [
            {
                "name": "mcp-server-for-ynab",
                "displayName": "MCP Server for YNAB",
                "description": DESCRIPTION,
                "version": version,
                "author": {"name": "Harsh S", "url": "https://github.com/hs737"},
                "homepage": "https://github.com/hs737/mcp-server-for-ynab#readme",
                "repository": "https://github.com/hs737/mcp-server-for-ynab",
                "license": "Apache-2.0",
                "keywords": ["mcp", "ynab", "budget", "finance", "personal-finance"],
                "source": "./",
                "category": "finance",
            }
        ],
    }


def plugin_manifest(version: str) -> dict[str, Any]:
    return {
        "name": "mcp-server-for-ynab",
        "displayName": "MCP Server for YNAB",
        "version": version,
        "description": DESCRIPTION,
        "author": {"name": "Harsh S", "url": "https://github.com/hs737"},
        "homepage": "https://github.com/hs737/mcp-server-for-ynab#readme",
        "repository": "https://github.com/hs737/mcp-server-for-ynab",
        "license": "Apache-2.0",
        "keywords": ["mcp", "ynab", "budget", "finance", "personal-finance"],
        "mcpServers": "./.mcp.json",
    }


def mcp_config(version: str) -> dict[str, Any]:
    """The stdio launch config the plugin points at.

    Pinned to the exact version this manifest was generated for. `@latest`
    would let a plugin install silently change what it runs between sessions,
    which is the wrong trade for a server holding a financial credential.
    """
    return {
        "mcpServers": {
            "ynab": {
                "command": "uvx",
                "args": [f"mcp-server-for-ynab=={version}", "stdio"],
                "env": {
                    "YNAB_API_KEY": "${YNAB_API_KEY}",
                    "YNAB_PLAN_ID": "${YNAB_PLAN_ID}",
                },
            }
        }
    }


def mcpb_manifest(version: str) -> dict[str, Any]:
    """The MCPB bundle manifest, for one-click install in desktop hosts.

    `user_config` is the whole point: the host renders a form and stores the
    token in the OS keychain, so nobody hand-edits JSON or leaves a personal
    access token sitting in a config file.
    """
    return {
        "manifest_version": "0.3",
        "name": "mcp-server-for-ynab",
        "display_name": "MCP Server for YNAB",
        "version": version,
        "description": DESCRIPTION,
        "long_description": (
            "Exposes the YNAB API as MCP tools, plus enriched tools that answer in one call what the raw API "
            "cannot: budget health, cash position, cleanup queues, overspending, and recurring charges. "
            "Read-only unless you tick Allow writes. When writes are on, every change records the state that "
            "preceded it so it can be reverted."
        ),
        "author": {"name": "Harsh S", "url": "https://github.com/hs737"},
        "homepage": "https://github.com/hs737/mcp-server-for-ynab#readme",
        "documentation": "https://github.com/hs737/mcp-server-for-ynab#readme",
        "support": "https://github.com/hs737/mcp-server-for-ynab/issues",
        "license": "Apache-2.0",
        "keywords": ["mcp", "ynab", "budget", "finance", "personal-finance"],
        "server": {
            "type": "binary",
            "entry_point": "uvx",
            "mcp_config": {
                "command": "uvx",
                "args": [f"mcp-server-for-ynab=={version}", "stdio"],
                "env": {
                    "YNAB_API_KEY": "${user_config.ynab_api_key}",
                    "YNAB_PLAN_ID": "${user_config.ynab_plan_id}",
                    "YNAB_ALLOW_WRITES": "${user_config.ynab_allow_writes}",
                },
            },
        },
        "user_config": {
            "ynab_api_key": {
                "type": "string",
                "title": "YNAB Personal Access Token",
                "description": (
                    "Create one at app.ynab.com/settings/developer. Stored by your OS keychain, not in a file."
                ),
                "sensitive": True,
                "required": True,
            },
            "ynab_plan_id": {
                "type": "string",
                "title": "Default plan ID (optional)",
                "description": (
                    "Set this and you never have to name a budget in a request. Ask for your plans to find it."
                ),
                "sensitive": False,
                "required": False,
                "default": "",
            },
            "ynab_allow_writes": {
                "type": "boolean",
                "title": "Allow writes",
                "description": (
                    "Leave off to keep the assistant read-only. Turn on to let it change your budget; "
                    "every write is recorded locally and can be reverted."
                ),
                "required": False,
                "default": False,
            },
        },
        "compatibility": {"runtimes": {"python": ">=3.12"}},
    }


# The registry namespace is fixed by how ownership is proven: GitHub-based
# authentication only permits names under the authenticating account.
MCP_REGISTRY_NAME = "io.github.hs737/mcp-server-for-ynab"

# The registry caps descriptions at 100 characters, shorter than the one the
# install surfaces use. Kept as its own string rather than truncating the other,
# so a future edit cannot silently push it back over the limit.
REGISTRY_DESCRIPTION = "Connect your AI assistant to YNAB. Read-only by default, with reversible opt-in writes."


def registry_manifest(version: str) -> dict[str, Any]:
    """The official MCP Registry entry.

    Ownership is verified by finding an `mcp-name:` marker in the package
    description on PyPI, which is this repository's README. The marker and this
    name must agree, so both are generated from the same constant — a mismatch
    fails the publish with a message about verification rather than about names.
    """
    return {
        "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
        "name": MCP_REGISTRY_NAME,
        "title": "MCP Server for YNAB",
        "description": REGISTRY_DESCRIPTION,
        "version": version,
        "repository": {
            "url": "https://github.com/hs737/mcp-server-for-ynab",
            "source": "github",
        },
        "websiteUrl": "https://github.com/hs737/mcp-server-for-ynab#readme",
        "packages": [
            {
                "registryType": "pypi",
                "identifier": "mcp-server-for-ynab",
                "version": version,
                "transport": {"type": "stdio"},
                "runtimeHint": "uvx",
                "environmentVariables": [
                    {
                        "name": "YNAB_API_KEY",
                        "description": "YNAB personal access token from app.ynab.com/settings/developer.",
                        "isRequired": True,
                        "isSecret": True,
                        "format": "string",
                    },
                    {
                        "name": "YNAB_PLAN_ID",
                        "description": "Default plan (budget) id, so tools do not need it passed on every call.",
                        "isRequired": False,
                        "isSecret": False,
                        "format": "string",
                    },
                    {
                        "name": "YNAB_ALLOW_WRITES",
                        "description": (
                            "Set to 1 to register the write tools. Unset means read-only, and the write "
                            "tools are absent from tools/list entirely."
                        ),
                        "isRequired": False,
                        "isSecret": False,
                        "format": "string",
                    },
                ],
            }
        ],
    }


def targets(version: str) -> dict[Path, dict[str, Any]]:
    return {
        REPO_ROOT / ".claude-plugin" / "marketplace.json": marketplace_manifest(version),
        REPO_ROOT / ".claude-plugin" / "plugin.json": plugin_manifest(version),
        REPO_ROOT / ".mcp.json": mcp_config(version),
        REPO_ROOT / "packaging" / "mcpb" / "manifest.json": mcpb_manifest(version),
        REPO_ROOT / "server.json": registry_manifest(version),
    }


def render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if any generated file is out of date.")
    args = parser.parse_args()

    version = str(project()["version"])
    stale: list[Path] = []

    readme = REPO_ROOT / "README.md"
    marker = f"mcp-name: {MCP_REGISTRY_NAME}"
    if marker not in readme.read_text():
        print(
            f"ERROR: README.md is missing the registry ownership marker.\n  Expected to find: {marker}",
            file=sys.stderr,
        )
        return 1

    for path, payload in targets(version).items():
        expected = render(payload)
        if args.check:
            actual = path.read_text() if path.exists() else ""
            if actual != expected:
                stale.append(path)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(expected)

    if args.check:
        if stale:
            print("ERROR: packaging manifests are out of date:", file=sys.stderr)
            for path in stale:
                print(f"  {path.relative_to(REPO_ROOT)}", file=sys.stderr)
            print("\nRun: uv run python scripts/sync_packaging.py", file=sys.stderr)
            return 1
        print(f"OK: packaging manifests are current. (version {version})")
        return 0

    print(f"Wrote {len(targets(version))} packaging manifests for version {version}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
