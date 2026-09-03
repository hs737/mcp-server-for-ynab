"""Write tools that compose several YNAB calls into one decision.

YNAB's API assigns money one category-month at a time. That is the right
primitive for the API and the wrong one for the work: applying a month's plan
is thirty-five separate writes, and moving money between two categories is two
writes whose amounts the caller has to compute from carried balances without
getting the arithmetic wrong.

Both tools here are ordinary writes underneath — nothing hidden, nothing
inferred — but each is journaled as a single history entry, so what was applied
as one decision can be undone as one decision. That is the part the API cannot
offer and the part a partial failure makes matter: a plan half-applied and
half-reverted is worse than either.

Neither is atomic, because YNAB has no transaction boundary. Each returns what
was applied, what failed, and the history entry that can put it back.
"""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from mcp_server_for_ynab.enriched.multi_month import normalize_month
from mcp_server_for_ynab.history import journal
from mcp_server_for_ynab.models.amounts import milliunits_to_display
from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpError, YnabMcpException
from mcp_server_for_ynab.models.ynab.categories import SaveCategory, SaveCategoryWrapper
from mcp_server_for_ynab.server.context import AppContext, get_app_context
from mcp_server_for_ynab.server.registry import tool_registry
from mcp_server_for_ynab.server.tools.boundary import tool_handler
from mcp_server_for_ynab.server.tools.registration import write_tool

# A month has as many lines as it has categories. Beyond a couple of hundred
# writes the rate budget is the binding constraint, not the tool.
MAX_ASSIGNMENTS = 100

tool_registry.register(
    "months_assign_many",
    "months",
    "write",
    "enriched",
    "Apply many category assignments for one month as a single revertible write. [WRITE]",
)
tool_registry.register(
    "money_move",
    "money_movements",
    "write",
    "enriched",
    "Move available money between two categories in a month. [WRITE]",
)


def _fail(message: str) -> YnabMcpException:
    return YnabMcpException(YnabMcpError(error_type=ErrorType.VALIDATION_ERROR, message=message))


async def _budgeted_now(ctx: AppContext, plan_id: str, month: str, category_id: str) -> tuple[int, str]:
    """The category's current budgeted amount for a month, and its name."""
    response = await ctx.categories.get_for_month(plan_id, month, category_id)
    return response.data.category.budgeted, response.data.category.name


