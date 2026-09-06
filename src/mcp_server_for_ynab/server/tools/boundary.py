"""MCP tool error boundary.

All tool handlers are wrapped with @tool_handler, which catches known
exceptions and converts them to the shared YnabMcpError shape so that AI
agents always receive a structured dict on failure instead of a raw exception.

Error precedence:
  1. YnabMcpException — already has a typed YnabMcpError payload; emit as-is.
  2. ConfigError      — missing/invalid configuration; emit as validation_error.
  3. ValidationError  — the caller's arguments failed a model constraint, such
                        as a memo past YNAB's 500-character cap; emit as
                        validation_error, because it is the caller's input that
                        is wrong and an agent can fix it and retry.
  4. Any other Exception — unexpected; emit as internal_error and log the
                           full traceback for debugging.

Every response, success or failure, also carries the request-budget trailer.
YNAB's hourly limit is the binding constraint on a long working session, and an
agent that can see `requests_remaining` on the answer it already has will pace
itself; one that has to spend a call to ask will not ask. The numbers are two
integers, which is a price worth paying on every payload.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from pydantic import ValidationError

from mcp_server_for_ynab.config.settings import ConfigError
from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpError, YnabMcpException

logger = logging.getLogger(__name__)


def _budget_trailer() -> dict[str, Any]:
    """What the rate budget has left, or nothing if it cannot be read.

    Imported here rather than at module scope because the context is bound at
    startup and this module is imported while tools are still registering. Any
    failure is swallowed: a missing trailer is a smaller problem than a tool
    that reports an internal error because the trailer could not be built.
    """
    from mcp_server_for_ynab.server.context import get_app_context

    try:
        return dict(get_app_context().http.budget.trailer())
    except Exception:  # pragma: no cover - defensive; no context, or a stubbed one
        return {}


def _with_trailer(payload: dict[str, Any]) -> dict[str, Any]:
    trailer = _budget_trailer()
    # A tool that reports the budget as its subject keeps its own numbers.
    if not trailer or "requests_used_this_hour" in payload:
        return payload
    return {**payload, **trailer}


type _AsyncToolFn[**P] = Callable[P, Coroutine[Any, Any, dict[str, Any]]]


def tool_handler[**P](fn: _AsyncToolFn[P]) -> _AsyncToolFn[P]:
    """Wrap an async tool handler with structured exception handling.

    Apply between @mcp.tool(...) and the function definition so the registered
    function is the wrapped one:

        @mcp.tool(name="my_tool", ...)
        @tool_handler
        async def my_tool(...) -> dict[str, Any]:
            ...
    """

    @functools.wraps(fn)
    async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return _with_trailer(await fn(*args, **kwargs))
        except YnabMcpException as exc:
            logger.warning("Tool %s failed: %s", fn.__name__, exc.error.message)
            return _with_trailer({"error": exc.error.model_dump()})
        except ConfigError as exc:
            error = YnabMcpError(
                error_type=ErrorType.VALIDATION_ERROR,
                message=str(exc),
            )
            logger.warning("Tool %s config error: %s", fn.__name__, exc)
            return _with_trailer({"error": error.model_dump()})
        except ValidationError as exc:
            # Reported as a validation error rather than an internal one: the
            # input is the thing that is wrong, and an agent told which field
            # and which limit can correct the call itself.
            details = [
                {"field": ".".join(str(part) for part in problem["loc"]), "problem": problem["msg"]}
                for problem in exc.errors()
            ]
            error = YnabMcpError(
                error_type=ErrorType.VALIDATION_ERROR,
                message=f"Invalid arguments for {fn.__name__}: {exc.error_count()} field(s) failed validation.",
                details={"fields": details},
            )
            logger.warning("Tool %s validation error: %s", fn.__name__, details)
            return _with_trailer({"error": error.model_dump()})
        except Exception as exc:
            error = YnabMcpError(
                error_type=ErrorType.INTERNAL_ERROR,
                message=f"Unexpected error in {fn.__name__}: {exc}",
            )
            logger.exception("Tool %s raised unexpected exception", fn.__name__)
            return _with_trailer({"error": error.model_dump()})

    return wrapper
