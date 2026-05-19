from __future__ import annotations

from ynab_mcp.models.ynab.common import YnabBaseModel


class MoneyMovement(YnabBaseModel):
    id: str
    date: str  # ISO date YYYY-MM-DD
    amount: int  # milliunits
    payee_name: str | None = None
    account_name: str | None = None
    category_name: str | None = None
    memo: str | None = None


class MoneyMovementGroup(YnabBaseModel):
    id: str
    name: str
    amount: int  # milliunits
    money_movements: list[MoneyMovement] = []  # noqa: RUF012


class MoneyMovementsResponse(YnabBaseModel):
    data: MoneyMovementsData


class MoneyMovementsData(YnabBaseModel):
    money_movements: list[MoneyMovement]
    server_knowledge: int


class MoneyMovementGroupsResponse(YnabBaseModel):
    data: MoneyMovementGroupsData


class MoneyMovementGroupsData(YnabBaseModel):
    money_movement_groups: list[MoneyMovementGroup]
    server_knowledge: int