@write_tool(
    name="months_assign_many",
    description=(
        "[WRITE] Set the budgeted amount of many categories for one month, in a single journaled "
        "write. Use this to apply a whole month's plan: building one by calling "
        "categories_update_for_month thirty-five times is thirty-five history entries that have to "
        "be undone one at a time. "
        "month: ISO date for the first of the month ('2024-01-01'), 'YYYY-MM', or 'current'. "
        "assignments: a list of {category_id, budgeted} objects. budgeted is the new total assigned "
        "for that category in that month, in milliunits (1000 = $1.00) — it replaces the current "
        "amount, it is not added to it. To move money between categories instead, use money_move. "
        "NOT atomic: YNAB has no transaction boundary, so check applied and failed in the response. "
        "This write is journaled — history_revert on the returned history_entry_id restores every "
        "category's previous amount in one step."
    ),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
)
@tool_handler
async def months_assign_many(
    month: str,
    assignments: list[dict[str, Any]],
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    target = normalize_month(month)

    if not assignments:
        raise _fail("assignments is empty. Pass at least one {category_id, budgeted} object.")
    if len(assignments) > MAX_ASSIGNMENTS:
        raise _fail(
            f"{len(assignments)} assignments is more than the {MAX_ASSIGNMENTS} this tool applies at once. "
            "Each one is a request against YNAB's hourly limit of 200. Split the plan."
        )

    parsed: list[tuple[str, int]] = []
    seen: set[str] = set()
    for index, item in enumerate(assignments):
        category_id = item.get("category_id")
        budgeted = item.get("budgeted")
        if not isinstance(category_id, str) or not category_id:
            raise _fail(f"assignments[{index}] has no category_id.")
        if not isinstance(budgeted, int) or isinstance(budgeted, bool):
            raise _fail(
                f"assignments[{index}] budgeted must be a whole number of milliunits (1000 = $1.00); got {budgeted!r}."
            )
        if category_id in seen:
            raise _fail(
                f"assignments[{index}] repeats category_id {category_id}. "
                "Two amounts for one category in one month is ambiguous; send the final amount once."
            )
        seen.add(category_id)
        parsed.append((category_id, budgeted))

    before: list[dict[str, Any]] = []
    applied: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    for category_id, budgeted in parsed:
        try:
            previous, name = await _budgeted_now(ctx, resolved, target, category_id)
        except Exception as exc:
            # Without a before-state this line cannot be reverted, so it is not
            # attempted: a plan that can only be half-undone is worse than one
            # line short.
            failed.append(
                {
                    "category_id": category_id,
                    "error": f"Could not read the current amount, so the change was not made: {exc}",
                }
            )
            continue

        try:
            result = await ctx.categories.update_for_month(
                resolved,
                target,
                category_id,
                SaveCategoryWrapper(category=SaveCategory(budgeted=budgeted)),
            )
        except Exception as exc:
            failed.append({"category_id": category_id, "name": name, "error": str(exc)})
            continue

        before.append({"id": category_id, "month": target, "budgeted": previous})
        stored = result.data.category.budgeted
        applied.append(
            {
                "category_id": category_id,
                "name": name,
                "previous_budgeted": previous,
                "budgeted": stored,
                "budgeted_display": milliunits_to_display(stored),
                "change": stored - previous,
                "verified": stored == budgeted,
            }
        )

    entry = journal.record(
        operation="category_month_budget_batch",
        tool="months_assign_many",
        plan_id=resolved,
        entity_id=None,
        before=before,
        after=[{"id": row["category_id"], "month": target, "budgeted": row["budgeted"]} for row in applied],
        note=f"{len(applied)} of {len(parsed)} assignments applied for {target}.",
    )

    unverified = [row["category_id"] for row in applied if not row["verified"]]
    verification: dict[str, Any] = {
        "requested_count": len(parsed),
        "applied_count": len(applied),
        "failed_count": len(failed),
        "verified": not unverified and not failed,
    }
    if unverified:
        verification["stored_a_different_amount"] = unverified
        verification["warning"] = (
            "YNAB accepted these but stored a different amount. Re-read them before relying on it."
        )

    return {
        "scope": "months_assign_many",
        "plan_id": resolved,
        "month": target,
        "total_assigned": sum(int(row["budgeted"]) for row in applied),
        "total_assigned_display": milliunits_to_display(sum(int(row["budgeted"]) for row in applied)),
        "applied": applied,
        "failed": failed,
        "history_entry_id": entry.id,
        "verification": verification,
    }


@write_tool(
    name="money_move",
    description=(
        "[WRITE] Move available money from one category to another within a month, the way YNAB's "
        "'move money' does. Pass null for from_category_id to take the money from Ready to Assign, "
        "or null for to_category_id to send it back there. "
        "amount: how much to move, a positive number of milliunits (1000 = $1.00). "
        "month: ISO date for the first of the month ('2024-01-01'), 'YYYY-MM', or 'current'. "
        "Underneath this adjusts each category's budgeted amount, which is what a move is in YNAB — "
        "the point of the tool is that it reads the current amounts and does that arithmetic, so a "
        "carried-forward balance cannot be mistaken for the assigned amount. "
        "Both sides are journaled as one entry; history_revert puts the money back."
    ),
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False),
)
@tool_handler
async def money_move(
    month: str,
    amount: int,
    from_category_id: str | None = None,
    to_category_id: str | None = None,
    plan_id: str | None = None,
) -> dict[str, Any]:
    ctx = get_app_context()
    resolved = ctx.settings.resolve_plan_id(plan_id)
    target = normalize_month(month)

    if amount <= 0:
        raise _fail(
            f"amount must be a positive number of milliunits; got {amount}. "
            "The direction comes from from_category_id and to_category_id, not from the sign."
        )
    if from_category_id is None and to_category_id is None:
        raise _fail(
            "Both sides are Ready to Assign, so there is nothing to move. "
            "Set from_category_id, to_category_id, or both."
        )
    if from_category_id == to_category_id:
        raise _fail("from_category_id and to_category_id are the same category.")

    before: list[dict[str, Any]] = []
    moves: list[dict[str, Any]] = []
    failure: dict[str, Any] | None = None

    # The source is reduced first. If the second write then fails the money is
    # unassigned rather than assigned twice, and Ready to Assign is where an
    # unexplained sum is easiest to notice.
    #
    # A failure part-way is caught rather than raised, because the first write
    # has already happened: raising would lose the before-state that is the only
    # way back, and this is exactly the case where a revert is needed.
    for category_id, delta in ((from_category_id, -amount), (to_category_id, amount)):
        if category_id is None:
            continue
        try:
            previous, name = await _budgeted_now(ctx, resolved, target, category_id)
            result = await ctx.categories.update_for_month(
                resolved,
                target,
                category_id,
                SaveCategoryWrapper(category=SaveCategory(budgeted=previous + delta)),
            )
        except Exception as exc:
            failure = {
                "category_id": category_id,
                "side": "from" if delta < 0 else "to",
                "error": str(exc),
            }
            break

        before.append({"id": category_id, "month": target, "budgeted": previous})
        stored = result.data.category.budgeted
        moves.append(
            {
                "category_id": category_id,
                "name": name,
                "direction": "from" if delta < 0 else "to",
                "previous_budgeted": previous,
                "budgeted": stored,
                "budgeted_display": milliunits_to_display(stored),
                "balance": result.data.category.balance,
                "balance_display": milliunits_to_display(result.data.category.balance),
                "verified": stored == previous + delta,
            }
        )

    entry = journal.record(
        operation="category_month_budget_batch",
        tool="money_move",
        plan_id=resolved,
        entity_id=None,
        before=before,
        after=[{"id": row["category_id"], "month": target, "budgeted": row["budgeted"]} for row in moves],
        note=(
            f"Moved {milliunits_to_display(amount)} in {target} "
            f"from {from_category_id or 'Ready to Assign'} to {to_category_id or 'Ready to Assign'}."
            + (" One side failed; this entry restores what was written." if failure else "")
        ),
    )

    unverified = [row["category_id"] for row in moves if not row["verified"]]
    expected_sides = sum(1 for side in (from_category_id, to_category_id) if side is not None)
    verification: dict[str, Any] = {
        "verified": not unverified and failure is None,
        "sides_written": len(moves),
        "sides_expected": expected_sides,
    }
    if unverified:
        verification["stored_a_different_amount"] = unverified
        verification["warning"] = "YNAB stored a different amount for these. The move did not fully take effect."
    if failure is not None:
        verification["failed_side"] = failure
        verification["warning"] = (
            "Only one side of the move was written, so the money left its category without arriving. "
            f"Revert history entry {entry.id} to put it back, then retry."
        )

    return {
        "scope": "money_move",
        "plan_id": resolved,
        "month": target,
        "amount": amount,
        "amount_display": milliunits_to_display(amount),
        "from_category_id": from_category_id,
        "to_category_id": to_category_id,
        "moved": moves,
        "history_entry_id": entry.id,
        "verification": verification,
    }
