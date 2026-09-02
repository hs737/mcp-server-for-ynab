"""What moved since last time.

YNAB's delta sync is on every list route already: pass `last_knowledge_of_server`
and get back only what changed. Almost nobody uses it, because using it means
knowing that the knowledge counter is plan-wide rather than per-route, threading
one integer through three separate calls, and reassembling the answer.

That cost lands exactly where it is least affordable. During a review the user
edits their budget in the app and asks the agent to look again — five times in
one session, on the plan this was written for — and each re-check costs a full
re-read of everything.

Called with no knowledge value this returns a baseline: the current counter and
nothing else. Call it once at the start, then pass the value back whenever you
need to know what the user changed.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp_server_for_ynab.enriched.multi_month import compact_category
from mcp_server_for_ynab.models.amounts import milliunits_to_display
from mcp_server_for_ynab.server.context import AppContext


async def changes_since(
    ctx: AppContext,
    plan_id: str,
    server_knowledge: int | None = None,
    *,
    limit: int = 200,
) -> dict[str, Any]:
    """Categories, months, and transactions that changed since a knowledge value."""
    categories_resp, months_resp, txn_resp = await asyncio.gather(
        ctx.categories.list(plan_id, last_knowledge_of_server=server_knowledge),
        ctx.months.list(plan_id, last_knowledge_of_server=server_knowledge),
        ctx.transactions.list(plan_id, last_knowledge_of_server=server_knowledge),
    )

    # The three routes share one plan-wide counter, so the highest value is the
    # one to carry forward — passing back a lower one would re-deliver changes
    # already seen.
    latest = max(
        categories_resp.data.server_knowledge,
        months_resp.data.server_knowledge,
        txn_resp.data.server_knowledge,
    )

    categories = [c for g in categories_resp.data.category_groups for c in g.categories if not c.deleted]
    months = [m for m in months_resp.data.months if not m.deleted]
    transactions = [t for t in txn_resp.data.transactions if not t.deleted]

    baseline = server_knowledge is None
    result: dict[str, Any] = {
        "scope": "changes_since",
        "plan_id": plan_id,
        "requested_server_knowledge": server_knowledge,
        "server_knowledge": latest,
        "baseline": baseline,
        "changed_category_count": len(categories),
        "changed_month_count": len(months),
        "changed_transaction_count": len(transactions),
        "amounts": "milliunits (1000 = $1.00)",
    }

    if baseline:
        result["note"] = (
            "No server_knowledge was given, so this is a baseline: the counts above are the whole plan, "
            f"not a change set. Pass server_knowledge={latest} next time to see only what moved."
        )
        return result

    result["categories"] = [compact_category(c) for c in categories[:limit]]
    result["months"] = [
        {
            "month": m.month,
            "income": m.income,
            "budgeted": m.budgeted,
            "activity": m.activity,
            "to_be_budgeted": m.to_be_budgeted,
        }
        for m in months[:limit]
    ]
    result["transactions"] = [
        {
            "id": t.id,
            "date": t.date,
            "amount": t.amount,
            "amount_display": milliunits_to_display(t.amount),
            "payee_name": t.payee_name,
            "account_name": t.account_name,
            "category_name": t.category_name,
            "cleared": t.cleared,
            "approved": t.approved,
        }
        for t in transactions[:limit]
    ]
    result["truncated"] = any(len(items) > limit for items in (categories, months, transactions))
    result["note"] = (
        "Delta sync reports records that changed, not how they changed — a category listed here was "
        "touched, and the values shown are its current ones. Deleted records are omitted. "
        f"Pass server_knowledge={latest} on the next call."
    )
    return result
