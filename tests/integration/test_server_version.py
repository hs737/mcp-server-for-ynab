"""Integration tests: the version a client sees during initialize.

The low-level server falls back to the mcp SDK's own version when its version is
unset, so a server that never sets one reports the SDK's version as its own and
tells a client the wrong thing about what it is talking to. In mcp 1.x there was
no version parameter and this had to be assigned onto a private attribute after
construction; 2.x takes `version` on the MCPServer constructor. Either way the
thing worth testing is the same, and it is the observable end of it: what
`initialize` actually reports.

The accessor is private in both versions (`_mcp_server` in 1.x, `_lowlevel_server`
in 2.x), which is exactly why this test exists — a rename there is silent, and
the symptom is a wrong version number rather than a crash.
"""

from __future__ import annotations

from importlib.metadata import version

from mcp_server_for_ynab.server.app import mcp, package_version


def _initialization_options() -> object:
    return mcp._lowlevel_server.create_initialization_options()


def test_initialize_reports_the_package_version() -> None:
    assert _initialization_options().server_version == package_version()  # type: ignore[attr-defined]


def test_reported_version_is_not_the_sdk_version() -> None:
    assert _initialization_options().server_version != version("mcp")  # type: ignore[attr-defined]


def test_server_name_complies_with_ynab_naming_rules() -> None:
    """YNAB: an application name may not contain "YNAB" unless preceded by "for"."""
    server_name = _initialization_options().server_name  # type: ignore[attr-defined]
    assert server_name == "mcp-server-for-ynab"

    lowered = server_name.lower()
    if "ynab" in lowered:
        assert "for-ynab" in lowered or "for ynab" in lowered
