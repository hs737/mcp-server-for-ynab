"""Unit tests: HTTP bind address resolution.

FastMCP's host and port are constructor arguments defaulting to 127.0.0.1:8000,
and they take precedence over FASTMCP_HOST / FASTMCP_PORT. An earlier version of
the CLI only set those env vars, so `--port` was silently ignored and the server
always bound 8000. These tests pin the precedence order.
"""

from __future__ import annotations

import pytest

from mcp_server_for_ynab.cli.main import DEFAULT_HOST, DEFAULT_PORT, resolve_bind


def test_defaults_when_nothing_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FASTMCP_HOST", raising=False)
    monkeypatch.delenv("FASTMCP_PORT", raising=False)
    assert resolve_bind(None, None) == (DEFAULT_HOST, DEFAULT_PORT)


def test_cli_flags_win(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FASTMCP_HOST", "10.0.0.1")
    monkeypatch.setenv("FASTMCP_PORT", "9999")
    assert resolve_bind("0.0.0.0", 8123) == ("0.0.0.0", 8123)


def test_env_vars_used_when_flags_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FASTMCP_HOST", "10.0.0.1")
    monkeypatch.setenv("FASTMCP_PORT", "9999")
    assert resolve_bind(None, None) == ("10.0.0.1", 9999)


def test_host_and_port_resolve_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FASTMCP_HOST", "10.0.0.1")
    monkeypatch.delenv("FASTMCP_PORT", raising=False)
    assert resolve_bind(None, 8123) == ("10.0.0.1", 8123)


def test_empty_env_values_fall_through_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FASTMCP_HOST", "")
    monkeypatch.setenv("FASTMCP_PORT", "")
    assert resolve_bind(None, None) == (DEFAULT_HOST, DEFAULT_PORT)


def test_port_zero_is_honoured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Port 0 means "pick a free port" — it must not be treated as unset."""
    monkeypatch.delenv("FASTMCP_PORT", raising=False)
    assert resolve_bind(None, 0)[1] == 0


def test_http_passes_the_resolved_bind_to_run() -> None:
    """mcp 2.x dropped host and port from settings and takes them as run()
    arguments. The old code assigned app.settings.host/port, which on 2.x would
    raise rather than bind somewhere wrong — but nothing here covered the wiring,
    so the transport was the one code path the suite could not vouch for."""
    from unittest.mock import MagicMock, patch

    import mcp_server_for_ynab.cli.main as cli

    app = MagicMock()
    with patch.object(cli, "_create_app_or_exit", return_value=app):
        cli._run_http("0.0.0.0", 9001)

    app.run.assert_called_once_with(transport="streamable-http", host="0.0.0.0", port=9001)
