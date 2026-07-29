"""Application context holding initialized YNAB clients.

The local PAT runtime uses one process-global AppContext. Hosted runtimes can
create request-scoped AppContext instances from another AuthProvider and bind
them for the duration of a request.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ynab_mcp.auth.base import AuthProvider
from ynab_mcp.auth.pat import PatAuthProvider
from ynab_mcp.config.settings import ConfigError, Settings
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


@runtime_checkable
class PlanResolver(Protocol):
    """Runtime settings surface needed by the tool layer."""

    def resolve_plan_id(self, plan_id: str | None) -> str:
        """Return an explicit plan_id or a configured default."""


@dataclass(frozen=True)
class StaticPlanResolver:
    """Simple plan resolver for embedded runtimes.

    Hosted runtimes can supply a per-user default plan without depending on the
    local PAT-focused Settings class.
    """

    default_plan_id: str | None = None

    def resolve_plan_id(self, plan_id: str | None) -> str:
        resolved = plan_id or self.default_plan_id
        if not resolved:
            raise ConfigError(
                "plan_id is required but was not provided and no default plan is configured for this runtime context."
            )
        return resolved


@dataclass
class AppContext:
    settings: PlanResolver
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
        return cls.from_auth_provider(settings=settings, auth_provider=PatAuthProvider(settings))

    @classmethod
    def from_auth_provider(cls, settings: PlanResolver, auth_provider: AuthProvider) -> AppContext:
        """Build a full client bundle from any AuthProvider implementation."""
        http = YnabHttpClient(auth_provider)
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
_request_app_context: ContextVar[AppContext | None] = ContextVar("ynab_mcp_request_app_context", default=None)


def set_app_context(ctx: AppContext) -> None:
    global _app_context
    _app_context = ctx


def push_app_context(ctx: AppContext) -> Token[AppContext | None]:
    """Bind an AppContext to the current task/request."""
    return _request_app_context.set(ctx)


def pop_app_context(token: Token[AppContext | None]) -> None:
    """Remove a request-scoped AppContext binding."""
    _request_app_context.reset(token)


@contextmanager
def bind_app_context(ctx: AppContext) -> Iterator[AppContext]:
    """Temporarily bind an AppContext for the current task/request."""
    token = push_app_context(ctx)
    try:
        yield ctx
    finally:
        pop_app_context(token)


def get_app_context() -> AppContext:
    request_ctx = _request_app_context.get()
    if request_ctx is not None:
        return request_ctx

    if _app_context is None:
        raise RuntimeError(
            "AppContext not initialized. Call set_app_context() at startup "
            "or bind a request-scoped context before invoking tools."
        )
    return _app_context
