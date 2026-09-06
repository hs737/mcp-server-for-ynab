"""Trimming list items down to what the caller actually reads.

A transaction as YNAB returns it is about 1.4 KB, and most of that is absence:
`flag_color`, `flag_name`, `debt_transaction_type`, `import_payee_name_original`
and an empty `subtransactions` list are present on nearly every row and empty on
nearly every row. Five hundred of them is 150 KB — past the point where a client
holds a tool result in the conversation at all, so the reviewer ends up parsing
the answer off disk.

Two reductions, in order of how much they save:

`fields` projects each item down to the columns named. A reconciliation needs
date, amount, cleared and import_id; it does not need the goal fields of the
category the transaction is in. Naming the columns is how a caller says so, and
`id` comes along whether or not it was asked for, because a row you cannot then
act on is not worth returning.

Empty values are dropped from every item regardless. This one needs stating in
the response rather than only here: a *missing* `category_id` means the
transaction is uncategorized, not that the field was withheld — which is the
same thing YNAB means by null, and the reason dropping it is safe.
"""

from __future__ import annotations

from typing import Any

from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpError, YnabMcpException

# Without this a projection can hand back rows that cannot be updated, matched
# to a journal entry, or fetched again.
ALWAYS_KEPT = ("id",)

EMPTY_FIELDS_NOTE = (
    "Fields that are null or empty are omitted from each item. A missing category_id therefore "
    "means the transaction is uncategorized, and a missing subtransactions list means it is not a "
    "split."
)


def fields_help(example: str) -> str:
    """The `fields` sentence for a tool description.

    The full list of names is not repeated here. It is on the item shape the
    tool returns, and an unknown name comes back as a validation error that
    names every valid one — which is a better place for a list of twenty-four
    strings than five tool descriptions.
    """
    return (
        "fields: name the columns you need and each item is projected down to them, which is where "
        f"the size of a long list actually goes — fields=['{example}'] is a fraction of the full "
        "row. id is always included, and an unknown name is refused with the list of valid ones. " + EMPTY_FIELDS_NOTE
    )


def validate_fields(fields: list[str] | None, allowed: tuple[str, ...]) -> tuple[str, ...] | None:
    """Check requested field names, or explain which ones do not exist.

    An unknown name is refused rather than ignored: silently returning rows
    without the column the caller asked for reads as "YNAB has no value for
    this", which is a different and much more expensive conclusion.
    """
    if fields is None:
        return None

    names = [name.strip() for name in fields if name and name.strip()]
    if not names:
        return None

    unknown = sorted({name for name in names if name not in allowed})
    if unknown:
        raise YnabMcpException(
            YnabMcpError(
                error_type=ErrorType.VALIDATION_ERROR,
                message=(
                    f"Unknown field(s) in fields: {', '.join(unknown)}. Available fields are: {', '.join(allowed)}."
                ),
            )
        )

    return tuple(dict.fromkeys([*ALWAYS_KEPT, *names]))


def _is_empty(value: Any) -> bool:
    return value is None or value == [] or value == {}


def strip_empty(value: Any) -> Any:
    """Drop null and empty members, recursively, from dicts and lists."""
    if isinstance(value, dict):
        return {k: strip_empty(v) for k, v in value.items() if not _is_empty(v)}
    if isinstance(value, list):
        return [strip_empty(item) for item in value]
    return value


def project_item(item: Any, fields: tuple[str, ...] | None) -> Any:
    """One serialized item, reduced to `fields` and with its empty values dropped."""
    if not isinstance(item, dict):
        return item
    chosen = {k: v for k, v in item.items() if k in fields} if fields else item
    return strip_empty(chosen)
