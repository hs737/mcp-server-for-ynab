"""Enriched bookkeeping tools: category suggestions, memo suggestions, transaction history."""

from __future__ import annotations

from collections import Counter
from typing import Any

from mcp_server_for_ynab.models.amounts import milliunits_to_display
from mcp_server_for_ynab.server.context import AppContext


async def categorization_suggestions(ctx: AppContext, plan_id: str) -> dict[str, Any]:
    """Suggest categories for uncategorized transactions using payee history.

    For each uncategorized transaction, looks up the most-common category
    that payee has been assigned in historical cleared transactions.
    """
    import asyncio

    uncategorized_resp, all_resp = await asyncio.gather(
        ctx.transactions.list(plan_id, type="uncategorized"),
        ctx.transactions.list(plan_id),
    )

    uncategorized = [t for t in uncategorized_resp.data.transactions if not t.deleted]
    all_txns = [t for t in all_resp.data.transactions if not t.deleted]

    # Build payee → category frequency map from cleared/categorized history
    payee_category: dict[str, Counter[str]] = {}
    for t in all_txns:
        if t.payee_id and t.category_id and t.category_name:
            payee_category.setdefault(t.payee_id, Counter())[t.category_name] += 1

    suggestions = []
    for t in uncategorized:
        suggestion: dict[str, Any] = {
            "transaction_id": t.id,
            "date": t.date,
            "amount": t.amount,
            "amount_display": milliunits_to_display(t.amount),
            "payee_name": t.payee_name,
            "account_name": t.account_name,
            "suggested_category": None,
            "confidence": "none",
            "alternatives": [],
        }

        if t.payee_id and t.payee_id in payee_category:
            counts = payee_category[t.payee_id]
            total = sum(counts.values())
            top = counts.most_common(3)
            best_name, best_count = top[0]
            ratio = best_count / total

            suggestion["suggested_category"] = best_name
            if ratio >= 0.8:
                suggestion["confidence"] = "high"
            elif ratio >= 0.5:
                suggestion["confidence"] = "medium"
            else:
                suggestion["confidence"] = "low"
            suggestion["alternatives"] = [{"category_name": n, "count": c} for n, c in top[1:]]

        suggestions.append(suggestion)

    actionable = sum(1 for s in suggestions if s["suggested_category"] is not None)
    return {
        "scope": "categorization_suggestions",
        "plan_id": plan_id,
        "uncategorized_count": len(uncategorized),
        "actionable_count": actionable,
        "suggestions": suggestions,
        "server_knowledge": uncategorized_resp.data.server_knowledge,
    }


async def memo_annotation_suggestions(ctx: AppContext, plan_id: str, since_date: str | None = None) -> dict[str, Any]:
    """Identify transactions that lack memos but probably need them.

    Flags large transactions (>= $50) and split transactions without memos.
    """
    resp = await ctx.transactions.list(plan_id, since_date=since_date)
    txns = [t for t in resp.data.transactions if not t.deleted]

    LARGE_THRESHOLD = 50_000  # $50 in milliunits

    candidates = []
    for t in txns:
        if t.memo:
            continue
        is_large = abs(t.amount) >= LARGE_THRESHOLD
        is_split = bool(t.subtransactions)
        if not (is_large or is_split):
            continue

        candidates.append(
            {
                "transaction_id": t.id,
                "date": t.date,
                "amount": t.amount,
                "amount_display": milliunits_to_display(t.amount),
                "payee_name": t.payee_name,
                "category_name": t.category_name,
                "account_name": t.account_name,
                "reason": "split" if is_split else "large",
            }
        )

    candidates.sort(key=lambda c: abs(c["amount"]), reverse=True)  # type: ignore[arg-type]
    return {
        "scope": "memo_annotation_suggestions",
        "plan_id": plan_id,
        "since_date": since_date,
        "candidate_count": len(candidates),
        "candidates": candidates[:50],
        "server_knowledge": resp.data.server_knowledge,
    }


async def transaction_history(
    ctx: AppContext,
    plan_id: str,
    *,
    since_date: str | None = None,
    payee_id: str | None = None,
    category_id: str | None = None,
    account_id: str | None = None,
) -> dict[str, Any]:
    """Retrieve recent transactions with optional scope filters.

    Pass at most one of payee_id / category_id / account_id for a scoped
    list; pass none for the full budget history (filtered by since_date).
    """
    if payee_id:
        resp = await ctx.transactions.list_by_payee(plan_id, payee_id, since_date=since_date)
    elif category_id:
        resp = await ctx.transactions.list_by_category(plan_id, category_id, since_date=since_date)
    elif account_id:
        resp = await ctx.transactions.list_by_account(plan_id, account_id, since_date=since_date)
    else:
        resp = await ctx.transactions.list(plan_id, since_date=since_date)

    txns = [t for t in resp.data.transactions if not t.deleted]
    txns.sort(key=lambda t: t.date, reverse=True)

    total_inflow = sum(t.amount for t in txns if t.amount > 0)
    total_outflow = sum(t.amount for t in txns if t.amount < 0)

    return {
        "scope": "transaction_history",
        "plan_id": plan_id,
        "since_date": since_date,
        "payee_id": payee_id,
        "category_id": category_id,
        "account_id": account_id,
        "count": len(txns),
        "total_inflow": total_inflow,
        "total_inflow_display": milliunits_to_display(total_inflow),
        "total_outflow": total_outflow,
        "total_outflow_display": milliunits_to_display(total_outflow),
        "net": total_inflow + total_outflow,
        "net_display": milliunits_to_display(total_inflow + total_outflow),
        "server_knowledge": resp.data.server_knowledge,
        "transactions": [
            {
                "id": t.id,
                "date": t.date,
                "amount": t.amount,
                "amount_display": milliunits_to_display(t.amount),
                "payee_name": t.payee_name,
                "category_name": t.category_name,
                "account_name": t.account_name,
                "memo": t.memo,
                "cleared": t.cleared,
                "approved": t.approved,
            }
            for t in txns
        ],
    }
