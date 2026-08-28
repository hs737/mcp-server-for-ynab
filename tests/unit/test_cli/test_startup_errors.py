"""Unit tests: what the CLI does when configuration is missing.

An unset YNAB_API_KEY is the single most common first-run failure, and stdio
clients such as Claude Desktop show the user only what reaches stderr — inside a
log file they have to go find. A traceback there buries the one line that says
what to do, so these tests pin the clean exit.
"""

from __future__ import annotations

import pytest

from mcp_server_for_ynab import package_version
from mcp_server_for_ynab.cli import main as cli_main


def test_missing_api_key_exits_with_one_readable_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("YNAB_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exc:
        cli_main._create_app_or_exit()

    assert exc.value.code == 1

    captured = capsys.readouterr()
    assert captured.out == ""
    assert "YNAB_API_KEY" in captured.err
    assert "Traceback" not in captured.err
    assert captured.err.strip().count("\n") == 0


def test_the_error_names_where_the_variable_goes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A uvx user has no clone, so pointing at .env.example is a dead end."""
    monkeypatch.delenv("YNAB_API_KEY", raising=False)

    with pytest.raises(SystemExit):
        cli_main._create_app_or_exit()

    err = capsys.readouterr().err
    assert "MCP client config" in err
    assert ".env.example" not in err


def test_version_flag_reports_the_package_version(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.argv", ["mcp-server-for-ynab", "--version"])

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    assert exc.value.code == 0
    assert package_version() in capsys.readouterr().out


def test_version_flag_needs_no_credentials(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--version is what someone runs while filing a bug, often before setup."""
    monkeypatch.delenv("YNAB_API_KEY", raising=False)
    monkeypatch.setattr("sys.argv", ["mcp-server-for-ynab", "--version"])

    with pytest.raises(SystemExit) as exc:
        cli_main.main()

    assert exc.value.code == 0
