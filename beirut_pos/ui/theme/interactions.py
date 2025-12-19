"""Interaction helpers (tooltips, animation defaults) for the UI theme."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication, QProxyStyle, QStyle


class InteractionStyle(QProxyStyle):
    """Proxy style that tweaks tooltip timing to feel more responsive."""

    def styleHint(self, hint, option=None, widget=None, returnData=None):  # noqa: N802 (Qt override)
        if hint == QStyle.StyleHint.SH_ToolTip_WakeUpDelay:
            return 350
        if hint == QStyle.StyleHint.SH_ToolTip_FallAsleepDelay:
            return 2600
        return super().styleHint(hint, option, widget, returnData)


def install_interaction_style(app: QApplication) -> None:
    """Layer the proxy style once so tooltip timings are applied app-wide."""

    current = app.style()
    if isinstance(current, InteractionStyle):
        return
    app.setStyle(InteractionStyle(current))
