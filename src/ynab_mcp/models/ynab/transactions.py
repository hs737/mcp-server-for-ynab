from __future__ import annotations

from enum import Enum

from ynab_mcp.models.ynab.common import YnabBaseModel


class ClearedStatus(str, Enum):
    CLEARED = "cleared"
    UNCLEARED = "uncleared"
    RECONCILED = "reconciled"


class FlagColor(str, Enum):
    RED = "red"
    ORANGE = "orange"
    YELLOW = "yellow"
    GREEN = "green"
    BLUE = "blue"
    PURPLE = "purple"


class SubTransaction(YnabBaseModel):
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


class TransactionBase(YnabBaseModel):
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

    subtransactions: list[SubTransaction] = []


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
    payee_name: str | None = None
    category_id: str | None = None
    memo: str | None = None


class SaveTransaction(YnabBaseModel):
    account_id: str
    date: str  # ISO date YYYY-MM-DD
    amount: int  # milliunits
    payee_id: str | None = None
    payee_name: str | None = None
    category_id: str | None = None
    memo: str | None = None
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
    payee_name: str | None = None
    category_id: str | None = None
    memo: str | None = None
    cleared: ClearedStatus | None = None
    approved: bool | None = None
    flag_color: FlagColor | None = None
    subtransactions: list[SaveSubTransaction] | None = None


class UpdateTransactionsWrapper(YnabBaseModel):
    transactions: list[UpdateTransaction]


class BulkTransactionResult(YnabBaseModel):
    """Result of a bulk transaction operation.

    IMPORTANT: Bulk update is NOT atomic. transaction_ids_approved contains
    transactions that were successfully created/updated. transaction_ids_duplicate
    contains IDs that were skipped due to duplicate import_id values.
    Always check both fields rather than assuming all-or-nothing success.
    """

    transaction_ids: list[str]
    duplicate_import_ids: list[str]


class BulkTransactionResponse(YnabBaseModel):
    data: BulkTransactionData


class BulkTransactionData(YnabBaseModel):
    bulk: BulkTransactionResult


class ImportResponse(YnabBaseModel):
    data: ImportData


class ImportData(YnabBaseModel):
    transaction_ids: list[str]
