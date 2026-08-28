from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from mcp_server_for_ynab.models.ynab.common import DecodedTextModel, YnabBaseModel
from mcp_server_for_ynab.models.ynab.limits import MEMO_MAX, TRANSACTION_PAYEE_NAME_MAX


class ClearedStatus(StrEnum):
    CLEARED = "cleared"
    UNCLEARED = "uncleared"
    RECONCILED = "reconciled"


class FlagColor(StrEnum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"


class SubTransaction(DecodedTextModel):
    id: str
    transaction_id: str
    amount: int  # milliunits — negative for outflow, positive for inflow
    memo: str | None = None
    payee_id: str | None = None
    payee_name: str | None = None
    category_id: str | None = None
    category_name: str | None = None
    transfer_account_id: str | None = None
    transfer_transaction_id: str | None = None
    deleted: bool


class TransactionBase(DecodedTextModel):
    """Fields common to both transaction summary and detail."""

    id: str
    date: str  # ISO date YYYY-MM-DD
    amount: int  # milliunits — negative for outflow, positive for inflow
    memo: str | None = None
    cleared: ClearedStatus
    approved: bool
    flag_color: FlagColor | None = None
    flag_name: str | None = None
    account_id: str
    account_name: str | None = None
    payee_id: str | None = None
    payee_name: str | None = None
    category_id: str | None = None
    category_name: str | None = None
    transfer_account_id: str | None = None
    transfer_transaction_id: str | None = None
    matched_transaction_id: str | None = None
    import_id: str | None = None
    import_payee_name: str | None = None
    import_payee_name_original: str | None = None
    debt_transaction_type: str | None = None
    deleted: bool


class Transaction(TransactionBase):
    """Full transaction detail, including subtransactions."""

    subtransactions: list[SubTransaction] = []  # noqa: RUF012


class TransactionSummary(TransactionBase):
    """Transaction as returned in list responses (no subtransactions)."""


class TransactionsResponse(YnabBaseModel):
    data: TransactionsData


class TransactionsData(YnabBaseModel):
    transactions: list[Transaction]
    server_knowledge: int


class TransactionResponse(YnabBaseModel):
    data: TransactionData


class TransactionData(YnabBaseModel):
    transaction: Transaction


class SaveSubTransaction(YnabBaseModel):
    amount: int  # milliunits
    payee_id: str | None = None
    payee_name: str | None = Field(default=None, max_length=TRANSACTION_PAYEE_NAME_MAX)
    category_id: str | None = None
    memo: str | None = Field(default=None, max_length=MEMO_MAX)


class SaveTransaction(YnabBaseModel):
    account_id: str
    date: str  # ISO date YYYY-MM-DD
    amount: int  # milliunits
    payee_id: str | None = None
    payee_name: str | None = Field(default=None, max_length=TRANSACTION_PAYEE_NAME_MAX)
    category_id: str | None = None
    memo: str | None = Field(default=None, max_length=MEMO_MAX)
    cleared: ClearedStatus | None = None
    approved: bool | None = None
    flag_color: FlagColor | None = None
    import_id: str | None = None
    subtransactions: list[SaveSubTransaction] | None = None


class SaveTransactionWrapper(YnabBaseModel):
    transaction: SaveTransaction


class SaveTransactionsWrapper(YnabBaseModel):
    transactions: list[SaveTransaction]


class UpdateTransaction(YnabBaseModel):
    """Used for bulk updates — id is required."""

    id: str
    account_id: str | None = None
    date: str | None = None
    amount: int | None = None  # milliunits
    payee_id: str | None = None
    payee_name: str | None = Field(default=None, max_length=TRANSACTION_PAYEE_NAME_MAX)
    category_id: str | None = None
    memo: str | None = Field(default=None, max_length=MEMO_MAX)
    cleared: ClearedStatus | None = None
    approved: bool | None = None
    flag_color: FlagColor | None = None
    subtransactions: list[SaveSubTransaction] | None = None


class UpdateTransactionsWrapper(YnabBaseModel):
    transactions: list[UpdateTransaction]


class BulkTransactionData(YnabBaseModel):
    """Result of a bulk transaction operation.

    IMPORTANT: Bulk update is NOT atomic. `transaction_ids` lists what was
    successfully created or updated, and `duplicate_import_ids` lists what was
    skipped for having a duplicate import_id. Always check both rather than
    assuming all-or-nothing success.

    These fields sit directly on `data`. An earlier version nested them under a
    `bulk` key, which the API has never returned on this route, so every bulk
    call failed to parse.
    """

    transaction_ids: list[str]
    duplicate_import_ids: list[str] = []  # noqa: RUF012
    transactions: list[Transaction] = []  # noqa: RUF012
    server_knowledge: int | None = None


class BulkTransactionResponse(YnabBaseModel):
    data: BulkTransactionData


class ImportResponse(YnabBaseModel):
    data: ImportData


class ImportData(YnabBaseModel):
    transaction_ids: list[str]
