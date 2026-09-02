"""Integration tests: the read-only default and the write opt-in.

Write tools are gated at import time, so the two states cannot both be observed
inside one process. These start a real server over stdio and read tools/list,
which is exactly what an MCP client sees. No YNAB credentials are needed —
listing tools never calls the API.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[2]

WRITE_TOOLS = {
    "accounts_create",
    "categories_create",
    "categories_update",
    "categories_update_for_month",
    "category_groups_create",
    "category_groups_update",
    "months_assign_many",
    "money_move",
    "payees_create",
    "payees_update",
    "scheduled_transactions_create",
    "scheduled_transactions_update",
    "scheduled_transactions_delete",
    "transactions_create",
    "transactions_update",
    "transactions_bulk_update",
    "transactions_delete",
    "transactions_trigger_import",
}


async def _tool_names(*, allow_writes: str | None) -> set[str]:
    env = {
        "PATH": os.environ["PATH"],
        # A syntactically valid but fake token: startup requires one, and
        # listing tools never contacts YNAB.
        "YNAB_API_KEY": "test-token-not-real",
        "YNAB_PLAN_ID": "plan-test",
    }
    if allow_writes is not None:
        env["YNAB_ALLOW_WRITES"] = allow_writes

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_server_for_ynab.cli.main", "stdio"],
        env=env,
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return {t.name for t in (await session.list_tools()).tools}


async def test_writes_are_absent_by_default() -> None:
    names = await _tool_names(allow_writes=None)

    assert not (names & WRITE_TOOLS)
    assert "transactions_list" in names  # reads still work


async def test_writes_appear_when_opted_in() -> None:
    names = await _tool_names(allow_writes="1")

    missing = WRITE_TOOLS - names
    assert not missing, f"write tools missing despite opt-in: {sorted(missing)}"


@pytest.mark.parametrize("value", ["0", "false", "no", "", "maybe"])
async def test_only_affirmative_values_enable_writes(value: str) -> None:
    names = await _tool_names(allow_writes=value)
    assert not (names & WRITE_TOOLS)


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
async def test_affirmative_spellings_all_work(value: str) -> None:
    names = await _tool_names(allow_writes=value)
    assert "transactions_create" in names
