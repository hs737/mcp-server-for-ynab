"""Unit tests: YnabMcpError and YnabMcpException shapes."""

from __future__ import annotations

import pytest

from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpError, YnabMcpException


def test_auth_failure_factory() -> None:
    e = YnabMcpError.auth_failure()
    assert e.error_type == ErrorType.AUTH_FAILURE
    assert e.status_code == 401


def test_rate_limited_factory_with_retry_after() -> None:
    e = YnabMcpError.rate_limited(retry_after=30)
    assert e.error_type == ErrorType.RATE_LIMITED
    assert e.status_code == 429
    assert e.retry_after == 30


def test_rate_limited_factory_without_retry_after() -> None:
    e = YnabMcpError.rate_limited()
    assert e.retry_after is None


def test_not_found_factory() -> None:
    e = YnabMcpError.not_found("transaction")
    assert e.error_type == ErrorType.NOT_FOUND
    assert e.status_code == 404
    assert "transaction" in e.message


@pytest.mark.parametrize(
    "status_code,expected_type",
    [
        (401, ErrorType.AUTH_FAILURE),
        (404, ErrorType.NOT_FOUND),
        (409, ErrorType.CONFLICT),
        (429, ErrorType.RATE_LIMITED),
        (500, ErrorType.YNAB_API_ERROR),
        (422, ErrorType.YNAB_API_ERROR),
    ],
)
def test_from_ynab_response_maps_status(status_code: int, expected_type: ErrorType) -> None:
    e = YnabMcpError.from_ynab_response(status_code=status_code)
    assert e.error_type == expected_type
    assert e.status_code == status_code


def test_from_ynab_response_preserves_names() -> None:
    e = YnabMcpError.from_ynab_response(
        status_code=422,
        error_name="bad_request",
        error_id="ERR-001",
        detail="Budget not found.",
    )
    assert e.ynab_error_name == "bad_request"
    assert e.ynab_error_id == "ERR-001"
    assert "Budget not found." in e.message


def test_exception_wraps_error() -> None:
    error = YnabMcpError.auth_failure()
    exc = YnabMcpException(error)
    assert isinstance(exc, Exception)
    assert exc.error is error
    assert str(exc) == error.message


def test_model_dump_is_serializable() -> None:
    data = YnabMcpError.auth_failure().model_dump()
    assert isinstance(data, dict)
    assert data["error_type"] == "auth_failure"
