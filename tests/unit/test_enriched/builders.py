"""Builders for enriched-tool tests.

Enriched tools take an AppContext and read through the ynab_client wrappers, so
these build typed model objects and hand back a context whose clients return
them. Keeping the construction here lets each test state only the field it cares
about.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from mcp_server_for_ynab.models.ynab.accounts import Account, AccountsData, AccountsResponse
from mcp_server_for_ynab.models.ynab.categories import (
    CategoriesData,
    CategoriesResponse,
    Category,
    CategoryGroup,
)
from mcp_server_for_ynab.models.ynab.money_movements import (
    MoneyMovement,
    MoneyMovementsData,
    MoneyMovementsResponse,
)
from mcp_server_for_ynab.models.ynab.months import (
    Month,
    MonthData,
    MonthResponse,
    MonthsData,
    MonthsResponse,
    MonthSummary,
)
from mcp_server_for_ynab.models.ynab.scheduled_transactions import (
    ScheduledTransaction,
    ScheduledTransactionsData,
    ScheduledTransactionsResponse,
)
from mcp_server_for_ynab.models.ynab.transactions import Transaction, TransactionsData, TransactionsResponse


def category(
    name: str = "Groceries",
    *,
    id: str = "cat-1",
    balance: int = 0,
    budgeted: int = 0,
    activity: int = 0,
    goal_under_funded: int | None = None,
    hidden: bool = False,
    deleted: bool = False,
    group_id: str = "group-1",
    group_name: str | None = "Everyday",
    **extra: Any,
) -> Category:
    return Category(
        id=id,
        category_group_id=group_id,
        category_group_name=group_name,
        name=name,
        hidden=hidden,
        budgeted=budgeted,
        activity=activity,
        balance=balance,
        goal_under_funded=goal_under_funded,
        deleted=deleted,
        **extra,
    )


def month(
    *,
    month: str = "2026-07-01",
    income: int = 0,
    budgeted: int = 0,
    activity: int = 0,
    to_be_budgeted: int = 0,
    age_of_money: int | None = None,
    categories: list[Category] | None = None,
) -> MonthResponse:
    return MonthResponse(
        data=MonthData(
            month=Month(
                month=month,
                income=income,
                budgeted=budgeted,
                activity=activity,
                to_be_budgeted=to_be_budgeted,
                age_of_money=age_of_money,
                deleted=False,
                categories=categories or [],
            )
        )
    )


def account(
    name: str = "Checking",
    *,
    id: str = "acct-1",
    balance: int = 0,
    on_budget: bool = True,
    closed: bool = False,
    deleted: bool = False,
    type: str = "checking",
    cleared_balance: int | None = None,
    uncleared_balance: int = 0,
    direct_import_linked: bool | None = None,
    last_reconciled_at: str | None = None,
) -> Account:
    return Account(
        id=id,
        name=name,
        type=type,
        on_budget=on_budget,
        closed=closed,
        balance=balance,
        cleared_balance=balance if cleared_balance is None else cleared_balance,
        uncleared_balance=uncleared_balance,
        transfer_payee_id=f"transfer-{id}",
        direct_import_linked=direct_import_linked,
        last_reconciled_at=last_reconciled_at,
        deleted=deleted,
    )


def accounts_response(*items: Account, server_knowledge: int = 1) -> AccountsResponse:
    return AccountsResponse(data=AccountsData(accounts=list(items), server_knowledge=server_knowledge))


def categories_response(*items: Category, server_knowledge: int = 1) -> CategoriesResponse:
    group = CategoryGroup(id="group-1", name="Everyday", hidden=False, deleted=False, categories=list(items))
    return CategoriesResponse(data=CategoriesData(category_groups=[group], server_knowledge=server_knowledge))


def category_group(
    name: str = "Everyday",
    *,
    id: str = "group-1",
    hidden: bool = False,
    categories: list[Category] | None = None,
) -> CategoryGroup:
    return CategoryGroup(id=id, name=name, hidden=hidden, deleted=False, categories=categories or [])


def groups_response(*groups: CategoryGroup, server_knowledge: int = 1) -> CategoriesResponse:
    """A categories response built from explicit groups, for multi-group cases."""
    return CategoriesResponse(data=CategoriesData(category_groups=list(groups), server_knowledge=server_knowledge))


def months_list_response(*items: MonthSummary, server_knowledge: int = 1) -> MonthsResponse:
    return MonthsResponse(data=MonthsData(months=list(items), server_knowledge=server_knowledge))


def month_summary(*, month: str = "2026-07-01", budgeted: int = 0) -> MonthSummary:
    return MonthSummary(
        month=month, income=0, budgeted=budgeted, activity=0, to_be_budgeted=0, age_of_money=None, deleted=False
    )


def money_movement(
    *,
    id: str = "mm-1",
    month: str = "2026-07-01",
    amount: int = 10_000,
    from_category_id: str | None = None,
    to_category_id: str | None = "cat-1",
) -> MoneyMovement:
    return MoneyMovement(
        id=id,
        month=month,
        moved_at=f"{month}T12:00:00Z",
        amount=amount,
        from_category_id=from_category_id,
        to_category_id=to_category_id,
    )


def money_movements_response(*items: MoneyMovement, server_knowledge: int = 1) -> MoneyMovementsResponse:
    return MoneyMovementsResponse(
        data=MoneyMovementsData(money_movements=list(items), server_knowledge=server_knowledge)
    )


def transaction(
    *,
    id: str = "txn-1",
    date: str = "2026-07-15",
    amount: int = -10_000,
    account_id: str = "acct-1",
    cleared: str = "cleared",
    import_id: str | None = None,
    payee_id: str | None = "payee-1",
    payee_name: str | None = "Grocery Store",
    category_id: str | None = "cat-1",
    category_name: str | None = "Groceries",
    memo: str | None = None,
    deleted: bool = False,
    transfer_account_id: str | None = None,
    subtransactions: list[Any] | None = None,
) -> Transaction:
    return Transaction(
        id=id,
        date=date,
        amount=amount,
        memo=memo,
        cleared=cleared,
        approved=True,
        import_id=import_id,
        account_id=account_id,
        account_name="Checking",
        payee_id=payee_id,
        payee_name=payee_name,
        category_id=category_id,
        category_name=category_name,
        transfer_account_id=transfer_account_id,
        deleted=deleted,
        subtransactions=subtransactions or [],
    )


def transactions_response(*items: Transaction, server_knowledge: int = 1) -> TransactionsResponse:
    return TransactionsResponse(data=TransactionsData(transactions=list(items), server_knowledge=server_knowledge))


def days_from_today(days: int) -> str:
    """A date relative to today, so tests do not go stale as the clock moves."""
    return (date.today() + timedelta(days=days)).isoformat()


def scheduled(
    *,
    id: str = "sched-1",
    date_next: str | None = None,
    amount: int = -50_000,
    category_id: str | None = "cat-1",
    category_name: str | None = "Groceries",
    payee_name: str | None = "Rent",
    deleted: bool = False,
) -> ScheduledTransaction:
    when = date_next or days_from_today(5)
    return ScheduledTransaction(
        id=id,
        date_first=when,
        date_next=when,
        frequency="monthly",
        amount=amount,
        account_id="acct-1",
        account_name="Checking",
        payee_name=payee_name,
        category_id=category_id,
        category_name=category_name,
        deleted=deleted,
    )


def scheduled_response(*items: ScheduledTransaction, server_knowledge: int = 1) -> ScheduledTransactionsResponse:
    return ScheduledTransactionsResponse(
        data=ScheduledTransactionsData(scheduled_transactions=list(items), server_knowledge=server_knowledge)
    )


def make_ctx(
    *,
    month_response: MonthResponse | None = None,
    months_by_month: dict[str, MonthResponse] | None = None,
    months_list: MonthsResponse | None = None,
    money_movements: MoneyMovementsResponse | None = None,
    accounts: AccountsResponse | None = None,
    categories: CategoriesResponse | None = None,
    transactions: TransactionsResponse | None = None,
    transactions_by_type: dict[str | None, TransactionsResponse] | None = None,
    scheduled_transactions: ScheduledTransactionsResponse | None = None,
) -> MagicMock:
    """Build an AppContext whose clients return the given typed responses.

    `transactions_by_type` keys on the `type` filter ("uncategorized",
    "unapproved", or None for unfiltered) so a single context can serve tools
    that fetch several queues at once.
    """
    ctx = MagicMock()

    if months_by_month is not None:

        async def _month(_plan: str, stamp: str) -> MonthResponse:
            return months_by_month[stamp]

        ctx.months.get = AsyncMock(side_effect=_month)
    else:
        ctx.months.get = AsyncMock(return_value=month_response or month())

    ctx.months.list = AsyncMock(return_value=months_list or months_list_response())
    ctx.money_movements.list = AsyncMock(return_value=money_movements or money_movements_response())
    ctx.accounts.list = AsyncMock(return_value=accounts or accounts_response())
    ctx.categories.list = AsyncMock(return_value=categories or categories_response())
    ctx.scheduled_transactions.list = AsyncMock(return_value=scheduled_transactions or scheduled_response())

    if transactions_by_type is not None:

        async def _list(_plan: str, *, type: str | None = None, **_kw: Any) -> TransactionsResponse:
            return transactions_by_type.get(type, transactions_response())

        ctx.transactions.list = AsyncMock(side_effect=_list)
    else:
        ctx.transactions.list = AsyncMock(return_value=transactions or transactions_response())

    for method in ("list_by_payee", "list_by_category", "list_by_account"):
        setattr(ctx.transactions, method, AsyncMock(return_value=transactions or transactions_response()))

    return ctx
