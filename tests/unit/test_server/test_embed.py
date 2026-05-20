"""Unit tests for the hosted embed surface."""

from __future__ import annotations

import pytest

from ynab_mcp.config.settings import ConfigError
from ynab_mcp.embed import StaticPlanResolver, bind_app_context, create_app_context, create_mcp_app
from ynab_mcp.server.context import get_app_context, set_app_context


class FakeAuthProvider:
    async def get_access_token(self) -> str:
        return "token-test-123"

    def describe_mode(self) -> str:
        return "fake"


def test_static_plan_resolver_requires_plan() -> None:
    resolver = StaticPlanResolver()
    with pytest.raises(ConfigError, match="plan_id"):
        resolver.resolve_plan_id(None)


def test_create_app_context_uses_default_plan() -> None:
    ctx = create_app_context(auth_provider=FakeAuthProvider(), default_plan_id="plan-default-123")
    assert ctx.settings.resolve_plan_id(None) == "plan-default-123"


def test_bind_app_context_overrides_global_context() -> None:
    global_ctx = create_app_context(auth_provider=FakeAuthProvider(), default_plan_id="plan-global")
    request_ctx = create_app_context(auth_provider=FakeAuthProvider(), default_plan_id="plan-request")
    set_app_context(global_ctx)

    assert get_app_context() is global_ctx

    with bind_app_context(request_ctx):
        assert get_app_context() is request_ctx

    assert get_app_context() is global_ctx


def test_create_mcp_app_does_not_require_pat_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YNAB_API_KEY", raising=False)
    assert create_mcp_app() is not None
