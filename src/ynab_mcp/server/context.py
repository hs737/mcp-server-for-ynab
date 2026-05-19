"""Application context holding all initialized YNAB clients.

A single AppContext is created at server startup and accessed by all tool handlers.
This avoids recreating clients per-request and keeps the tool layer stateless.
"""

from __future__ import annotations

from dataclasses import dataclass

from ynab_mcp.auth.pat import PatAuthProvider
from ynab_mcp.config.settings import Settings
from ynab_mcp.http_client.client import YnabHttpClient
from ynab_mcp.ynab_client.accounts import AccountsClient
from ynab_mcp.ynab_client.categories import CategoriesClient
from ynab_mcp.ynab_client.money_movements import MoneyMovementsClient
from ynab_mcp.ynab_client.months import MonthsClient
from ynab_mcp.ynab_client.payees import PayeesClient
from ynab_mcp.ynab_client.plans import PlansClient
from ynab_mcp.ynab_client.scheduled_transactions import ScheduledTransactionsClient
from ynab_mcp.ynab_client.transactions import TransactionsClient
from ynab_mcp.ynab_client.user import UserClient


@dataclass
class AppContext:
    settings: Settings
    http: YnabHttpClient
    user: UserClient
    plans: PlansClient
    accounts: AccountsClient
    categories: CategoriesClient
    months: MonthsClient
    payees: PayeesClient
    transactions: TransactionsClient
    scheduled_transactions: ScheduledTransactionsClient
    money_movements: MoneyMovementsClient

    @classmethod
    def from_settings(cls, settings: Settings) -> AppContext:
        auth = PatAuthProvider(settings)
        http = YnabHttpClient(auth)
        return cls(
            settings=settings,
            http=http,
            user=UserClient(http),
            plans=PlansClient(http),
            accounts=AccountsClient(http),
            categories=CategoriesClient(http),
            months=MonthsClient(http),
            payees=PayeesClient(http),
            transactions=TransactionsClient(http),
            scheduled_transactions=ScheduledTransactionsClient(http),
            money_movements=MoneyMovementsClient(http),
        )


_app_context: AppContext | None = None


def set_app_context(ctx: AppContext) -> None:
    global _app_context
    _app_context = ctx


def get_app_context() -> AppContext:
    if _app_context is None:
        raise RuntimeError("AppContext not initialized. Call set_app_context() at startup.")
    return _app_context
