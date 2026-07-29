from __future__ import annotations

from mcp_server_for_ynab.models.ynab.common import YnabBaseModel


class CurrencyFormat(YnabBaseModel):
    iso_code: str
    example_format: str
    decimal_digits: int
    decimal_separator: str
    symbol_first: bool
    group_separator: str
    currency_symbol: str
    display_symbol: bool


class Plan(YnabBaseModel):
    id: str
    name: str
    last_modified_on: str | None = None
    first_month: str | None = None
    last_month: str | None = None
    date_format: dict[str, str] | None = None
    currency_format: CurrencyFormat | None = None
    accounts: list[dict[str, object]] | None = None


class PlanSummary(YnabBaseModel):
    id: str
    name: str
    last_modified_on: str | None = None


class PlanSettings(YnabBaseModel):
    date_format: dict[str, str]
    currency_format: CurrencyFormat


class PlanResponse(YnabBaseModel):
    data: PlanData


class PlanData(YnabBaseModel):
    budget: Plan
    server_knowledge: int


class PlansResponse(YnabBaseModel):
    data: PlansData


class PlansData(YnabBaseModel):
    budgets: list[PlanSummary]
    default_budget: PlanSummary | None = None


class PlanSettingsResponse(YnabBaseModel):
    data: PlanSettingsData


class PlanSettingsData(YnabBaseModel):
    settings: PlanSettings
