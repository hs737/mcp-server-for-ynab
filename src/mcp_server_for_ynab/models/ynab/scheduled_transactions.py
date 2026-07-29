from __future__ import annotations

from enum import StrEnum

from mcp_server_for_ynab.models.ynab.common import YnabBaseModel
from mcp_server_for_ynab.models.ynab.transactions import FlagColor, SubTransaction


class Frequency(StrEnum):
    NEVER = "never"
    DAILY = "daily"
    WEEKLY = "weekly"
    EVERY_OTHER_WEEK = "everyOtherWeek"
    TWICE_A_MONTH = "twiceAMonth"
    EVERY_4_WEEKS = "every4Weeks"
    MONTHLY = "monthly"
    EVERY_OTHER_MONTH = "everyOtherMonth"
    EVERY_3_MONTHS = "every3Months"
    EVERY_4_MONTHS = "every4Months"
    TWICE_A_YEAR = "twiceAYear"
    YEARLY = "yearly"
    EVERY_OTHER_YEAR = "everyOtherYear"


class ScheduledTransaction(YnabBaseModel):
    id: str
    date_first: str  # ISO date YYYY-MM-DD
    date_next: str  # ISO date YYYY-MM-DD
    frequency: Frequency
    amount: int  # milliunits
    memo: str | None = None
    flag_color: FlagColor | None = None
    flag_name: str | None = None
    account_id: str
    account_name: str | None = None
    payee_id: str | None = None
    payee_name: str | None = None
    category_id: str | None = None
    category_name: str | None = None
    transfer_account_id: str | None = None
    deleted: bool
    subtransactions: list[SubTransaction] = []  # noqa: RUF012


class ScheduledTransactionsResponse(YnabBaseModel):
    data: ScheduledTransactionsData


class ScheduledTransactionsData(YnabBaseModel):
    scheduled_transactions: list[ScheduledTransaction]
    server_knowledge: int


class ScheduledTransactionResponse(YnabBaseModel):
    data: ScheduledTransactionData


class ScheduledTransactionData(YnabBaseModel):
    scheduled_transaction: ScheduledTransaction


class SaveScheduledTransaction(YnabBaseModel):
    account_id: str
    date: str  # ISO date YYYY-MM-DD — first occurrence date
    frequency: Frequency
    amount: int  # milliunits
    payee_id: str | None = None
    payee_name: str | None = None
    category_id: str | None = None
    memo: str | None = None
    flag_color: FlagColor | None = None


class SaveScheduledTransactionWrapper(YnabBaseModel):
    scheduled_transaction: SaveScheduledTransaction
