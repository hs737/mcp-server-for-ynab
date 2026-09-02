"""Client-side filters for transaction lists.

YNAB's transaction routes take `since_date` and a `type` of `uncategorized` or
`unapproved`, and nothing else. Every other question — what is still uncleared,
what was entered by hand, what is over $500 — has to be answered by fetching
the account's whole history and filtering it.

Doing that here rather than in the caller is not a convenience. The filtering
happens before pagination, so `total_available` counts matches instead of rows,
and the page the caller receives is a page of answers.
"""

from __future__ import annotations

from typing import Any

from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpError, YnabMcpException

CLEARED_VALUES = ("cleared", "uncleared", "reconciled")

FILTER_HELP = (
    "Filters applied before paging: cleared ('cleared', 'uncleared', 'reconciled'), "
    "approved (true/false), manual_only=true for transactions with no import_id (entered by hand), "
    "min_amount to keep only transactions whose absolute amount is at least that many milliunits."
)


def apply_transaction_filters(
    transactions: list[Any],
    *,
    cleared: str | None = None,
    approved: bool | None = None,
    manual_only: bool | None = None,
    min_amount: int | None = None,
) -> list[Any]:
    if cleared is not None and cleared not in CLEARED_VALUES:
        raise YnabMcpException(
            YnabMcpError(
                error_type=ErrorType.VALIDATION_ERROR,
                message=f"cleared must be one of {', '.join(CLEARED_VALUES)}; got {cleared!r}.",
            )
        )
    if min_amount is not None and min_amount < 0:
        raise YnabMcpException(
            YnabMcpError(
                error_type=ErrorType.VALIDATION_ERROR,
                message=(
                    "min_amount is an absolute size in milliunits and cannot be negative. "
                    "It keeps both inflows and outflows of at least that size."
                ),
            )
        )

    result = transactions
    if cleared is not None:
        result = [t for t in result if str(t.cleared) == cleared]
    if approved is not None:
        result = [t for t in result if t.approved is approved]
    if manual_only:
        result = [t for t in result if t.import_id is None]
    if min_amount:
        result = [t for t in result if abs(t.amount) >= min_amount]
    return result
