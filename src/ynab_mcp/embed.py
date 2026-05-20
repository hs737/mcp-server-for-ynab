"""Stable embed surface for hosted runtimes that import ynab-mcp as a library."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ynab_mcp.auth.base import AuthProvider
from ynab_mcp.server.app import create_embedded_app
from ynab_mcp.server.context import (
    AppContext,
    PlanResolver,
    StaticPlanResolver,
    bind_app_context,
    get_app_context,
)


def create_app_context(
    *,
    auth_provider: AuthProvider,
    default_plan_id: str | None = None,
    plan_resolver: PlanResolver | None = None,
) -> AppContext:
    """Build a request-scoped AppContext for an embedded runtime.

    Hosted runtimes can pass either:
    - `default_plan_id` for the common "one default plan per user" case, or
    - a custom `plan_resolver` implementation for more complex policy.
    """
    resolver = plan_resolver or StaticPlanResolver(default_plan_id=default_plan_id)
    return AppContext.from_auth_provider(settings=resolver, auth_provider=auth_provider)


def create_mcp_app() -> FastMCP:
    """Return the core FastMCP application without PAT-only startup wiring."""
    return create_embedded_app()


__all__ = [
    "AppContext",
    "PlanResolver",
    "StaticPlanResolver",
    "bind_app_context",
    "create_app_context",
    "create_mcp_app",
    "get_app_context",
]
