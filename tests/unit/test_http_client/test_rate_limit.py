"""Unit tests: 429 handling.

YNAB allows 200 requests per hour per token, and a single enriched tool can
spend several, so a rate limit is a normal event rather than an exceptional one.
The client previously parsed Retry-After and then raised immediately without
ever waiting.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from mcp_server_for_ynab.http_client.client import YnabHttpClient
from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpException


def _auth() -> AsyncMock:
    auth = AsyncMock()
    auth.get_access_token = AsyncMock(return_value="test-token")
    return auth


def _response(status: int, *, retry_after: str | None = None, body: dict | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after else {}
    return httpx.Response(
        status_code=status,
        headers=headers,
        json=body if body is not None else {"data": {"ok": True}},
        request=httpx.Request("GET", "https://api.ynab.com/v1/budgets"),
    )


async def test_retries_after_the_server_specified_delay() -> None:
    client = YnabHttpClient(_auth())
    responses = [_response(429, retry_after="2"), _response(200)]

    with (
        patch.object(httpx.AsyncClient, "request", new=AsyncMock(side_effect=responses)),
        patch("mcp_server_for_ynab.http_client.client.asyncio.sleep", new=AsyncMock()) as sleep,
    ):
        result = await client.get("/budgets")

    assert result == {"data": {"ok": True}}
    sleep.assert_awaited_once_with(2)


async def test_waits_a_default_when_no_retry_after_header() -> None:
    client = YnabHttpClient(_auth())
    responses = [_response(429), _response(200)]

    with (
        patch.object(httpx.AsyncClient, "request", new=AsyncMock(side_effect=responses)),
        patch("mcp_server_for_ynab.http_client.client.asyncio.sleep", new=AsyncMock()) as sleep,
    ):
        await client.get("/budgets")

    sleep.assert_awaited_once_with(5)


async def test_does_not_wait_out_a_long_rolling_window() -> None:
    """A rolling-hour limit can report minutes. Fail fast and tell the caller."""
    client = YnabHttpClient(_auth())

    with (
        patch.object(httpx.AsyncClient, "request", new=AsyncMock(return_value=_response(429, retry_after="1800"))),
        patch("mcp_server_for_ynab.http_client.client.asyncio.sleep", new=AsyncMock()) as sleep,
        pytest.raises(YnabMcpException) as exc,
    ):
        await client.get("/budgets")

    sleep.assert_not_awaited()
    assert exc.value.error.error_type == ErrorType.RATE_LIMITED
    assert exc.value.error.retry_after == 1800


async def test_gives_up_after_the_retry_budget() -> None:
    client = YnabHttpClient(_auth())

    with (
        patch.object(httpx.AsyncClient, "request", new=AsyncMock(return_value=_response(429, retry_after="1"))),
        patch("mcp_server_for_ynab.http_client.client.asyncio.sleep", new=AsyncMock()) as sleep,
        pytest.raises(YnabMcpException) as exc,
    ):
        await client.get("/budgets")

    assert sleep.await_count == 3
    assert exc.value.error.error_type == ErrorType.RATE_LIMITED


async def test_malformed_retry_after_falls_back_to_the_default() -> None:
    client = YnabHttpClient(_auth())
    responses = [_response(429, retry_after="soon"), _response(200)]

    with (
        patch.object(httpx.AsyncClient, "request", new=AsyncMock(side_effect=responses)),
        patch("mcp_server_for_ynab.http_client.client.asyncio.sleep", new=AsyncMock()) as sleep,
    ):
        await client.get("/budgets")

    sleep.assert_awaited_once_with(5)
