# beirut_pos/ui/components/table_map.py
from PyQt6.QtWidgets import (
    QWidget, QPushButton, QLabel, QGridLayout, QFrame,
    QSizePolicy, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, QSize

STYLE = """
QFrame#tile { background-color:#2b2b2b; border:1px solid #444; border-radius:12px; }
QPushButton#tableBtn {
  background-color:#3b3b3b; color:#eee; border:0; border-radius:10px; padding:16px; font-weight:700;
}
QPushButton#tableBtn:checked { border:2px solid #4fc3f7; }
QLabel#badge { background:#111; color:#fff; border-radius:10px; padding:2px 8px; }
"""

class TableTile(QFrame):
    def __init__(self, code: str, on_select):
        super().__init__()
        self.setObjectName("tile")
        self.setStyleSheet(STYLE)
        self.code = code

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

    def set_state(self, state: str):
        color = {
            'free': '#2e7d32',
            'occupied': '#f9a825',
            'paid': '#c62828',
            'disabled': '#616161'
        }.get(state, '#2e7d32')
        self.btn.setStyleSheet(
            f"background-color:#3b3b3b; color:white; border:2px solid {color}; "
            f"border-radius:10px; padding:16px; font-weight:700;"
        )

    def set_total(self, cents: int, currency: str = "ج.م"):
        if cents and cents > 0:
            self.badge.setText(f"{currency} {cents/100:.2f}")
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


class TableMap(QWidget):
    MIN_TILE = QSize(160, 120)

    def __init__(self, table_codes, on_select):
        super().__init__()
        self.tiles = {}
        self._current = None
        self._external_select_cb = on_select
        self._table_codes = table_codes
        self._last_cols = -1  # cache to avoid redundant relayouts

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(12, 12, 12, 12)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        for code in table_codes:
            t = TableTile(code, self._on_click)
            t.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.tiles[code] = t

        self._relayout(force=True)

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
