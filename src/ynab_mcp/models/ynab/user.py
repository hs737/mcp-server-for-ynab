from __future__ import annotations

from ynab_mcp.models.ynab.common import YnabBaseModel


class User(YnabBaseModel):
    id: str


class UserResponse(YnabBaseModel):
    data: UserData


class UserData(YnabBaseModel):
    user: User
