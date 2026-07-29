"""Shared base types used across multiple YNAB resources."""

from __future__ import annotations

from pydantic import BaseModel


class YnabBaseModel(BaseModel):
    """Base model for all YNAB API response shapes."""

    model_config = {"populate_by_name": True, "extra": "ignore"}


class DeltaResponse(YnabBaseModel):
    """Mixin for responses that include server_knowledge for delta sync."""

    server_knowledge: int
