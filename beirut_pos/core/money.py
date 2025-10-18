"""Helpers for working with Egyptian Pound (LE) currency values."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

_DECIMAL_2_PLACES = Decimal("0.01")


def to_le(value: Any) -> Decimal:
    """Convert *value* to a :class:`~decimal.Decimal` rounded to two places."""
    if isinstance(value, Decimal):
        quantized = value
    else:
        quantized = Decimal(str(value))
    return quantized.quantize(_DECIMAL_2_PLACES, rounding=ROUND_HALF_UP)


def fmt_le(value: Any) -> str:
    """Format *value* as an LE string with two decimal places."""
    amount = to_le(value)
    return f"LE {amount}"  # Arabic UI still prefixes with Latin letters per design


def cents_to_le(cents: int | float | str | Decimal | None) -> Decimal:
    """Convert legacy *cents* integers into rounded LE decimals."""
    if cents is None:
        return Decimal("0")
    return to_le(Decimal(cents) / Decimal(100))


def le_to_cents(value: Any) -> int:
    """Return an integer cent representation for compatibility paths."""
    amount = to_le(value)
    return int(amount * Decimal(100))
