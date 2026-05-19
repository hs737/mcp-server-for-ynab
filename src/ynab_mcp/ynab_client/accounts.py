from __future__ import annotations

from ynab_mcp.models.ynab.accounts import (
    AccountResponse,
    AccountResponseWrapper,
    AccountsResponse,
    SaveAccountWrapper,
)
from ynab_mcp.ynab_client.base import BaseClient


class AccountsClient(BaseClient):
    async def list(self, plan_id: str, *, last_knowledge_of_server: int | None = None) -> AccountsResponse:
        """GET /budgets/{id}/accounts — [READ] List all accounts for a plan."""
        params = {}
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(f"/budgets/{plan_id}/accounts", params=params or None)
        return AccountsResponse.model_validate(data)

    async def get(self, plan_id: str, account_id: str) -> AccountResponse:
        """GET /budgets/{id}/accounts/{account_id} — [READ] Get a single account."""
        data = await self._http.get(f"/budgets/{plan_id}/accounts/{account_id}")
        return AccountResponse.model_validate(data)

    async def create(self, plan_id: str, payload: SaveAccountWrapper) -> AccountResponseWrapper:
        """POST /budgets/{id}/accounts — [WRITE] Create a new account."""
        data = await self._http.post(
            f"/budgets/{plan_id}/accounts",
            json=payload.model_dump(exclude_none=True),
        )
        return AccountResponseWrapper.model_validate(data)
