"""Unit tests: Settings loading and resolve_plan_id."""

from __future__ import annotations

import pytest

from ynab_mcp.config.settings import ConfigError, Settings, get_settings


def test_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("YNAB_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="YNAB_API_KEY"):
        Settings()


def test_loads_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_API_KEY", "my-secret-key")
    s = Settings()
    assert s.ynab_api_key == "my-secret-key"


def test_plan_id_optional(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_API_KEY", "k")
    monkeypatch.delenv("YNAB_PLAN_ID", raising=False)
    assert Settings().ynab_plan_id is None


def test_plan_id_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_API_KEY", "k")
    monkeypatch.setenv("YNAB_PLAN_ID", "plan-abc")
    assert Settings().ynab_plan_id == "plan-abc"


def test_resolve_explicit_plan_id(ynab_env: None) -> None:
    s = Settings()
    assert s.resolve_plan_id("explicit-id") == "explicit-id"


def test_resolve_falls_back_to_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_API_KEY", "k")
    monkeypatch.setenv("YNAB_PLAN_ID", "env-plan")
    s = Settings()
    assert s.resolve_plan_id(None) == "env-plan"


def test_resolve_raises_when_neither_set(ynab_env: None) -> None:
    s = Settings()
    with pytest.raises(ConfigError, match="plan_id"):
        s.resolve_plan_id(None)


def test_get_settings_singleton(ynab_env: None) -> None:
    a = get_settings()
    b = get_settings()
    assert a is b


def test_log_level_default(ynab_env: None) -> None:
    assert Settings().log_level == "INFO"


def test_log_level_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YNAB_API_KEY", "k")
    monkeypatch.setenv("LOG_LEVEL", "debug")
    assert Settings().log_level == "DEBUG"
