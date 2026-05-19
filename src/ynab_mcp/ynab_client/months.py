from __future__ import annotations

from ynab_mcp.models.ynab.months import MonthResponse, MonthsResponse
from ynab_mcp.ynab_client.base import BaseClient


class MonthsClient(BaseClient):
    async def list(self, plan_id: str, *, last_knowledge_of_server: int | None = None) -> MonthsResponse:
        """GET /budgets/{id}/months — [READ] List all budget months (summaries)."""
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(f"/budgets/{plan_id}/months", params=params or None)
        return MonthsResponse.model_validate(data)

    async def get(self, plan_id: str, month: str) -> MonthResponse:
        """GET /budgets/{id}/months/{month} — [READ] Get full month data including all categories.

        month: ISO date string for the first day of the month, e.g. '2024-01-01'.
        Use 'current' as a convenience alias for the current month.
        """
        data = await self._http.get(f"/budgets/{plan_id}/months/{month}")
        return MonthResponse.model_validate(data)
