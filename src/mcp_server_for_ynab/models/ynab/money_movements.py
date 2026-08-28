"""Money movement shapes.

A money movement records budgeted funds moving between categories within a
month — not a transaction. It has no date, payee, or account; it has the month
it applies to, the moment it was performed, and the two category endpoints.

`from_category_id` and `to_category_id` are independently nullable: a null side
means the funds came from, or went to, Ready to Assign.

A money movement group ties several movements together (one "move money"
action that touched multiple categories). The group carries no amount of its
own and does not embed its movements — join on `money_movement_group_id`.

Field names and nullability here were taken from live API responses. Do not
infer them from the transaction shapes; the two resources differ.
"""

from __future__ import annotations

from mcp_server_for_ynab.models.ynab.common import DecodedTextModel, YnabBaseModel


class MoneyMovement(DecodedTextModel):
    id: str
    month: str  # ISO date for the first day of the month, e.g. "2026-06-01"
    moved_at: str  # ISO 8601 UTC timestamp
    amount: int  # milliunits
    amount_formatted: str | None = None  # pre-formatted in the plan's currency, e.g. "$500.00"
    amount_currency: float | None = None  # amount as a currency value, e.g. 500.0
    from_category_id: str | None = None  # null means Ready to Assign
    to_category_id: str | None = None  # null means Ready to Assign
    money_movement_group_id: str | None = None
    performed_by_user_id: str | None = None
    note: str | None = None
    deleted: bool = False


class MoneyMovementGroup(DecodedTextModel):
    id: str
    month: str  # ISO date for the first day of the month
    group_created_at: str  # ISO 8601 UTC timestamp
    performed_by_user_id: str | None = None
    note: str | None = None
    deleted: bool = False


class MoneyMovementsData(YnabBaseModel):
    money_movements: list[MoneyMovement]
    server_knowledge: int


class MoneyMovementsResponse(YnabBaseModel):
    data: MoneyMovementsData


class MoneyMovementGroupsData(YnabBaseModel):
    money_movement_groups: list[MoneyMovementGroup]
    server_knowledge: int


class MoneyMovementGroupsResponse(YnabBaseModel):
    data: MoneyMovementGroupsData
