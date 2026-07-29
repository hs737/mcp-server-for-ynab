from __future__ import annotations

from mcp_server_for_ynab.models.ynab.common import YnabBaseModel


class Payee(YnabBaseModel):
    id: str
    name: str
    transfer_account_id: str | None = None
    deleted: bool


class PayeesResponse(YnabBaseModel):
    data: PayeesData


class PayeesData(YnabBaseModel):
    payees: list[Payee]
    server_knowledge: int


class PayeeResponse(YnabBaseModel):
    data: PayeeData


class PayeeData(YnabBaseModel):
    payee: Payee


class SavePayee(YnabBaseModel):
    name: str


class SavePayeeWrapper(YnabBaseModel):
    payee: SavePayee


class PayeeLocation(YnabBaseModel):
    id: str
    payee_id: str
    latitude: str | None = None
    longitude: str | None = None
    deleted: bool


class PayeeLocationsResponse(YnabBaseModel):
    data: PayeeLocationsData


class PayeeLocationsData(YnabBaseModel):
    payee_locations: list[PayeeLocation]


class PayeeLocationResponse(YnabBaseModel):
    data: PayeeLocationData


class PayeeLocationData(YnabBaseModel):
    payee_location: PayeeLocation
