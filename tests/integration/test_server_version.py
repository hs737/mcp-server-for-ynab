"""Integration tests: the version a client sees during initialize.

FastMCP has no version parameter, and the low-level server falls back to the mcp
SDK's version when its own is unset. Without an explicit assignment the server
reported the SDK version (1.27.1) as its own, which tells a client the wrong
thing about what it is talking to.
"""

from __future__ import annotations

from importlib.metadata import version

from mcp_server_for_ynab.server.app import mcp, package_version


def test_initialize_reports_the_package_version() -> None:
    options = mcp._mcp_server.create_initialization_options()
    assert options.server_version == package_version()


def test_reported_version_is_not_the_sdk_version() -> None:
    options = mcp._mcp_server.create_initialization_options()
    assert options.server_version != version("mcp")


def test_server_name_complies_with_ynab_naming_rules() -> None:
    """YNAB: an application name may not contain "YNAB" unless preceded by "for"."""
    options = mcp._mcp_server.create_initialization_options()
    assert options.server_name == "mcp-server-for-ynab"

    lowered = options.server_name.lower()
    if "ynab" in lowered:
        assert "for-ynab" in lowered or "for ynab" in lowered
