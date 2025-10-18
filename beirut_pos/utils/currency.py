"""Currency formatting helpers for Beirut POS.

The application stores monetary amounts internally as integers that represent
"cents".  A lot of stakeholders however prefer to read the values in whole
pounds without trailing decimals.  The helpers below encapsulate this
presentation logic so every UI element and report is consistent.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def _to_decimal_cents(amount_cents: int | float | None) -> Decimal:
    """Normalize incoming values so rounding behaves consistently."""

    if amount_cents is None:
        return Decimal(0)
    # Using ``str`` preserves precision for integers while supporting floats.
    try:
        return Decimal(str(amount_cents))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(0)


def format_pounds(amount_cents: int | float | None, currency: str = "ج.م") -> str:
    """Return a human friendly amount using pound units with no fractional cents."""

    cents = _to_decimal_cents(amount_cents).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    pounds = (cents / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    pounds_int = int(pounds)
    sign = "-" if pounds_int < 0 else ""
    display = f"{abs(pounds_int):,}"
    if currency:
        return f"{currency} {sign}{display}"
    return f"{sign}{display}"


def pounds_value(amount_cents: int | float | None) -> str:
    """Shorthand formatter that omits the currency label."""

    return format_pounds(amount_cents, currency="").strip()

