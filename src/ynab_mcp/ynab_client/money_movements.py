from __future__ import annotations

from ynab_mcp.models.ynab.money_movements import (
    MoneyMovementGroupsResponse,
    MoneyMovementsResponse,
)
from ynab_mcp.ynab_client.base import BaseClient


class MoneyMovementsClient(BaseClient):
    async def list(self, plan_id: str, *, last_knowledge_of_server: int | None = None) -> MoneyMovementsResponse:
        """GET /budgets/{id}/money_movements — [READ] List all money movements."""
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(f"/budgets/{plan_id}/money_movements", params=params or None)
        return MoneyMovementsResponse.model_validate(data)

    async def list_by_month(
        self, plan_id: str, month: str, *, last_knowledge_of_server: int | None = None
    ) -> MoneyMovementsResponse:
        """GET /budgets/{id}/months/{month}/money_movements — [READ]"""
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(f"/budgets/{plan_id}/months/{month}/money_movements", params=params or None)
        return MoneyMovementsResponse.model_validate(data)

    async def list_groups(
        self, plan_id: str, *, last_knowledge_of_server: int | None = None
    ) -> MoneyMovementGroupsResponse:
        """GET /budgets/{id}/money_movement_groups — [READ] List money movement groups."""
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(f"/budgets/{plan_id}/money_movement_groups", params=params or None)
        return MoneyMovementGroupsResponse.model_validate(data)

    async def list_groups_by_month(
        self, plan_id: str, month: str, *, last_knowledge_of_server: int | None = None
    ) -> MoneyMovementGroupsResponse:
        """GET /budgets/{id}/months/{month}/money_movement_groups — [READ]"""
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(
            f"/budgets/{plan_id}/months/{month}/money_movement_groups",
            params=params or None,
        )
        return MoneyMovementGroupsResponse.model_validate(data)
