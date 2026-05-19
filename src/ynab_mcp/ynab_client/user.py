from __future__ import annotations

from ynab_mcp.models.ynab.user import UserResponse
from ynab_mcp.ynab_client.base import BaseClient


class UserClient(BaseClient):
    async def get(self) -> UserResponse:
        """GET /user — [READ] Returns the authenticated YNAB user."""
        data = await self._http.get("/user")
        return UserResponse.model_validate(data)
