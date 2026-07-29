from __future__ import annotations

from mcp_server_for_ynab.models.ynab.categories import Category
from mcp_server_for_ynab.models.ynab.common import YnabBaseModel


class Month(YnabBaseModel):
    month: str  # ISO date string YYYY-MM-DD (first of the month)
    note: str | None = None
    income: int  # milliunits
    budgeted: int  # milliunits
    activity: int  # milliunits
    to_be_budgeted: int  # milliunits
    age_of_money: int | None = None
    deleted: bool
    categories: list[Category] = []  # noqa: RUF012


class MonthSummary(YnabBaseModel):
    month: str
    note: str | None = None
    income: int  # milliunits
    budgeted: int  # milliunits
    activity: int  # milliunits
    to_be_budgeted: int  # milliunits
    age_of_money: int | None = None
    deleted: bool


class MonthsResponse(YnabBaseModel):
    data: MonthsData


class MonthsData(YnabBaseModel):
    months: list[MonthSummary]
    server_knowledge: int


class MonthResponse(YnabBaseModel):
    data: MonthData


class MonthData(YnabBaseModel):
    month: Month
