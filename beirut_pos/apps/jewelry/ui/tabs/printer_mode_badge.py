"""Shared printer mode badge helpers for Jewelry tabs."""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel

from ...services.i18n import t
from ...services.settings import PRINTER_MODE_LABEL, get_printer_mode

RECEIPT_BADGE_STYLE = (
    "font-size: 11px; font-weight: 600; color: #0f5132; background: #d1e7dd; "
    "border: 1px solid #badbcc; border-radius: 8px; padding: 2px 8px;"
)
LABEL_BADGE_STYLE = (
    "font-size: 11px; font-weight: 600; color: #664d03; background: #fff3cd; "
    "border: 1px solid #ffecb5; border-radius: 8px; padding: 2px 8px;"
)


def refresh_printer_mode_badge(badge: QLabel, language: str) -> None:
    """Apply current printer mode text and style to a badge label."""
    is_label_mode = get_printer_mode() == PRINTER_MODE_LABEL
    mode_label = (
        t("settings.printer_mode_label", language=language)
        if is_label_mode
        else t("settings.printer_mode_receipt", language=language)
    )
    badge_prefix = t("settings.printer_mode", language=language)
    badge.setStyleSheet(LABEL_BADGE_STYLE if is_label_mode else RECEIPT_BADGE_STYLE)
    badge.setText(f"{badge_prefix}: {mode_label}")
