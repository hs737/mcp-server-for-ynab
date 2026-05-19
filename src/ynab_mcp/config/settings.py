"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import logging
import os


class ConfigError(Exception):
    """Raised when required configuration is missing or invalid."""


class Settings:
    """Application settings loaded from environment variables.

    Required:
        YNAB_API_KEY: YNAB Personal Access Token.

    Recommended:
        YNAB_PLAN_ID: Default budget/plan ID. When set, all tools that accept
            plan_id treat it as optional and default to this value.

    Optional:
        LOG_LEVEL: Logging verbosity. Defaults to INFO.
    """

    def __init__(self) -> None:
        self.ynab_api_key: str = self._require("YNAB_API_KEY")
        self.ynab_plan_id: str | None = os.environ.get("YNAB_PLAN_ID") or None
        self.log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()

    @staticmethod
    def _require(name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise ConfigError(
                f"Required environment variable {name!r} is not set. "
                f"See .env.example for setup instructions."
            )
        return value

    def resolve_plan_id(self, plan_id: str | None) -> str:
        """Return plan_id if provided, fall back to the configured default.

        Raises ConfigError when neither is available.
        """
        resolved = plan_id or self.ynab_plan_id
        if not resolved:
            raise ConfigError(
                "plan_id is required but was not provided and YNAB_PLAN_ID is not configured. "
                "Either pass plan_id explicitly or set YNAB_PLAN_ID in your environment."
            )
        return resolved

    def configure_logging(self) -> None:
        level = getattr(logging, self.log_level, logging.INFO)
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton Settings instance, initializing it on first call."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset the singleton for testing."""
    global _settings
    _settings = None
