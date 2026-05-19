"""Personal Access Token auth provider — Phase 1 implementation."""

from __future__ import annotations

from ynab_mcp.config import ConfigError, Settings


class PatAuthProvider:
    """Reads YNAB_API_KEY from config and returns it as-is.

    The PAT never expires, so there is no refresh logic needed.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.ynab_api_key:
            raise ConfigError("YNAB_API_KEY is required for PAT auth but is not set.")
        self._token = settings.ynab_api_key

    async def get_access_token(self) -> str:
        return self._token

    def describe_mode(self) -> str:
        return "PAT (Personal Access Token)"
