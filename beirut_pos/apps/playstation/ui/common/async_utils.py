"""Small helpers for async-like UX niceties (debounce, task toasts, loaders)."""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, QTimer, Qt
from PyQt6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from beirut_pos.core.bus import bus


class Debouncer(QObject):
    """Schedule a single callback run after the user stops typing/clicking."""

    def __init__(self, callback: Callable[[], None], delay_ms: int = 300, parent: QObject | None = None):
        super().__init__(parent)
        self._callback = callback
        self._delay_ms = max(1, int(delay_ms))
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._callback)

    def trigger(self) -> None:
        """Start (or restart) the countdown for the callback."""

        self._timer.start(self._delay_ms)

    def flush(self) -> None:
        """Run the callback immediately, cancelling any pending timer."""

        if self._timer.isActive():
            self._timer.stop()
        self._callback()


def emit_task_status(message: str, level: str = "info") -> None:
    """Broadcast a task status toast to the main window banner."""

    bus.emit("task_status", message, level)


def build_busy_placeholder(message: str) -> QWidget:
    """Return a compact loading placeholder with an indeterminate bar."""

    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(12)

    label = QLabel(message)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    bar = QProgressBar()
    bar.setRange(0, 0)
    bar.setMaximumHeight(16)
    layout.addWidget(bar)

    return wrapper
