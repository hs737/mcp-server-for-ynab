"""Unit tests: the prompt and resource surface.

Prompts are the discovery path for anyone who has not read the tool catalogue,
and resources carry the guidance that is too long to repeat in every tool
description. Both are easy to break silently, because nothing else in the suite
loads them.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from mcp_server_for_ynab.server import prompts, resources
from mcp_server_for_ynab.server.app import mcp

EXPECTED_PROMPTS = {
    "monthly_review",
    "weekly_triage",
    "categorize_and_approve",
    "subscription_audit",
    "cash_position",
    "undo_last_changes",
    "budget_audit",
}

RESOURCE_BODIES = [
    resources.method_guide,
    resources.write_safety_guide,
    resources.tool_selection_guide,
    resources.credit_accounts_guide,
]


@pytest.fixture(autouse=True)
def _registered(ynab_env: None) -> None:
    from mcp_server_for_ynab.server.app import create_app

    create_app()


def _all_tool_names() -> set[str]:
    """Every tool name, writes included.

    Has to run out of process: tool modules read the write gate at import time,
    so once this interpreter has imported them read-only the write tools are
    gone for the rest of the session and no amount of env patching brings them
    back. That is the design working correctly, not a limitation to route
    around in the source.
    """
    script = (
        "import json;"
        "from mcp_server_for_ynab.server.app import create_app;"
        "from mcp_server_for_ynab.server.registry import tool_registry;"
        "create_app();"
        "print(json.dumps([m.name for m in tool_registry.all()]))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "YNAB_API_KEY": "test-pat-key-abc123", "YNAB_ALLOW_WRITES": "1"},
    )
    return set(json.loads(completed.stdout.strip().splitlines()[-1]))


async def test_every_prompt_is_registered() -> None:
    registered = {prompt.name for prompt in await mcp.list_prompts()}
    assert EXPECTED_PROMPTS <= registered


async def test_prompts_carry_a_title_for_clients_to_display() -> None:
    for prompt in await mcp.list_prompts():
        if prompt.name in EXPECTED_PROMPTS:
            assert prompt.title, f"{prompt.name} has no title"
            assert prompt.description, f"{prompt.name} has no description"


async def test_every_resource_is_registered() -> None:
    uris = {str(resource.uri) for resource in await mcp.list_resources()}
    assert {
        "ynab://guide/method",
        "ynab://guide/write-safety",
        "ynab://guide/tool-selection",
    } <= uris


@pytest.mark.parametrize("body", RESOURCE_BODIES)
def test_resources_return_non_trivial_markdown(body: object) -> None:
    text = body()  # type: ignore[operator]
    assert text.lstrip().startswith("#")
    assert len(text) > 500


def test_prompts_name_only_tools_that_exist() -> None:
    """A prompt that sends the model at a tool we removed is worse than none."""
    import re

    known = _all_tool_names()
    bodies = [
        prompts.monthly_review(),
        prompts.weekly_triage(),
        prompts.categorize_and_approve(),
        prompts.subscription_audit(),
        prompts.cash_position(),
        prompts.undo_last_changes(),
        prompts.budget_audit(),
    ]

    referenced = {name for body in bodies for name in re.findall(r"`([a-z_]+_[a-z_]+)`", body)}
    unknown = referenced - known

    assert not unknown, f"prompts reference tools that are not registered: {sorted(unknown)}"
