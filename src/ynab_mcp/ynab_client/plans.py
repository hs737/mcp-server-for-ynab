from __future__ import annotations

from ynab_mcp.models.ynab.plans import PlanResponse, PlanSettingsResponse, PlansResponse
from ynab_mcp.ynab_client.base import BaseClient


class PlansClient(BaseClient):
    async def list(self) -> PlansResponse:
        """GET /budgets — [READ] List all plans (budgets)."""
        data = await self._http.get("/budgets")
        return PlansResponse.model_validate(data)

    async def get(self, plan_id: str, *, last_knowledge_of_server: int | None = None) -> PlanResponse:
        """GET /budgets/{id} — [READ] Get a single plan with full detail.

        Pass last_knowledge_of_server for delta sync — only changed data is returned.
        The response includes server_knowledge for use in the next delta request.
        """
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(f"/budgets/{plan_id}", params=params or None)
        return PlanResponse.model_validate(data)

    async def get_settings(self, plan_id: str) -> PlanSettingsResponse:
        """GET /budgets/{id}/settings — [READ] Get plan settings (currency/date format).

        Note: this endpoint returns limited data. It is primarily useful for
        determining the currency symbol and date format used by the budget.
        """
        data = await self._http.get(f"/budgets/{plan_id}/settings")
        return PlanSettingsResponse.model_validate(data)
