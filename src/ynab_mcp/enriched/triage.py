"""Enriched triage tools: uncategorized and unapproved transaction queues."""

from __future__ import annotations

from datetime import date
from typing import Any

from ynab_mcp.models.amounts import milliunits_to_display
from ynab_mcp.server.context import AppContext


async def triage_uncategorized(ctx: AppContext, plan_id: str) -> dict[str, Any]:
    """Return all uncategorized transactions, most-recent first."""
    resp = await ctx.transactions.list(plan_id, type="uncategorized")
    txns = [t for t in resp.data.transactions if not t.deleted]
    txns.sort(key=lambda t: t.date, reverse=True)

    return {
        "scope": "triage_uncategorized",
        "plan_id": plan_id,
        "count": len(txns),
        "server_knowledge": resp.data.server_knowledge,
        "transactions": [_slim(t) for t in txns],
    }


async def triage_unapproved(ctx: AppContext, plan_id: str) -> dict[str, Any]:
    """Return all unapproved transactions, most-recent first."""
    resp = await ctx.transactions.list(plan_id, type="unapproved")
    txns = [t for t in resp.data.transactions if not t.deleted]
    txns.sort(key=lambda t: t.date, reverse=True)

    return {
        "scope": "triage_unapproved",
        "plan_id": plan_id,
        "count": len(txns),
        "server_knowledge": resp.data.server_knowledge,
        "transactions": [_slim(t) for t in txns],
    }


async def triage_summary(ctx: AppContext, plan_id: str) -> dict[str, Any]:
    """Combined count of pending work: uncategorized + unapproved transactions."""
    import asyncio

    uncategorized_resp, unapproved_resp = await asyncio.gather(
        ctx.transactions.list(plan_id, type="uncategorized"),
        ctx.transactions.list(plan_id, type="unapproved"),
    )
    uncategorized = [t for t in uncategorized_resp.data.transactions if not t.deleted]
    unapproved = [t for t in unapproved_resp.data.transactions if not t.deleted]

    today = date.today().isoformat()
    return {
        "scope": "triage_summary",
        "plan_id": plan_id,
        "as_of": today,
        "uncategorized_count": len(uncategorized),
        "unapproved_count": len(unapproved),
        "total_pending": len(uncategorized) + len(unapproved),
        "needs_attention": len(uncategorized) > 0 or len(unapproved) > 0,
    }


def _slim(t: object) -> dict[str, Any]:
    from ynab_mcp.models.ynab.transactions import Transaction

    assert isinstance(t, Transaction)
    return {
        "id": t.id,
        "date": t.date,
        "amount": t.amount,
        "amount_display": milliunits_to_display(t.amount),
        "payee_name": t.payee_name,
        "account_name": t.account_name,
        "category_id": t.category_id,
        "category_name": t.category_name,
        "memo": t.memo,
        "cleared": t.cleared,
        "approved": t.approved,
        "import_payee_name": t.import_payee_name,
    }
