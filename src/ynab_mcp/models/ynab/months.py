from __future__ import annotations

from ynab_mcp.models.ynab.categories import Category
from ynab_mcp.models.ynab.common import YnabBaseModel


class Month(YnabBaseModel):
    month: str  # ISO date string YYYY-MM-DD (first of the month)
    note: str | None = None
    income: int  # milliunits
    budgeted: int  # milliunits
    activity: int  # milliunits
    to_be_budgeted: int  # milliunits
    age_of_money: int | None = None
    deleted: bool
    categories: list[Category] = []


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
