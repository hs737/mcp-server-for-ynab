"""MCP tool error boundary.

All tool handlers are wrapped with @tool_handler, which catches known
exceptions and converts them to the shared YnabMcpError shape so that AI
agents always receive a structured dict on failure instead of a raw exception.

Error precedence:
  1. YnabMcpException — already has a typed YnabMcpError payload; emit as-is.
  2. ConfigError      — missing/invalid configuration; emit as validation_error.
  3. Any other Exception — unexpected; emit as internal_error and log the
                           full traceback for debugging.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable, Coroutine
from typing import Any

from mcp_server_for_ynab.config.settings import ConfigError
from mcp_server_for_ynab.models.errors import ErrorType, YnabMcpError, YnabMcpException

logger = logging.getLogger(__name__)

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
            return await fn(*args, **kwargs)
        except YnabMcpException as exc:
            logger.warning("Tool %s failed: %s", fn.__name__, exc.error.message)
            return {"error": exc.error.model_dump()}
        except ConfigError as exc:
            error = YnabMcpError(
                error_type=ErrorType.VALIDATION_ERROR,
                message=str(exc),
            )
            logger.warning("Tool %s config error: %s", fn.__name__, exc)
            return {"error": error.model_dump()}
        except Exception as exc:
            error = YnabMcpError(
                error_type=ErrorType.INTERNAL_ERROR,
                message=f"Unexpected error in {fn.__name__}: {exc}",
            )
            logger.exception("Tool %s raised unexpected exception", fn.__name__)
            return {"error": error.model_dump()}

    return wrapper
