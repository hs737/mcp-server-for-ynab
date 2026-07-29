"""Unit tests: milliunit conversion helpers."""

from __future__ import annotations

import pytest

from mcp_server_for_ynab.models.amounts import dollars_to_milliunits, milliunits_to_display, milliunits_to_dollars


@pytest.mark.parametrize(
    "milliunits,expected",
    [
        (1000, "$1.00"),
        (-1000, "-$1.00"),
        (0, "$0.00"),
        (1500, "$1.50"),
        (-999, "-$0.99"),  # sub-cent milliunit truncated to 2 decimal places
        (100_000, "$100.00"),
        (-50_000, "-$50.00"),
    ],
)
def test_milliunits_to_display(milliunits: int, expected: str) -> None:
    assert milliunits_to_display(milliunits) == expected


@pytest.mark.parametrize(
    "milliunits,expected",
    [
        (1000, 1.0),
        (-1000, -1.0),
        (0, 0.0),
        (1500, 1.5),
        (999, 0.999),
    ],
)
def test_milliunits_to_dollars(milliunits: int, expected: float) -> None:
    assert milliunits_to_dollars(milliunits) == expected


@pytest.mark.parametrize(
    "dollars,expected",
    [
        (1.0, 1000),
        (-1.0, -1000),
        (0.0, 0),
        (1.5, 1500),
        (0.001, 1),
        (100.0, 100_000),
    ],
)
def test_dollars_to_milliunits(dollars: float, expected: int) -> None:
    assert dollars_to_milliunits(dollars) == expected


def test_roundtrip(ynab_env: None = None) -> None:
    for amount in [1000, -2500, 99999, -1]:
        assert dollars_to_milliunits(milliunits_to_dollars(amount)) == amount
