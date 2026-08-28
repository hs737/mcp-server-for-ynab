"""Unit tests: HTML entity decoding on response models.

YNAB returns some free text HTML-escaped, and bank imports are the usual
source. An assistant that repeats "B&amp;H Photo Video" back shows the user
something they never typed and cannot search for.

The direction matters as much as the decoding: responses are decoded, writes
are not. Silently rewriting an outgoing memo is a worse bug than displaying an
escaped one.
"""

from __future__ import annotations

from mcp_server_for_ynab.models.ynab.payees import Payee
from mcp_server_for_ynab.models.ynab.transactions import SaveTransaction, Transaction


def _transaction(**overrides: object) -> Transaction:
    payload: dict[str, object] = {
        "id": "t1",
        "date": "2026-08-01",
        "amount": -1000,
        "cleared": "cleared",
        "approved": True,
        "account_id": "a1",
        "account_name": "Checking",
        "deleted": False,
    }
    payload.update(overrides)
    return Transaction.model_validate(payload)


def test_payee_names_are_decoded() -> None:
    txn = _transaction(payee_name="B&amp;H Photo Video")
    assert txn.payee_name == "B&H Photo Video"


def test_memos_are_decoded() -> None:
    assert _transaction(memo="Lunch &amp; coffee").memo == "Lunch & coffee"


def test_numeric_and_named_entities_both_decode() -> None:
    assert _transaction(memo="caf&#233; &amp; bar").memo == "café & bar"


def test_text_without_entities_is_untouched() -> None:
    assert _transaction(payee_name="Whole Foods").payee_name == "Whole Foods"


def test_a_bare_ampersand_survives() -> None:
    """Already-decoded text must not be mangled by a second pass."""
    assert _transaction(payee_name="Marks & Spencer").payee_name == "Marks & Spencer"


def test_decoding_applies_across_response_models() -> None:
    payee = Payee.model_validate({"id": "p1", "name": "AT&amp;T", "deleted": False})
    assert payee.name == "AT&T"


def test_writes_send_exactly_what_the_caller_supplied() -> None:
    """Save models deliberately do not decode."""
    save = SaveTransaction(account_id="a1", date="2026-08-01", amount=-1000, memo="Literal &amp; intended")
    assert save.memo == "Literal &amp; intended"


def test_identifiers_are_never_rewritten() -> None:
    """Only named free-text fields decode; ids and dates are left alone."""
    txn = _transaction(id="t&amp;1", payee_name="X")
    assert txn.id == "t&amp;1"
