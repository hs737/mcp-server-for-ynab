"""Shared base for all YNAB resource clients."""

from __future__ import annotations

from ynab_mcp.http_client.client import YnabHttpClient


class BaseClient:
    def __init__(self, http: YnabHttpClient) -> None:
        self._http = http
