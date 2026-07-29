from __future__ import annotations

from mcp_server_for_ynab.models.ynab.user import UserResponse
from mcp_server_for_ynab.ynab_client.base import BaseClient


class UserClient(BaseClient):
    async def get(self) -> UserResponse:
        """GET /user — [READ] Returns the authenticated YNAB user."""
        data = await self._http.get("/user")
        return UserResponse.model_validate(data)
