"""Unit tests: the write journal."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_server_for_ynab.history import journal


@pytest.fixture(autouse=True)
def _isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Never touch the real ~/.mcp-for-ynab/history.jsonl from a test."""
    monkeypatch.setenv("YNAB_HISTORY_PATH", str(tmp_path / "history.jsonl"))


def test_entries_round_trip_oldest_first() -> None:
    journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="a")
    journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="b")

    entries = journal.load()
    assert [e.entity_id for e in entries] == ["a", "b"]


def test_before_state_is_preserved_verbatim() -> None:
    before = {"id": "t1", "amount": -25_000, "memo": "old", "payee_id": None}
    entry = journal.record(operation="transaction_update", tool="t", plan_id="p1", entity_id="t1", before=before)

    assert journal.get(entry.id).before == before


def test_creating_an_account_is_recorded_but_not_revertible() -> None:
    entry = journal.record(operation="account_create", tool="accounts_create", plan_id="p1", entity_id="a1")

    assert entry.revertible is False
    assert "no route to delete an account" in entry.summary()["not_revertible_because"]


def test_an_update_is_revertible_until_it_is_reverted() -> None:
    entry = journal.record(operation="transaction_update", tool="t", plan_id="p1", entity_id="t1", before={})
    assert entry.revertible is True

    journal.mark_reverted(entry.id, "rev123")

    assert journal.get(entry.id).revertible is False
    assert journal.get(entry.id).reverted_by == "rev123"


def test_a_truncated_final_line_does_not_break_the_history() -> None:
    """A process killed mid-append must not make earlier entries unreadable."""
    journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id="a")
    path = journal.history_path()
    with path.open("a") as fh:
        fh.write('{"operation": "transaction_cre')

    entries = journal.load()
    assert len(entries) == 1
    assert entries[0].entity_id == "a"


def test_history_is_capped() -> None:
    for i in range(journal.MAX_ENTRIES + 25):
        journal.record(operation="transaction_create", tool="t", plan_id="p1", entity_id=f"e{i}")

    entries = journal.load()
    assert len(entries) == journal.MAX_ENTRIES
    assert entries[-1].entity_id == f"e{journal.MAX_ENTRIES + 24}"  # newest survives


def test_ids_are_unique() -> None:
    ids = {journal.record(operation="transaction_create", tool="t", plan_id="p1").id for _ in range(50)}
    assert len(ids) == 50


def test_summary_omits_payloads_but_detail_includes_them() -> None:
    entry = journal.record(
        operation="transaction_update", tool="t", plan_id="p1", entity_id="t1", before={"memo": "old"}
    )

    assert "before" not in entry.summary()
    assert entry.detail()["before"] == {"memo": "old"}
