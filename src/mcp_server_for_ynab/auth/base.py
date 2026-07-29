"""AuthProvider protocol — the interface all auth implementations must satisfy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class AuthProvider(Protocol):
    """Common interface for auth providers.

    PatAuthProvider reads a static PAT today.
    A future OAuthAuthProvider can implement token refresh behind this interface.
    """

    async def get_access_token(self) -> str:
        """Return a valid Bearer token for the YNAB API."""
        ...

    def describe_mode(self) -> str:
        """Return a short human-readable description of the auth mode."""
        ...
