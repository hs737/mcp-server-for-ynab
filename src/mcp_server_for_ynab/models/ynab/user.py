from __future__ import annotations

from mcp_server_for_ynab.models.ynab.common import YnabBaseModel


class User(YnabBaseModel):
    id: str


class UserResponse(YnabBaseModel):
    data: UserData


class UserData(YnabBaseModel):
    user: User
