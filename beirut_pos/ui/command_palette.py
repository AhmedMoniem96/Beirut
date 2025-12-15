from __future__ import annotations

from typing import Callable, Iterable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
)


class CommandPaletteDialog(QDialog):
    """Lightweight command palette with fuzzy filtering."""

    def __init__(self, commands: Iterable[dict], parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle("Quick Actions")
        self.resize(520, 420)
        self._commands = list(commands)
        self._filtered: list[dict] = list(self._commands)
        self._selected: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        hint = QLabel("Type to search actions. Press Enter to run or Esc to close.")
        hint.setObjectName("CommandPaletteHint")
        layout.addWidget(hint)

        self.input = QLineEdit(self)
        self.input.setPlaceholderText("Search settings, reports, shortcuts…")
        self.input.textChanged.connect(self._filter)
        self.input.returnPressed.connect(self._accept_selection)
        layout.addWidget(self.input)

        self.list = QListWidget(self)
        self.list.itemDoubleClicked.connect(lambda _item: self._accept_selection())
        layout.addWidget(self.list, 1)

        self._refresh_list()

    def showEvent(self, event):  # noqa: D401 - Qt lifecycle
        super().showEvent(event)
        self.input.selectAll()
        self.input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _filter(self, text: str) -> None:
        query = (text or "").lower()
        if not query:
            self._filtered = list(self._commands)
        else:
            self._filtered = [
                cmd
                for cmd in self._commands
                if query in cmd.get("title", "").lower()
                or query in cmd.get("subtitle", "").lower()
            ]
        self._refresh_list()

    def _refresh_list(self) -> None:
        self.list.clear()
        for cmd in self._filtered:
            label = cmd.get("title", "")
            subtitle = cmd.get("subtitle")
            if subtitle:
                label = f"{label} — {subtitle}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cmd)
            self.list.addItem(item)
        if self.list.count() > 0:
            self.list.setCurrentRow(0)

    def _accept_selection(self) -> None:
        item = self.list.currentItem()
        if not item:
            return
        self._selected = item.data(Qt.ItemDataRole.UserRole)
        self.accept()

    def selected_command(self) -> dict | None:
        return self._selected


def build_command(
    title: str,
    handler: Callable[[], None],
    *,
    subtitle: str = "",
    shortcut: str | None = None,
) -> dict:
    """Helper to create a command palette entry."""

    extra = f" ({shortcut})" if shortcut else ""
    return {
        "title": f"{title}{extra}",
        "subtitle": subtitle,
        "handler": handler,
    }
