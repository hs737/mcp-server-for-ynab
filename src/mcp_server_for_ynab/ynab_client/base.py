"""Shared base for all YNAB resource clients."""

from __future__ import annotations

from mcp_server_for_ynab.http_client.client import YnabHttpClient


class BaseClient:
    def __init__(self, http: YnabHttpClient) -> None:
        self._http = http
