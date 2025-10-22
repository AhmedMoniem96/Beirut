from __future__ import annotations

from datetime import datetime, timezone
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QLabel,
    QMessageBox,
)

# Use the shared texts registry if available (keeps labels dynamic)
try:
    from ..services import texts
except Exception:
    texts = None


ALLOW_LATE_EDIT_OVERRIDE = os.getenv("ALLOW_ADMIN_EDIT_AFTER_WINDOW", "0") == "1"


class OrderItemEditor(QDialog):
    """Allow adjusting quantity and note for an existing order item.

    Parameters
    ----------
    product: str
        Product label (display only).
    qty: float
        Current quantity.
    note: str
        Current note.
    editable_until: datetime | str | None
        If provided, determines whether editing is allowed. Accepts an ISO string
        or a datetime. If None, editing is allowed.
    is_admin: bool
        If True and ALLOW_ADMIN_EDIT_AFTER_WINDOW env var is set, admin can edit after the window.
    """

    def __init__(self, product: str, qty: float, note: str, editable_until=None, is_admin: bool = False, parent=None):
        super().__init__(parent)
        # title uses dynamic text if available
        title = f"تعديل عنصر — {product}"
        if texts:
            title = texts.get("order_item_editor.title", title)
        self.setWindowTitle(title)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self._values: dict | None = None

        # parse editable_until
        self._editable_until: datetime | None = None
        if editable_until is not None:
            if isinstance(editable_until, datetime):
                self._editable_until = editable_until
            else:
                try:
                    self._editable_until = datetime.fromisoformat(str(editable_until))
                except Exception:
                    self._editable_until = None

        self._is_admin = bool(is_admin)
        self._allow_admin_override = ALLOW_LATE_EDIT_OVERRIDE and self._is_admin

        form = QFormLayout(self)

        # Quantity field
        self.qty_field = QDoubleSpinBox()
        self.qty_field.setRange(0, 10_000)
        self.qty_field.setDecimals(2)
        self.qty_field.setSingleStep(0.5)
        self.qty_field.setValue(float(qty))

        # Note field
        self.note_field = QLineEdit(note or "")
        self.note_field.setMaxLength(120)

        # Info / countdown label
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setObjectName("editWindowInfo")
        self.info_label.setMinimumWidth(200)

        # add rows
        qty_label = texts.get("order_item_editor.qty_label", "الكمية:") if texts else "الكمية:"
        note_label = texts.get("order_item_editor.note_label", "ملاحظة:") if texts else "ملاحظة:"
        form.addRow(qty_label, self.qty_field)
        form.addRow(note_label, self.note_field)
        form.addRow(self.info_label)

        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_btn = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.cancel_btn = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        form.addRow(self.buttons)

        # Timer to update countdown
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        # Initialize state
        self._update_ui_state()
        if self._editable_until and not self._is_locked():
            self._timer.start()

    def _now_utc(self) -> datetime:
        # keep consistent with existing code that uses naive UTC; use tz-aware here
        return datetime.now(timezone.utc).replace(tzinfo=None) if datetime.now(timezone.utc).tzinfo else datetime.utcnow()

    def _is_locked(self) -> bool:
        """Return True if editing is not allowed now (and admin override not active)."""
        if self._editable_until is None:
            return False
        # admin override from env + flag
        if self._allow_admin_override:
            return False
        try:
            # compare naive datetimes consistently: if editable_until has tzinfo, convert to naive UTC
            eu = self._editable_until
            if getattr(eu, "tzinfo", None) is not None:
                eu = eu.astimezone(timezone.utc).replace(tzinfo=None)
            now = datetime.utcnow()
            return now > eu
        except Exception:
            # if parse failed, be conservative and allow editing
            return False

    def _format_timedelta(self, seconds: int) -> str:
        seconds = max(0, int(seconds))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h:
            return f"{h:02d}:{m:02d}:{s:02d}"
        return f"{m:02d}:{s:02d}"

    def _on_tick(self):
        # timer tick updates countdown; stop when window expires
        if self._editable_until is None:
            self._timer.stop()
            return
        try:
            eu = self._editable_until
            if getattr(eu, "tzinfo", None) is not None:
                eu = eu.astimezone(timezone.utc).replace(tzinfo=None)
            now = datetime.utcnow()
            remaining = int((eu - now).total_seconds())
            if remaining <= 0:
                # expired
                self._timer.stop()
                self._update_ui_state()
            else:
                label = texts.get(
                    "order_item_editor.remaining",
                    "بقي وقت التعديل: {time}",
                ).format(time=self._format_timedelta(remaining)) if texts else f"بقي وقت التعديل: {self._format_timedelta(remaining)}"
                self.info_label.setText(label)
        except Exception:
            self._timer.stop()
            self._update_ui_state()

    def _update_ui_state(self):
        """Enable/disable OK and show message depending on editable window."""
        locked = self._is_locked()
        if locked:
            # locked - disable OK
            if texts:
                title = texts.get("orders.edit_locked", "انتهت مدة التعديل")
                msg = texts.get("order_item_editor.locked_msg", "انتهت مدة التعديل على هذا الطلب ولا يمكن تغييره.")
            else:
                title = "انتهت مهلة التعديل"
                msg = "انتهت مدة التعديل على هذا الطلب ولا يمكن تغييره."

            self.info_label.setText(f"<b>{title}</b><br/>{msg}")
            self.ok_btn.setEnabled(False)
            self.ok_btn.setToolTip(title)
        else:
            # editable
            self.ok_btn.setEnabled(True)
            self.ok_btn.setToolTip("")
            if self._editable_until:
                # start/refresh countdown text
                try:
                    eu = self._editable_until
                    if getattr(eu, "tzinfo", None) is not None:
                        eu = eu.astimezone(timezone.utc).replace(tzinfo=None)
                    now = datetime.utcnow()
                    remaining = int((eu - now).total_seconds())
                    label = texts.get(
                        "order_item_editor.remaining",
                        "بقي وقت التعديل: {time}",
                    ).format(time=self._format_timedelta(remaining)) if texts else f"بقي وقت التعديل: {self._format_timedelta(remaining)}"
                    self.info_label.setText(label)
                except Exception:
                    self.info_label.clear()
            else:
                self.info_label.clear()

    def accept(self) -> None:
        # Re-check lock on accept (race conditions)
        if self._is_locked():
            QMessageBox.warning(
                self,
                texts.get("orders.edit_locked_title", "انتهت مدة التعديل") if texts else "انتهت مدة التعديل",
                texts.get("orders.edit_locked", "انتهت مدة التعديل") if texts else "انتهت مدة التعديل",
            )
            return
        qty = float(self.qty_field.value())
        note = self.note_field.text().strip()
        self._values = {"qty": qty, "note": note}
        super().accept()

    def get_values(self) -> dict | None:
        return self._values
