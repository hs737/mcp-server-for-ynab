"""Shared error shape for all MCP tool failures."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ErrorType(StrEnum):
    AUTH_FAILURE = "auth_failure"
    RATE_LIMITED = "rate_limited"
    NOT_FOUND = "not_found"
    VALIDATION_ERROR = "validation_error"
    CONFLICT = "conflict"
    TRANSPORT_ERROR = "transport_error"
    YNAB_API_ERROR = "ynab_api_error"
    INTERNAL_ERROR = "internal_error"


class YnabMcpError(BaseModel):
    """Normalized error returned by all tools on failure.

    AI agents can reliably inspect error_type to decide how to recover.
    For rate_limited errors, retry_after is set when YNAB provides it.
    """

    error_type: ErrorType
    message: str
    status_code: int | None = None
    retry_after: int | None = None
    details: dict[str, object] | None = None
    ynab_error_name: str | None = None
    ynab_error_id: str | None = None

    @classmethod
    def auth_failure(cls, message: str = "Authentication failed.") -> YnabMcpError:
        return cls(error_type=ErrorType.AUTH_FAILURE, message=message, status_code=401)

    @classmethod
    def rate_limited(cls, retry_after: int | None = None) -> YnabMcpError:
        return cls(
            error_type=ErrorType.RATE_LIMITED,
            message="YNAB API rate limit reached. Retry after the indicated delay.",
            status_code=429,
            retry_after=retry_after,
        )

    @classmethod
    def not_found(cls, resource: str = "resource") -> YnabMcpError:
        return cls(
            error_type=ErrorType.NOT_FOUND,
            message=f"The requested {resource} was not found.",
            status_code=404,
        )

    @classmethod
    def validation_error(cls, message: str) -> YnabMcpError:
        return cls(error_type=ErrorType.VALIDATION_ERROR, message=message)

    @classmethod
    def from_ynab_response(
        cls,
        status_code: int,
        error_name: str | None = None,
        error_id: str | None = None,
        detail: str | None = None,
        retry_after: int | None = None,
    ) -> YnabMcpError:
        """Map a YNAB API error response to the shared error shape."""
        if status_code == 401:
            error_type = ErrorType.AUTH_FAILURE
            message = detail or "YNAB API authentication failed. Check YNAB_API_KEY."
        elif status_code == 404:
            error_type = ErrorType.NOT_FOUND
            message = detail or "The requested resource was not found."
        elif status_code == 409:
            error_type = ErrorType.CONFLICT
            message = detail or "Conflict: the request conflicts with existing data."
        elif status_code == 429:
            error_type = ErrorType.RATE_LIMITED
            message = detail or "Rate limited by YNAB API."
        else:
            error_type = ErrorType.YNAB_API_ERROR
            message = detail or f"YNAB API returned status {status_code}."

        return cls(
            error_type=error_type,
            message=message,
            status_code=status_code,
            retry_after=retry_after,
            ynab_error_name=error_name,
            ynab_error_id=error_id,
        )


class YnabMcpException(Exception):
    """Raised by the HTTP client and ynab_client layer on API failures.

    Carries a structured YnabMcpError payload so tool handlers can either
    propagate the exception or serialize error.model_dump() back to the agent.
    """

    def __init__(self, error: YnabMcpError) -> None:
        self.error = error
        super().__init__(error.message)
