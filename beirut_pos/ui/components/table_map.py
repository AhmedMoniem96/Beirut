# beirut_pos/ui/components/table_map.py
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QLabel, QGridLayout, QFrame,
    QSizePolicy, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, QSize

from ...utils.currency import format_pounds
STYLE = """
QFrame#tile { background-color:#2b2b2b; border:1px solid #444; border-radius:12px; }
QPushButton#tableBtn {
  background-color:#3b3b3b; color:#eee; border:0; border-radius:10px; padding:16px; font-weight:700;
}
QPushButton#tableBtn:checked { border:2px solid #4fc3f7; }
QLabel#badge { background:#111; color:#fff; border-radius:10px; padding:2px 8px; }
QLabel#reservedLabel { color:#f8bbd0; font-weight:600; }
"""

RESERVED_BORDER = "#8e24aa"


def _format_ampm(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    return f"{hour:02d}:{dt.minute:02d} {suffix}"

class TableTile(QFrame):
    def __init__(self, code: str, on_select):
        super().__init__()
        self.setObjectName("tile")
        self.setStyleSheet(STYLE)
        self.code = code
        self._state = "free"
        self._reserved_for: datetime | None = None
        self._reserved_text: str | None = None

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)

        # Top row: PS indicator + amount badge
        top = QHBoxLayout()
        top.setSpacing(6)

        self.ps = QLabel()              # 🎮 tiny indicator
        self.ps.setFixedSize(18, 18)
        self.ps.setToolTip("PlayStation قيد الاستخدام")
        self.ps.hide()

        self.badge = QLabel("")
        self.badge.setObjectName("badge")
        self.badge.hide()

        top.addWidget(self.ps)
        top.addStretch(1)
        top.addWidget(self.badge)
        v.addLayout(top)

        # Main button
        self.btn = QPushButton(code)
        self.btn.setObjectName("tableBtn")
        self.btn.setCheckable(True)
        self.btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.btn.clicked.connect(lambda: on_select(code))
        v.addWidget(self.btn, 1)

        self.reserved_label = QLabel("")
        self.reserved_label.setObjectName("reservedLabel")
        self.reserved_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reserved_label.hide()
        v.addWidget(self.reserved_label)

    def set_state(self, state: str):
        self._state = state
        self._apply_style()

    def set_total(self, cents: int, currency: str = "ج.م"):
        if cents and cents > 0:
            self.badge.setText(format_pounds(cents, currency))
            self.badge.show()
        else:
            self.badge.hide()

    def set_ps_active(self, active: bool):
        if active:
            self.ps.setText("🎮")
            self.ps.show()
        else:
            self.ps.hide()

    def set_checked(self, checked: bool):
        self.btn.setChecked(checked)

    def set_reserved(self, reserved_iso: str | None):
        self._reserved_for = None
        self._reserved_text = None
        if reserved_iso:
            text = str(reserved_iso)
            try:
                dt = datetime.fromisoformat(text)
            except Exception:
                dt = None
            if dt is not None:
                self._reserved_for = dt
                text = _format_ampm(dt)
            self._reserved_text = text
            self.reserved_label.setText(f"Reserved at {text}")
            self.reserved_label.show()
            self.btn.setToolTip(f"Reserved at {text}")
        else:
            self.reserved_label.hide()
            self.btn.setToolTip("")
        self._apply_style()

    def _apply_style(self):
        palette = {
            'free': '#2e7d32',
            'occupied': '#f9a825',
            'paid': '#c62828',
            'disabled': '#616161'
        }
        color = palette.get(self._state, '#2e7d32')
        if self._reserved_text:
            if self._state == 'free':
                color = RESERVED_BORDER
            self.reserved_label.show()
        else:
            self.reserved_label.hide()
        self.btn.setStyleSheet(
            f"background-color:#3b3b3b; color:white; border:2px solid {color}; "
            f"border-radius:10px; padding:16px; font-weight:700;"
        )


class TableMap(QWidget):
    MIN_TILE = QSize(160, 120)

    def __init__(self, table_codes, on_select):
        super().__init__()
        self.tiles = {}
        self._current = None
        self._external_select_cb = on_select
        self._table_codes = []
        self._last_cols = -1  # cache to avoid redundant relayouts
        self._reservations: dict[str, str] = {}

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(12, 12, 12, 12)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.set_table_codes(table_codes, reset_selection=True)

    # <<< THIS WAS MISSING
    def _on_click(self, code: str):
        if self._current and self._current != code:
            self.tiles[self._current].set_checked(False)
        self._current = code
        self._external_select_cb(code)

    def clear_selection(self):
        if self._current and self._current in self.tiles:
            self.tiles[self._current].set_checked(False)
        self._current = None

    def set_table_codes(self, codes, reset_selection: bool = False):
        cleaned = [str(code).strip().upper() for code in codes if str(code).strip()]
        cleaned = [code for i, code in enumerate(cleaned) if code not in cleaned[:i]]
        if not cleaned:
            cleaned = []
        if cleaned == self._table_codes:
            return

        # remove tiles no longer present
        current_set = set(self.tiles)
        new_set = set(cleaned)
        for code in current_set - new_set:
            widget = self.tiles.pop(code)
            widget.setParent(None)
            widget.deleteLater()

        for code in cleaned:
            if code not in self.tiles:
                tile = TableTile(code, self._on_click)
                tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                tile.set_reserved(self._reservations.get(code))
                self.tiles[code] = tile

        self._table_codes = cleaned
        if reset_selection or (self._current and self._current not in cleaned):
            self.clear_selection()
        self._relayout(force=True)

    def update_table(self, code, state: str = None, total_cents: int = None, ps_active: bool = None):
        t = self.tiles.get(code)
        if not t:
            return
        if state is not None:
            t.set_state(state)
        if total_cents is not None:
            t.set_total(total_cents)
        if ps_active is not None:
            t.set_ps_active(ps_active)

    def set_reservations(self, reservations: dict[str, str]):
        normalized: dict[str, str] = {}
        for code, value in reservations.items():
            if not code:
                continue
            normalized[code.strip().upper()] = value
        self._reservations = normalized
        for code, tile in self.tiles.items():
            tile.set_reserved(self._reservations.get(code))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def _relayout(self, force: bool = False):
        width = max(self.width(), 1)
        cols = max(
            3,
            min(len(self._table_codes),
                width // (self.MIN_TILE.width() + self.grid.horizontalSpacing()))
        )
        if not force and cols == self._last_cols:
            return
        self._last_cols = cols

        # remove positions (but keep widgets alive)
        while self.grid.count():
            self.grid.takeAt(0)

        for i, code in enumerate(self._table_codes):
            r, c = divmod(i, cols)
            self.grid.addWidget(self.tiles[code], r, c)
