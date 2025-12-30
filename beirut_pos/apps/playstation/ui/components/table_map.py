# beirut_pos/ui/components/table_map.py
from datetime import datetime, timedelta
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QWidget, QPushButton, QLabel, QGridLayout, QFrame,
    QSizePolicy, QVBoxLayout, QHBoxLayout
)
from PyQt6.QtCore import Qt, QSize, QTimer

from ...utils.currency import format_pounds

STYLE = """
QFrame#tile { background-color:#2b2b2b; border:1px solid #444; border-radius:12px; }
QPushButton#tableBtn {
  background-color:#3b3b3b; color:#eee; border:0; border-radius:10px; padding:16px; font-weight:700;
}
QPushButton#tableBtn:checked { border:2px solid #4fc3f7; }
QLabel#badge { background:#111; color:#fff; border-radius:10px; padding:2px 8px; }
QLabel#reservedLabel { color:#f8bbd0; font-weight:600; }
QLabel#psTimer { color:#ff9800; font-weight:700; padding:0 6px; font-size:11px; }
"""

RESERVED_BORDER = "#8e24aa"


def _format_ampm(dt: datetime) -> str:
    hour = dt.hour % 12 or 12
    suffix = "AM" if dt.hour < 12 else "PM"
    return f"{hour:02d}:{dt.minute:02d} {suffix}"


class TableTile(QFrame):
    def __init__(self, code: str, on_select: Callable[[str], None]):
        super().__init__()
        self.setObjectName("tile")
        self.setStyleSheet(STYLE)
        self.code = code
        self._state = "free"
        self._reservations = None
        self._ps_running = False
        self._ps_elapsed = 0  # seconds

        v = QVBoxLayout(self)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)

        # Top: PS timer + badge on the right
        top = QHBoxLayout()
        top.setSpacing(6)

        self.ps_timer = QLabel("")  # timer text only
        self.ps_timer.setObjectName("psTimer")
        self.ps_timer.hide()

        top.addStretch(1)
        top.addWidget(self.ps_timer)
        self.badge = QLabel("")
        self.badge.setObjectName("badge")
        self.badge.hide()
        top.addWidget(self.badge)
        v.addLayout(top)

        # Main large button (table name)
        self.btn = QPushButton(code)
        self.btn.setObjectName("tableBtn")
        self.btn.setCheckable(True)
        self.btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.btn.clicked.connect(lambda: on_select(code))
        v.addWidget(self.btn, 1)

        # Reservation text
        self.reserved_label = QLabel("")
        self.reserved_label.setObjectName("reservedLabel")
        self.reserved_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reserved_label.hide()
        v.addWidget(self.reserved_label)

        # Client name label
        self.client_label = QLabel("")
        self.client_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.client_label.setStyleSheet("color:#cfd8dc; font-weight:600; font-size:13px;")
        self.client_label.hide()
        v.addWidget(self.client_label)

        # timer for live update when running
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        # increment and display hh:mm:ss
        self._ps_elapsed += 1
        self._render_timer_label()

    def _render_timer_label(self):
        sec = int(self._ps_elapsed or 0)
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        self.ps_timer.setText(f"🎮 {h:02d}:{m:02d}:{s:02d}")

    def set_state(self, state: str):
        self._state = state
        self._apply_style()

    def set_total(self, cents: int, currency: str = "ج.م"):
        if cents and cents > 0:
            self.badge.setText(format_pounds(cents, currency))
            self.badge.show()
        else:
            self.badge.hide()

    def set_ps_active(self, active: bool, elapsed_seconds: int = 0):
        """Turn PS timer on/off for this tile."""
        if active:
            self._ps_elapsed = int(elapsed_seconds or 0)
            self._render_timer_label()
            self.ps_timer.show()
            if not self._timer.isActive():
                self._timer.start()
        else:
            # stop timer and hide
            if self._timer.isActive():
                self._timer.stop()
            self.ps_timer.hide()

    def set_checked(self, checked: bool):
        self.btn.setChecked(checked)

    def set_reserved(self, reserved_iso: Optional[str]):
        self._reservations = None
        if reserved_iso:
            text = str(reserved_iso)
            try:
                dt = datetime.fromisoformat(text)
            except Exception:
                dt = None
            if dt is not None:
                self._reservations = dt
                text = _format_ampm(dt)
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
        if self._reservations:
            if self._state == 'free':
                color = RESERVED_BORDER
            self.reserved_label.show()
        else:
            self.reserved_label.hide()
        self.btn.setStyleSheet(
            f"background-color:#3b3b3b; color:white; border:2px solid {color}; "
            f"border-radius:10px; padding:16px; font-weight:700;"
        )

    def set_client_name(self, name: str):
        text = (name or "").strip()
        if text:
            self.client_label.setText(text)
            self.client_label.show()
        else:
            self.client_label.hide()
            self.client_label.clear()


class TableMap(QWidget):
    MIN_TILE = QSize(160, 120)

    def __init__(self, table_codes, on_select):
        super().__init__()
        self.tiles = {}
        self._current = None
        self._external_select_cb = on_select
        self._table_codes = []
        self._last_cols = -1
        self._reservations = {}
        self._client_names: dict[str, str] = {}

        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(12, 12, 12, 12)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        # fixed: use AlignTop / AlignRight in PyQt6
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        self.set_table_codes(table_codes, reset_selection=True)

    def _on_click(self, code: str):
        if self._current and self._current != code:
            self.tiles[self._current].set_checked(False)
        self._current = code
        self.tiles[code].set_checked(True)
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
                tile.set_client_name(self._client_names.get(code, ""))
                self.tiles[code] = tile

        self._table_codes = cleaned
        if reset_selection or (self._current and self._current not in cleaned):
            self.clear_selection()
        self._relayout(force=True)

    def update_table(self, code, state: str = None, total_cents: int = None, ps_active: Optional[bool] = None,
                     ps_elapsed_seconds: Optional[int] = None, **kwargs):
        """
        Update table tile with state, total, and PS status.
        """
        t = self.tiles.get(code)
        if not t:
            return
        if state is not None:
            t.set_state(state)
        if total_cents is not None:
            t.set_total(total_cents)

        # Handle PS display
        if ps_active is None:
            if "ps_running" in kwargs:
                ps_active = bool(kwargs.get("ps_running"))
            elif "ps_active" in kwargs:
                ps_active = bool(kwargs.get("ps_active"))

        if ps_elapsed_seconds is None:
            for k in ("ps_elapsed_seconds", "ps_elapsed", "elapsed_seconds", "elapsed"):
                if k in kwargs:
                    try:
                        ps_elapsed_seconds = int(kwargs.get(k) or 0)
                        break
                    except Exception:
                        ps_elapsed_seconds = 0

        if ps_active is not None:
            try:
                t.set_ps_active(bool(ps_active), int(ps_elapsed_seconds or 0))
            except Exception:
                pass

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

    def set_client_name(self, code: str, name: str):
        if not code:
            return
        norm = code.strip().upper()
        value = (name or "").strip()
        if value:
            self._client_names[norm] = value
        else:
            self._client_names.pop(norm, None)
        tile = self.tiles.get(norm)
        if tile:
            tile.set_client_name(value)

    def set_client_names(self, mapping: dict[str, str]):
        self._client_names = {}
        for code, name in (mapping or {}).items():
            if not code:
                continue
            norm = code.strip().upper()
            value = (name or "").strip()
            if norm and value:
                self._client_names[norm] = value
        for code, tile in self.tiles.items():
            tile.set_client_name(self._client_names.get(code, ""))