"""Unit tests: field length limits taken from YNAB's API specification.

Catching an over-long memo locally turns a 400 relayed through two layers into
a validation error naming the field. It matters most for bulk writes: YNAB
rejects the whole request, so one bad memo in a batch of forty fails the other
thirty-nine.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mcp_server_for_ynab.models.ynab.categories import SaveCategoryGroup
from mcp_server_for_ynab.models.ynab.limits import (
    CATEGORY_GROUP_NAME_MAX,
    MEMO_MAX,
    PAYEE_NAME_MAX,
    TRANSACTION_PAYEE_NAME_MAX,
)
from mcp_server_for_ynab.models.ynab.payees import SavePayee
from mcp_server_for_ynab.models.ynab.transactions import SaveTransaction


def _save(**overrides: object) -> SaveTransaction:
    return SaveTransaction(account_id="a1", date="2026-08-01", amount=-1000, **overrides)  # type: ignore[arg-type]


def test_memo_at_the_limit_is_accepted() -> None:
    assert _save(memo="x" * MEMO_MAX).memo is not None


def test_memo_past_the_limit_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _save(memo="x" * (MEMO_MAX + 1))


def test_transaction_payee_name_past_the_limit_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _save(payee_name="x" * (TRANSACTION_PAYEE_NAME_MAX + 1))


def test_the_two_payee_limits_are_not_the_same() -> None:
    """YNAB caps payee_name at 200 on transactions and the payee itself at 500."""
    assert TRANSACTION_PAYEE_NAME_MAX < PAYEE_NAME_MAX

    long_name = "x" * (TRANSACTION_PAYEE_NAME_MAX + 1)
    assert SavePayee(name=long_name).name == long_name  # fine on the payee route

    with pytest.raises(ValidationError):
        _save(payee_name=long_name)  # too long on the transaction route


def test_payee_name_past_its_own_limit_is_rejected() -> None:
    with pytest.raises(ValidationError):
        SavePayee(name="x" * (PAYEE_NAME_MAX + 1))


def test_category_group_name_is_capped() -> None:
    assert SaveCategoryGroup(name="x" * CATEGORY_GROUP_NAME_MAX).name

    with pytest.raises(ValidationError):
        SaveCategoryGroup(name="x" * (CATEGORY_GROUP_NAME_MAX + 1))
