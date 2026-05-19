from __future__ import annotations

from enum import StrEnum

from ynab_mcp.models.ynab.common import YnabBaseModel


class AccountType(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CASH = "cash"
    CREDIT_CARD = "creditCard"
    LINE_OF_CREDIT = "lineOfCredit"
    OTHER_ASSET = "otherAsset"
    OTHER_LIABILITY = "otherLiability"
    MORTGAGE = "mortgage"
    AUTO_LOAN = "autoLoan"
    STUDENT_LOAN = "studentLoan"
    PERSONAL_LOAN = "personalLoan"
    MEDICAL_DEBT = "medicalDebt"
    OTHER_DEBT = "otherDebt"


class Account(YnabBaseModel):
    id: str
    name: str
    type: AccountType
    on_budget: bool
    closed: bool
    note: str | None = None
    balance: int  # milliunits
    cleared_balance: int  # milliunits
    uncleared_balance: int  # milliunits
    transfer_payee_id: str
    direct_import_linked: bool | None = None
    direct_import_in_error: bool | None = None
    last_reconciled_at: str | None = None
    debt_original_balance: int | None = None  # milliunits
    debt_interest_rates: dict[str, object] | None = None
    debt_minimum_payments: dict[str, object] | None = None
    debt_escrow_amounts: dict[str, object] | None = None
    deleted: bool


class AccountsResponse(YnabBaseModel):
    data: AccountsData


class AccountsData(YnabBaseModel):
    accounts: list[Account]
    server_knowledge: int


class AccountResponse(YnabBaseModel):
    data: AccountData


class AccountData(YnabBaseModel):
    account: Account


class SaveAccount(YnabBaseModel):
    name: str
    type: AccountType
    balance: int  # milliunits — initial balance


class SaveAccountWrapper(YnabBaseModel):
    account: SaveAccount


class AccountResponseWrapper(YnabBaseModel):
    data: AccountData
