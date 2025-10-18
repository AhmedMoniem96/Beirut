"""Simple UI to manage table reservations."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import reservations as reservations_service
from .common.big_dialog import BigDialog


_STATUS_DISPLAY = {
    "pending": "قيد الانتظار",
    "seated": "حضر",
    "cancelled": "أُلغي",
}


class ReservationsDialog(BigDialog):
    def __init__(self, parent=None):
        super().__init__("الحجوزات", remember_key="reservations", parent=parent)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "الاسم",
                "الهاتف",
                "عدد الأشخاص",
                "وقت الحجز",
                "الطاولة",
                "الحالة",
                "ملاحظات",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)

        btn_new = QPushButton("إضافة حجز")
        btn_new.clicked.connect(self._create_reservation)

        btn_seated = QPushButton("تأكيد الحضور")
        btn_seated.clicked.connect(lambda: self._update_status("seated"))

        btn_cancel = QPushButton("إلغاء الحجز")
        btn_cancel.clicked.connect(lambda: self._update_status("cancelled"))

        btn_delete = QPushButton("حذف")
        btn_delete.clicked.connect(self._delete_reservation)

        btn_refresh = QPushButton("تحديث")
        btn_refresh.clicked.connect(self._load_reservations)

        controls = QHBoxLayout()
        controls.addWidget(btn_new)
        controls.addWidget(btn_seated)
        controls.addWidget(btn_cancel)
        controls.addWidget(btn_delete)
        controls.addStretch(1)
        controls.addWidget(btn_refresh)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.table, 1)

        self._load_reservations()

    # ------------------------------------------------------------------ helpers
    def _load_reservations(self):
        rows = reservations_service.list_reservations()
        self.table.setRowCount(len(rows))
        for idx, row in enumerate(rows):
            self._set_row(idx, row)

    def _set_row(self, row_idx: int, data: dict):
        mapping = [
            data.get("name", ""),
            data.get("phone", ""),
            str(data.get("party_size", "")),
            _format_datetime(data.get("reserved_for")),
            data.get("table_code", ""),
            _STATUS_DISPLAY.get(data.get("status", "pending"), data.get("status", "")),
            data.get("notes", ""),
        ]
        for col, value in enumerate(mapping):
            item = QTableWidgetItem(value)
            item.setData(Qt.ItemDataRole.UserRole, data.get("id"))
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row_idx, col, item)

    def _current_reservation_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if not item:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return None if data is None else int(data)

    def _selected_row_data(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        res_id = self._current_reservation_id()
        if res_id is None:
            return None
        rows = reservations_service.list_reservations()
        for data in rows:
            if data.get("id") == res_id:
                return data
        return None

    def _create_reservation(self):
        dialog = _ReservationEditor(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        values = dialog.values
        if not values:
            return
        reservations_service.create_reservation(**values)
        self._load_reservations()

    def _update_status(self, status: str):
        res_id = self._current_reservation_id()
        if res_id is None:
            QMessageBox.information(self, "الحجوزات", "اختر حجزاً أولاً.")
            return
        reservations_service.update_status(res_id, status)
        self._load_reservations()

    def _delete_reservation(self):
        res_id = self._current_reservation_id()
        if res_id is None:
            QMessageBox.information(self, "الحجوزات", "اختر حجزاً لحذفه.")
            return
        confirm = QMessageBox.question(
            self,
            "تأكيد الحذف",
            "سيتم حذف الحجز نهائياً. هل أنت متأكد؟",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        reservations_service.delete_reservation(res_id)
        self._load_reservations()


class _ReservationEditor(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إضافة حجز")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.values: dict | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.name = QLineEdit()
        form.addRow("الاسم:", self.name)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("مثال: 01001234567")
        form.addRow("الهاتف:", self.phone)

        self.party_size = QSpinBox()
        self.party_size.setRange(1, 30)
        form.addRow("عدد الأشخاص:", self.party_size)

        self.when = QDateTimeEdit(datetime.now())
        self.when.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.when.setCalendarPopup(True)
        form.addRow("التاريخ والوقت:", self.when)

        self.table_code = QLineEdit()
        form.addRow("الطاولة المخصصة:", self.table_code)

        self.notes = QLineEdit()
        self.notes.setPlaceholderText("ملاحظات إضافية")
        form.addRow("ملاحظات:", self.notes)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self) -> None:
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "خطأ", "يجب إدخال اسم صاحب الحجز.")
            return
        self.values = {
            "name": name,
            "phone": self.phone.text().strip(),
            "party_size": int(self.party_size.value()),
            "reserved_for": self.when.dateTime().toString(Qt.DateFormat.ISODate),
            "table_code": self.table_code.text().strip().upper(),
            "notes": self.notes.text().strip(),
        }
        super().accept()


def _format_datetime(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value

