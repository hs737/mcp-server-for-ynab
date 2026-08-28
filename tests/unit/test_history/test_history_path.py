"""Unit tests: which history file the journal picks.

The directory was renamed from ~/.mcp-for-ynab to ~/.mcp-server-for-ynab to
match the package name. This file holds the before-states that make a revert
possible, and YNAB cannot reproduce them, so anyone upgrading has to keep
reaching the entries they already have — a rename that quietly stranded them
would break the one guarantee the journal exists to provide.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_server_for_ynab.history import journal


@pytest.fixture(autouse=True)
def _no_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("YNAB_HISTORY_PATH", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))


def _legacy(home: Path) -> Path:
    return home / journal.LEGACY_HISTORY_DIR / "history.jsonl"


def _current(home: Path) -> Path:
    return home / journal.HISTORY_DIR / "history.jsonl"


def test_fresh_install_uses_the_new_directory(tmp_path: Path) -> None:
    assert journal.history_path() == _current(tmp_path)


def test_an_existing_legacy_file_keeps_being_used(tmp_path: Path) -> None:
    legacy = _legacy(tmp_path)
    legacy.parent.mkdir(parents=True)
    legacy.write_text("")

    assert journal.history_path() == legacy


def test_the_new_location_wins_once_it_exists(tmp_path: Path) -> None:
    """Both present means the move already happened; do not fall back."""
    for path in (_legacy(tmp_path), _current(tmp_path)):
        path.parent.mkdir(parents=True)
        path.write_text("")

    assert journal.history_path() == _current(tmp_path)


def test_the_override_beats_both(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    legacy = _legacy(tmp_path)
    legacy.parent.mkdir(parents=True)
    legacy.write_text("")
    monkeypatch.setenv("YNAB_HISTORY_PATH", str(tmp_path / "elsewhere.jsonl"))

    assert journal.history_path() == tmp_path / "elsewhere.jsonl"


def test_legacy_entries_are_still_readable_after_the_rename(tmp_path: Path) -> None:
    """The point of the fallback: past writes stay revertible."""
    legacy = _legacy(tmp_path)
    legacy.parent.mkdir(parents=True)
    legacy.write_text("")

    entry = journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="a")

    assert legacy.read_text() != ""
    assert not _current(tmp_path).exists()
    assert journal.get(entry.id).entity_id == "a"
