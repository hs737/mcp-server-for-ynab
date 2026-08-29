"""Milliunit conversion utilities.

YNAB represents all currency amounts as milliunits: 1000 milliunits = $1.00.
This module provides helpers for converting between milliunits and display strings.

Rules:
  - Raw tools always use milliunits for canonical amount fields.
  - Enriched tools may add a display_amount string alongside milliunit values.
  - Any dollar-input convenience must go through dollars_to_milliunits().
"""

from __future__ import annotations

import math


def milliunits_to_display(milliunits: int, currency_symbol: str = "$") -> str:
    """Convert milliunits to a human-readable currency string.

    Grouped in thousands, because these strings exist to be read by a person and
    an unseparated "$14840.36" has to be counted rather than recognised. Every
    enriched tool emits these alongside its canonical milliunit values, so the
    separator is the difference between a figure someone can scan and one they
    have to parse.

    >>> milliunits_to_display(12500)
    '$12.50'
    >>> milliunits_to_display(-5000)
    '-$5.00'
    >>> milliunits_to_display(0)
    '$0.00'
    >>> milliunits_to_display(14840360)
    '$14,840.36'
    >>> milliunits_to_display(-1234567890)
    '-$1,234,567.89'
    """
    negative = milliunits < 0
    abs_milliunits = abs(milliunits)
    dollars = abs_milliunits // 1000
    cents = (abs_milliunits % 1000) // 10
    sign = "-" if negative else ""
    return f"{sign}{currency_symbol}{dollars:,}.{cents:02d}"


def dollars_to_milliunits(dollars: float) -> int:
    """Convert a dollar amount to milliunits (rounds to nearest milliunit).

    >>> dollars_to_milliunits(1.00)
    1000
    >>> dollars_to_milliunits(12.50)
    12500
    >>> dollars_to_milliunits(-5.99)
    -5990
    """
    return math.floor(dollars * 1000 + 0.5) if dollars >= 0 else -math.floor(abs(dollars) * 1000 + 0.5)


def milliunits_to_dollars(milliunits: int) -> float:
    """Convert milliunits to a float dollar amount.

    >>> milliunits_to_dollars(12500)
    12.5
    >>> milliunits_to_dollars(-5000)
    -5.0
    """
    return milliunits / 1000.0
