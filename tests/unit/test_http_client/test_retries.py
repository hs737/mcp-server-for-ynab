"""Unit tests: HTTP client retry logic, error mapping, and header redaction."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from mcp_server_for_ynab.http_client.client import YnabHttpClient, _redact_headers
from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpException


def _make_client() -> YnabHttpClient:
    auth = MagicMock()
    auth.get_access_token = AsyncMock(return_value="test-token")
    return YnabHttpClient(auth)


def _make_response(status: int, body: Any = None, headers: dict[str, str] | None = None) -> httpx.Response:
    import json

    content = json.dumps(body).encode() if body is not None else b"{}"
    resp = httpx.Response(status_code=status, content=content, headers=headers or {})
    resp.request = httpx.Request("GET", "https://api.ynab.com/v1/test")
    return resp


def _mock_client(response: httpx.Response | list[httpx.Response]) -> MagicMock:
    """Return a mock httpx.AsyncClient that returns the given response(s)."""
    mock = MagicMock(spec=httpx.AsyncClient)
    if isinstance(response, list):
        mock.request = AsyncMock(side_effect=response)
    else:
        mock.request = AsyncMock(return_value=response)
    return mock


async def test_get_success() -> None:
    client = _make_client()
    expected = {"data": {"budget_id": "abc"}}
    mock_httpx = _mock_client(_make_response(200, expected))

    with patch.object(client, "_get_client", new=AsyncMock(return_value=mock_httpx)):
        result = await client.get("/budgets/abc")

    assert result == expected


async def test_raises_on_401() -> None:
    client = _make_client()
    body = {"error": {"name": "unauthorized", "id": "401", "detail": "Invalid token."}}
    mock_httpx = _mock_client(_make_response(401, body))

    with patch.object(client, "_get_client", new=AsyncMock(return_value=mock_httpx)):
        with pytest.raises(YnabMcpException) as exc_info:
            await client.get("/budgets")

    assert exc_info.value.error.error_type == ErrorType.AUTH_FAILURE


async def test_raises_on_404() -> None:
    client = _make_client()
    body = {"error": {"name": "not_found", "id": "404", "detail": "Not found."}}
    mock_httpx = _mock_client(_make_response(404, body))

    with patch.object(client, "_get_client", new=AsyncMock(return_value=mock_httpx)):
        with pytest.raises(YnabMcpException) as exc_info:
            await client.get("/budgets/nonexistent")

    assert exc_info.value.error.error_type == ErrorType.NOT_FOUND


async def test_raises_rate_limited_with_retry_after() -> None:
    client = _make_client()
    mock_httpx = _mock_client(_make_response(429, headers={"Retry-After": "45"}))

    with patch.object(client, "_get_client", new=AsyncMock(return_value=mock_httpx)):
        with pytest.raises(YnabMcpException) as exc_info:
            await client.get("/budgets")

    err = exc_info.value.error
    assert err.error_type == ErrorType.RATE_LIMITED
    assert err.retry_after == 45


async def test_retries_on_500() -> None:
    client = _make_client()
    success_body = {"data": {"ok": True}}
    responses = [
        _make_response(500),
        _make_response(500),
        _make_response(200, success_body),
    ]
    mock_httpx = _mock_client(responses)

    with (
        patch.object(client, "_get_client", new=AsyncMock(return_value=mock_httpx)),
        patch("mcp_server_for_ynab.http_client.client.asyncio.sleep", new=AsyncMock()),
    ):
        result = await client.get("/budgets")

    assert result == success_body
    assert mock_httpx.request.call_count == 3


async def test_raises_transport_error_after_max_retries() -> None:
    client = _make_client()
    mock_httpx = MagicMock(spec=httpx.AsyncClient)
    mock_httpx.request = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

    with (
        patch.object(client, "_get_client", new=AsyncMock(return_value=mock_httpx)),
        patch("mcp_server_for_ynab.http_client.client.asyncio.sleep", new=AsyncMock()),
        pytest.raises(YnabMcpException) as exc_info,
    ):
        await client.get("/budgets")

    assert exc_info.value.error.error_type == ErrorType.TRANSPORT_ERROR


# ---------------------------------------------------------------------------
# _redact_headers
# ---------------------------------------------------------------------------


def test_redact_headers_removes_authorization() -> None:
    """The real token must not appear anywhere in the redacted dict."""
    raw = httpx.Headers({"authorization": "Bearer secret-token", "content-type": "application/json"})
    result = _redact_headers(raw)

    assert "secret-token" not in str(result)
    assert result["authorization"] == "Bearer [REDACTED]"
    assert result["content-type"] == "application/json"


def test_redact_headers_no_duplicate_key() -> None:
    """Redaction must not leave both 'authorization' and 'Authorization' in the dict."""
    raw = httpx.Headers({"authorization": "Bearer secret"})
    result = _redact_headers(raw)

    lowercase_keys = {k.lower() for k in result}
    assert lowercase_keys == {"authorization"}  # exactly one entry


def test_redact_headers_no_auth_header_is_unchanged() -> None:
    raw = httpx.Headers({"content-type": "application/json", "x-request-id": "abc123"})
    result = _redact_headers(raw)

    assert "authorization" not in result
    assert result["content-type"] == "application/json"
