"""Application launcher for Beirut POS."""

from __future__ import annotations

import importlib.util
import os
import sys

from beirut_pos.utils.error_handling import console_notifier, log_exception


def _infer_mode_from_executable() -> str | None:
    executable_name = os.path.basename(sys.argv[0]).lower()
    if "jewelry" in executable_name:
        return "jewelry"
    if "playstation" in executable_name:
        return "playstation"
    return None


def _is_desktop_context() -> bool:
    if sys.platform == "win32":
        return True
    if os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"):
        return True
    platform = os.getenv("QT_QPA_PLATFORM", "").lower()
    return platform not in {"", "offscreen"}


def _get_qt_widgets():
    if importlib.util.find_spec("PyQt6.QtWidgets") is None:
        return None
    from PyQt6.QtWidgets import QApplication, QMessageBox

    return QApplication, QMessageBox


def _notify_app_mode_error(raw_mode: str | None) -> None:
    title = "Invalid APP_MODE configuration"
    guidance = (
        "APP_MODE must be set to one of the following values:\n"
        "  - playstation\n"
        "  - jewelry\n\n"
        "Set it before launching, for example:\n"
        "  export APP_MODE=playstation\n"
        "  # or\n"
        "  export APP_MODE=jewelry\n"
    )
    exc = ValueError(f"Unsupported APP_MODE: {raw_mode!r}")
    log_path = log_exception("APP_MODE configuration", exc, extra=guidance)
    details_parts = [f"Received APP_MODE: {raw_mode!r}"]
    if log_path:
        details_parts.append(f"Log saved to: {log_path}")
    details = "\n".join(details_parts)

    if _is_desktop_context():
        qt_widgets = _get_qt_widgets()
        if qt_widgets is not None:
            QApplication, QMessageBox = qt_widgets
            app = QApplication.instance() or QApplication(sys.argv)
            box = QMessageBox()
            box.setWindowTitle(title)
            box.setText(guidance)
            box.setDetailedText(details)
            box.setIcon(QMessageBox.Icon.Critical)
            box.exec()
            return

    console_notifier(title, guidance, details, stream=sys.stderr)


def run() -> None:
    raw_mode = os.getenv("APP_MODE")
    if raw_mode is None:
        raw_mode = _infer_mode_from_executable()
    if raw_mode is None:
        _notify_app_mode_error(raw_mode)
        raise SystemExit(1)

    mode = raw_mode.strip().lower()
    if mode == "playstation":
        from beirut_pos.apps.playstation.app import run as app_run
    elif mode == "jewelry":
        from beirut_pos.apps.jewelry.app import run as app_run
    else:
        _notify_app_mode_error(mode)
        raise SystemExit(1)

    app_run()


if __name__ == "__main__":
    run()
