"""Async httpx wrapper for YNAB API calls.

Responsibilities:
- Inject Bearer token from AuthProvider
- Retry on transient errors (5xx, network failures) with exponential backoff
- Handle 429 rate-limit responses, extracting Retry-After when present
- Redact Authorization headers before logging
- Normalize error responses into YnabMcpError
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from ynab_mcp.auth.base import AuthProvider
from ynab_mcp.models.errors import YnabMcpError

logger = logging.getLogger(__name__)

YNAB_BASE_URL = "https://api.ynab.com/v1"

_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds


def _redact_headers(headers: httpx.Headers) -> dict[str, str]:
    """Return a copy of headers with Authorization redacted for logging."""
    result = dict(headers)
    if "authorization" in {k.lower() for k in result}:
        result["Authorization"] = "Bearer [REDACTED]"
    return result


class YnabHttpClient:
    """Async YNAB API client with auth injection, retries, and error normalization."""

    def __init__(self, auth_provider: AuthProvider) -> None:
        self._auth = auth_provider
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=YNAB_BASE_URL,
                timeout=httpx.Timeout(30.0),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any = None,
    ) -> dict[str, Any]:
        """Execute an authenticated request, retrying on transient errors.

        Returns the parsed JSON body on success.
        Raises YnabMcpError on API errors.
        Raises httpx.HTTPError on transport-level failures after retries exhausted.
        """
        token = await self._auth.get_access_token()
        headers = {"Authorization": f"Bearer {token}"}

        last_error: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            client = await self._get_client()
            try:
                response = await client.request(
                    method,
                    path,
                    headers=headers,
                    params=params,
                    json=json,
                )
            except httpx.TransportError as exc:
                last_error = exc
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Transport error on %s %s (attempt %d/%d), retrying in %.1fs: %s",
                        method,
                        path,
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                        exc,
                    )
                    await asyncio.sleep(wait)
                    continue
                raise YnabMcpError(
                    error_type="transport_error",
                    message=f"Network error communicating with YNAB API: {exc}",
                ) from exc

            logger.debug(
                "%s %s → %d (headers: %s)",
                method,
                path,
                response.status_code,
                _redact_headers(response.request.headers),
            )

            if response.status_code == 429:
                retry_after: int | None = None
                raw_retry = response.headers.get("Retry-After")
                if raw_retry:
                    try:
                        retry_after = int(raw_retry)
                    except ValueError:
                        pass
                raise YnabMcpError.rate_limited(retry_after=retry_after)

            if response.status_code in _RETRYABLE_STATUS_CODES:
                last_error = Exception(f"HTTP {response.status_code}")
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE * (2 ** attempt)
                    logger.warning(
                        "Retryable error %d on %s %s (attempt %d/%d), retrying in %.1fs",
                        response.status_code,
                        method,
                        path,
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

            if response.status_code >= 400:
                error_body: dict[str, Any] = {}
                try:
                    error_body = response.json()
                except Exception:
                    pass
                error_detail = error_body.get("error", {})
                raise YnabMcpError.from_ynab_response(
                    status_code=response.status_code,
                    error_name=error_detail.get("name") if isinstance(error_detail, dict) else None,
                    error_id=error_detail.get("id") if isinstance(error_detail, dict) else None,
                    detail=error_detail.get("detail") if isinstance(error_detail, dict) else None,
                )

            return response.json()

        raise YnabMcpError(
            error_type="transport_error",
            message=f"Request failed after {_MAX_RETRIES} retries: {last_error}",
        )

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, *, json: Any = None) -> dict[str, Any]:
        return await self.request("POST", path, json=json)

    async def put(self, path: str, *, json: Any = None) -> dict[str, Any]:
        return await self.request("PUT", path, json=json)

    async def patch(self, path: str, *, json: Any = None) -> dict[str, Any]:
        return await self.request("PATCH", path, json=json)

    async def delete(self, path: str) -> dict[str, Any]:
        return await self.request("DELETE", path)
