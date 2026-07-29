"""Append-only record of every write this server performs.

The point is not audit logging — it is being able to put a plan back the way it
was. Each entry therefore stores the *before* state of what changed, which is
the only thing YNAB cannot give you afterwards: the API has no history endpoint,
and once a value is overwritten the previous one is gone.

Entries are JSON lines under `~/.mcp-for-ynab/history.jsonl`, oldest first.
Nothing is ever rewritten in place; reverting appends a new entry of its own, so
the file stays an accurate account of what happened including the undoing.

Not everything can be undone. YNAB has no delete route for accounts, categories,
category groups, or payees, so creating one is permanent. Those entries are
recorded with `revertible: false` and a reason, because a history that silently
omits them would imply a rollback is complete when it is not.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_ENTRIES = 500

# What a revert would have to do, per kind of write.
REVERT_STRATEGIES = {
    "transaction_create": "delete the created transaction",
    "transaction_update": "restore the previous field values",
    "transaction_delete": "recreate the transaction from its recorded state",
    "transaction_bulk_update": "restore the previous values of each transaction",
    "scheduled_create": "delete the created scheduled transaction",
    "scheduled_update": "restore the previous field values",
    "scheduled_delete": "recreate the scheduled transaction from its recorded state",
    "category_update": "restore the previous name and note",
    "category_month_budget": "restore the previous budgeted amount",
    "category_group_update": "restore the previous name",
    "payee_update": "restore the previous name",
}

IRREVERSIBLE = {
    "account_create": "YNAB has no route to delete an account",
    "category_create": "YNAB has no route to delete a category",
    "category_group_create": "YNAB has no route to delete a category group",
    "payee_create": "YNAB has no route to delete a payee",
    "transactions_import": "YNAB owns imported transactions; the import cannot be rolled back",
}


def history_path() -> Path:
    """Where the journal lives. Override with YNAB_HISTORY_PATH."""
    override = os.environ.get("YNAB_HISTORY_PATH", "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / ".mcp-for-ynab" / "history.jsonl"


@dataclass
class HistoryEntry:
    operation: str  # a key of REVERT_STRATEGIES or IRREVERSIBLE
    tool: str
    plan_id: str
    entity_id: str | None = None
    before: Any = None
    after: Any = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    reverted_by: str | None = None  # id of the entry that undid this one
    note: str | None = None

    @property
    def revertible(self) -> bool:
        return self.operation in REVERT_STRATEGIES and self.reverted_by is None

    def summary(self) -> dict[str, Any]:
        """The shape an agent sees in a listing: enough to choose, not the payloads."""
        reason = IRREVERSIBLE.get(self.operation)
        return {
            "id": self.id,
            "at": self.at,
            "tool": self.tool,
            "operation": self.operation,
            "plan_id": self.plan_id,
            "entity_id": self.entity_id,
            "revertible": self.revertible,
            "revert_strategy": REVERT_STRATEGIES.get(self.operation),
            "not_revertible_because": reason,
            "reverted_by": self.reverted_by,
            "note": self.note,
        }

    def detail(self) -> dict[str, Any]:
        return {**self.summary(), "before": self.before, "after": self.after}


def _read_raw(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            # A truncated final line (killed mid-write) must not make the whole
            # history unreadable — the rest is still valid.
            continue
    return rows


def load() -> list[HistoryEntry]:
    """Every entry, oldest first."""
    return [HistoryEntry(**row) for row in _read_raw(history_path())]


def append(entry: HistoryEntry) -> HistoryEntry:
    path = history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(asdict(entry)) + "\n")
    _trim(path)
    return entry


def _trim(path: Path) -> None:
    rows = _read_raw(path)
    if len(rows) <= MAX_ENTRIES:
        return
    keep = rows[-MAX_ENTRIES:]
    path.write_text("".join(json.dumps(row) + "\n" for row in keep))


def get(entry_id: str) -> HistoryEntry | None:
    for entry in load():
        if entry.id == entry_id:
            return entry
    return None


def mark_reverted(entry_id: str, by_entry_id: str) -> None:
    """Record that an entry has been undone, so it is not undone twice."""
    path = history_path()
    rows = _read_raw(path)
    for row in rows:
        if row.get("id") == entry_id:
            row["reverted_by"] = by_entry_id
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def record(
    *,
    operation: str,
    tool: str,
    plan_id: str,
    entity_id: str | None = None,
    before: Any = None,
    after: Any = None,
    note: str | None = None,
) -> HistoryEntry:
    return append(
        HistoryEntry(
            operation=operation,
            tool=tool,
            plan_id=plan_id,
            entity_id=entity_id,
            before=before,
            after=after,
            note=note,
        )
    )
