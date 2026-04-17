"""Date helpers for Jewelry UI input/output formatting."""

from __future__ import annotations

from datetime import datetime
from typing import Optional


_ISO_DATE_FORMAT = "%Y-%m-%d"
_UI_DATE_FORMAT = "%d/%m/%Y"


def parse_iso_or_ui_date(value: str) -> Optional[datetime]:
    """Parse legacy ISO or UI date text into a datetime date value."""
    if not value:
        return None
    clean_value = value.strip()
    if not clean_value:
        return None
    for fmt in (_ISO_DATE_FORMAT, _UI_DATE_FORMAT):
        try:
            return datetime.strptime(clean_value, fmt)
        except ValueError:
            continue
    return None


def to_iso_date(value: str) -> str:
    """Convert supported date input to ISO YYYY-MM-DD for persistence."""
    parsed = parse_iso_or_ui_date(value)
    if not parsed:
        return ""
    return parsed.strftime(_ISO_DATE_FORMAT)


def to_ui_date(value: str) -> str:
    """Convert supported date input to dd/MM/yyyy for UI display."""
    parsed = parse_iso_or_ui_date(value)
    if not parsed:
        return value
    return parsed.strftime(_UI_DATE_FORMAT)
