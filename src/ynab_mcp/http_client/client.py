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
from ynab_mcp.models.errors import ErrorType, YnabMcpError, YnabMcpException

logger = logging.getLogger(__name__)

YNAB_BASE_URL = "https://api.ynab.com/v1"

_RETRYABLE_STATUS_CODES = {500, 502, 503, 504}
_MAX_RETRIES = 3
_BACKOFF_BASE = 0.5  # seconds

# YNAB allows 200 requests per hour per token. A single enriched tool can spend
# several, so hitting 429 during normal use is expected rather than exceptional.
# Wait when the server tells us how long, but only for a short, bounded pause —
# a rolling-window limit can report a retry-after of many minutes, and an agent
# waiting silently that long is worse than a clear error it can act on.
_MAX_RATE_LIMIT_WAIT_SECONDS = 30
_DEFAULT_RATE_LIMIT_WAIT_SECONDS = 5


def _redact_headers(headers: httpx.Headers) -> dict[str, str]:
    """Return a copy of headers with Authorization redacted for logging.

    httpx.Headers stores keys in lowercase. dict(headers) therefore produces
    lowercase keys. Adding a capitalized "Authorization" key would leave the
    original lowercase "authorization" key (containing the real token) intact.
    Normalise to lowercase first so the replacement is unambiguous.
    """
    result = {k.lower(): v for k, v in headers.items()}
    if "authorization" in result:
        result["authorization"] = "Bearer [REDACTED]"
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
                    wait = _BACKOFF_BASE * (2**attempt)
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
                raise YnabMcpException(
                    YnabMcpError(
                        error_type=ErrorType.TRANSPORT_ERROR,
                        message=f"Network error communicating with YNAB API: {exc}",
                    )
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

                wait = retry_after if retry_after is not None else _DEFAULT_RATE_LIMIT_WAIT_SECONDS
                if attempt < _MAX_RETRIES and wait <= _MAX_RATE_LIMIT_WAIT_SECONDS:
                    logger.warning(
                        "Rate limited on %s %s (attempt %d/%d), retrying in %ds",
                        method,
                        path,
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                # Out of attempts, or the wait is too long to sit on. Surface
                # retry_after so the caller can decide when to come back.
                raise YnabMcpException(YnabMcpError.rate_limited(retry_after=retry_after))

            if response.status_code in _RETRYABLE_STATUS_CODES:
                last_error = Exception(f"HTTP {response.status_code}")
                if attempt < _MAX_RETRIES:
                    wait = _BACKOFF_BASE * (2**attempt)
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
                raise YnabMcpException(
                    YnabMcpError.from_ynab_response(
                        status_code=response.status_code,
                        error_name=error_detail.get("name") if isinstance(error_detail, dict) else None,
                        error_id=error_detail.get("id") if isinstance(error_detail, dict) else None,
                        detail=error_detail.get("detail") if isinstance(error_detail, dict) else None,
                    )
                )

            return response.json()  # type: ignore[no-any-return]

        raise YnabMcpException(
            YnabMcpError(
                error_type=ErrorType.TRANSPORT_ERROR,
                message=f"Request failed after {_MAX_RETRIES} retries: {last_error}",
            )
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
