from __future__ import annotations

from ynab_mcp.models.ynab.scheduled_transactions import (
    SaveScheduledTransactionWrapper,
    ScheduledTransactionResponse,
    ScheduledTransactionsResponse,
)
from ynab_mcp.ynab_client.base import BaseClient


class ScheduledTransactionsClient(BaseClient):
    async def list(
        self, plan_id: str, *, last_knowledge_of_server: int | None = None
    ) -> ScheduledTransactionsResponse:
        """GET /budgets/{id}/scheduled_transactions — [READ] List scheduled transactions."""
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(
            f"/budgets/{plan_id}/scheduled_transactions", params=params or None
        )
        return ScheduledTransactionsResponse.model_validate(data)

    async def get(
        self, plan_id: str, scheduled_transaction_id: str
    ) -> ScheduledTransactionResponse:
        """GET /budgets/{id}/scheduled_transactions/{id} — [READ] Get a scheduled transaction."""
        data = await self._http.get(
            f"/budgets/{plan_id}/scheduled_transactions/{scheduled_transaction_id}"
        )
        return ScheduledTransactionResponse.model_validate(data)

    async def create(
        self, plan_id: str, payload: SaveScheduledTransactionWrapper
    ) -> ScheduledTransactionResponse:
        """POST /budgets/{id}/scheduled_transactions — [WRITE] Create a scheduled transaction.

        All amounts must be in milliunits (1000 = $1.00).
        """
        data = await self._http.post(
            f"/budgets/{plan_id}/scheduled_transactions",
            json=payload.model_dump(exclude_none=True),
        )
        return ScheduledTransactionResponse.model_validate(data)

    async def update(
        self,
        plan_id: str,
        scheduled_transaction_id: str,
        payload: SaveScheduledTransactionWrapper,
    ) -> ScheduledTransactionResponse:
        """PUT /budgets/{id}/scheduled_transactions/{id} — [WRITE] Update a scheduled transaction."""
        data = await self._http.put(
            f"/budgets/{plan_id}/scheduled_transactions/{scheduled_transaction_id}",
            json=payload.model_dump(exclude_none=True),
        )
        return ScheduledTransactionResponse.model_validate(data)

    async def delete(
        self, plan_id: str, scheduled_transaction_id: str
    ) -> ScheduledTransactionResponse:
        """DELETE /budgets/{id}/scheduled_transactions/{id} — [WRITE] Delete a scheduled transaction."""
        data = await self._http.delete(
            f"/budgets/{plan_id}/scheduled_transactions/{scheduled_transaction_id}"
        )
        return ScheduledTransactionResponse.model_validate(data)
