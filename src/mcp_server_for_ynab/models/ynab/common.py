"""Shared base types used across multiple YNAB resources."""

from __future__ import annotations

import html
from typing import Any

from pydantic import BaseModel, model_validator


class YnabBaseModel(BaseModel):
    """Base model for all YNAB API response shapes."""

    model_config = {"populate_by_name": True, "extra": "ignore"}


# Free-text fields YNAB may return HTML-escaped. Bank imports are the usual
# source: a payee comes back as "B&amp;H Photo Video", and an assistant that
# repeats it verbatim shows the user something they did not type and cannot
# search for. Restricted to named fields rather than every string, because ids
# and dates never carry entities and blanket decoding invites surprises.
_TEXT_FIELDS = frozenset(
    {
        "account_name",
        "category_group_name",
        "category_name",
        "import_payee_name",
        "import_payee_name_original",
        "memo",
        "name",
        "note",
        "payee_name",
        "transfer_account_name",
    }
)


class DecodedTextModel(YnabBaseModel):
    """A response model whose free-text fields are HTML-unescaped on the way in.

    Applied only to response shapes. The Save and Update models deliberately do
    not inherit it: a write must send exactly what the caller supplied, and
    silently rewriting an outgoing memo is a different and worse bug than
    showing an escaped one.
    """

    @model_validator(mode="before")
    @classmethod
    def _decode_text(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        decoded: dict[str, Any] | None = None
        for key in _TEXT_FIELDS:
            value = data.get(key)
            if isinstance(value, str) and "&" in value:
                unescaped = html.unescape(value)
                if unescaped != value:
                    if decoded is None:
                        decoded = dict(data)
                    decoded[key] = unescaped

        return decoded if decoded is not None else data


class DeltaResponse(YnabBaseModel):
    """Mixin for responses that include server_knowledge for delta sync."""

    server_knowledge: int
