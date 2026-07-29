from __future__ import annotations

from mcp_server_for_ynab.models.ynab.transactions import (
    BulkTransactionResponse,
    ImportResponse,
    SaveTransactionsWrapper,
    SaveTransactionWrapper,
    TransactionResponse,
    TransactionsResponse,
    UpdateTransactionsWrapper,
)
from mcp_server_for_ynab.ynab_client.base import BaseClient


class TransactionsClient(BaseClient):
    async def list(
        self,
        plan_id: str,
        *,
        since_date: str | None = None,
        type: str | None = None,
        last_knowledge_of_server: int | None = None,
    ) -> TransactionsResponse:
        """GET /budgets/{id}/transactions — [READ] List transactions.

        since_date: ISO date string. Only transactions on or after this date.
        type: 'uncategorized' or 'unapproved' for filtered results.
        last_knowledge_of_server: for delta sync.
        """
        params: dict[str, object] = {}
        if since_date:
            params["since_date"] = since_date
        if type:
            params["type"] = type
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(f"/budgets/{plan_id}/transactions", params=params or None)
        return TransactionsResponse.model_validate(data)

    async def list_by_account(
        self,
        plan_id: str,
        account_id: str,
        *,
        since_date: str | None = None,
        type: str | None = None,
        last_knowledge_of_server: int | None = None,
    ) -> TransactionsResponse:
        """GET /budgets/{id}/accounts/{account_id}/transactions — [READ]"""
        params: dict[str, object] = {}
        if since_date:
            params["since_date"] = since_date
        if type:
            params["type"] = type
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(
            f"/budgets/{plan_id}/accounts/{account_id}/transactions",
            params=params or None,
        )
        return TransactionsResponse.model_validate(data)

    async def list_by_category(
        self,
        plan_id: str,
        category_id: str,
        *,
        since_date: str | None = None,
        type: str | None = None,
        last_knowledge_of_server: int | None = None,
    ) -> TransactionsResponse:
        """GET /budgets/{id}/categories/{category_id}/transactions — [READ]"""
        params: dict[str, object] = {}
        if since_date:
            params["since_date"] = since_date
        if type:
            params["type"] = type
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(
            f"/budgets/{plan_id}/categories/{category_id}/transactions",
            params=params or None,
        )
        return TransactionsResponse.model_validate(data)

    async def list_by_payee(
        self,
        plan_id: str,
        payee_id: str,
        *,
        since_date: str | None = None,
        type: str | None = None,
        last_knowledge_of_server: int | None = None,
    ) -> TransactionsResponse:
        """GET /budgets/{id}/payees/{payee_id}/transactions — [READ]"""
        params: dict[str, object] = {}
        if since_date:
            params["since_date"] = since_date
        if type:
            params["type"] = type
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(
            f"/budgets/{plan_id}/payees/{payee_id}/transactions",
            params=params or None,
        )
        return TransactionsResponse.model_validate(data)

    async def list_by_month(
        self,
        plan_id: str,
        month: str,
        *,
        since_date: str | None = None,
        type: str | None = None,
        last_knowledge_of_server: int | None = None,
    ) -> TransactionsResponse:
        """GET /budgets/{id}/months/{month}/transactions — [READ]"""
        params: dict[str, object] = {}
        if since_date:
            params["since_date"] = since_date
        if type:
            params["type"] = type
        if last_knowledge_of_server is not None:
            params["last_knowledge_of_server"] = last_knowledge_of_server
        data = await self._http.get(
            f"/budgets/{plan_id}/months/{month}/transactions",
            params=params or None,
        )
        return TransactionsResponse.model_validate(data)

    async def get(self, plan_id: str, transaction_id: str) -> TransactionResponse:
        """GET /budgets/{id}/transactions/{transaction_id} — [READ] Get a single transaction.

        The response includes subtransactions for split transactions.
        """
        data = await self._http.get(f"/budgets/{plan_id}/transactions/{transaction_id}")
        return TransactionResponse.model_validate(data)

    async def create(self, plan_id: str, payload: SaveTransactionWrapper) -> TransactionResponse:
        """POST /budgets/{id}/transactions — [WRITE] Create a single transaction.

        All amounts must be in milliunits (1000 = $1.00).
        For transfer transactions, set payee_id to the transfer_payee_id of the target account.
        For split transactions, provide subtransactions whose amounts sum to the parent amount.
        """
        data = await self._http.post(
            f"/budgets/{plan_id}/transactions",
            json=payload.model_dump(exclude_none=True),
        )
        return TransactionResponse.model_validate(data)

    async def create_many(self, plan_id: str, payload: SaveTransactionsWrapper) -> BulkTransactionResponse:
        """POST /budgets/{id}/transactions (multiple) — [WRITE] Create multiple transactions.

        IMPORTANT: This operation is NOT atomic. Check duplicate_import_ids in the
        response — some transactions may be skipped if they have duplicate import_id values.
        """
        data = await self._http.post(
            f"/budgets/{plan_id}/transactions",
            json=payload.model_dump(exclude_none=True),
        )
        return BulkTransactionResponse.model_validate(data)

    async def update(self, plan_id: str, transaction_id: str, payload: SaveTransactionWrapper) -> TransactionResponse:
        """PUT /budgets/{id}/transactions/{transaction_id} — [WRITE] Update a transaction.

        All amounts must be in milliunits.
        """
        data = await self._http.put(
            f"/budgets/{plan_id}/transactions/{transaction_id}",
            json=payload.model_dump(exclude_none=True),
        )
        return TransactionResponse.model_validate(data)

    async def bulk_update(self, plan_id: str, payload: UpdateTransactionsWrapper) -> BulkTransactionResponse:
        """PATCH /budgets/{id}/transactions — [WRITE] Update multiple transactions.

        IMPORTANT: Bulk update is NOT atomic. The response contains transaction_ids
        (successfully updated) and duplicate_import_ids (skipped). Always verify the
        response rather than assuming all-or-nothing success.

        All amounts must be in milliunits.
        """
        data = await self._http.patch(
            f"/budgets/{plan_id}/transactions",
            json=payload.model_dump(exclude_none=True),
        )
        return BulkTransactionResponse.model_validate(data)

    async def delete(self, plan_id: str, transaction_id: str) -> TransactionResponse:
        """DELETE /budgets/{id}/transactions/{transaction_id} — [WRITE] Delete a transaction.

        WARNING: For transfer transactions, deleting one side also affects the linked
        paired transaction. Check transfer_account_id and transfer_transaction_id before
        deleting.
        """
        data = await self._http.delete(f"/budgets/{plan_id}/transactions/{transaction_id}")
        return TransactionResponse.model_validate(data)

    async def trigger_import(self, plan_id: str) -> ImportResponse:
        """POST /budgets/{id}/transactions/import — [WRITE] Trigger YNAB import.

        This triggers YNAB's built-in import from linked bank accounts.
        It does NOT accept raw transaction data or external file imports.
        Only linked (directly imported) accounts are affected.
        Returns the IDs of transactions that were imported.
        """
        data = await self._http.post(f"/budgets/{plan_id}/transactions/import")
        return ImportResponse.model_validate(data)
