"""Simple UI to manage table reservations."""

from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt, QTimer
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
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from ..services import reservations as reservations_service
from .common.big_dialog import BigDialog
from .common.async_utils import build_busy_placeholder, emit_task_status


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
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
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

        self.loading_state = build_busy_placeholder("يتم تحميل الحجوزات…")
        self._table_stack = QStackedLayout()
        self._table_stack.setContentsMargins(0, 0, 0, 0)
        self._table_stack.setSpacing(0)
        self._table_stack.addWidget(self.table)
        self._table_stack.addWidget(self.loading_state)

        table_host = QWidget()
        table_layout = QVBoxLayout(table_host)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.addLayout(self._table_stack)
        layout.addWidget(table_host, 1)

        self._reservations_cache: list[dict] = []
        self._load_reservations()

    # ------------------------------------------------------------------ helpers
    def _set_loading(self, loading: bool) -> None:
        self._table_stack.setCurrentWidget(self.loading_state if loading else self.table)

    def _load_reservations(self, *, silent: bool = False):
        self._set_loading(True)
        if not silent:
            emit_task_status("يتم تحديث الحجوزات…", "info")
        QTimer.singleShot(0, lambda: self._populate_reservations(silent=silent))

    def _populate_reservations(self, *, silent: bool = False):
        try:
            rows = reservations_service.list_reservations()
        except Exception as exc:  # pragma: no cover - UI feedback
            self._set_loading(False)
            if not silent:
                emit_task_status("تعذر تحديث الحجوزات.", "error")
            QMessageBox.critical(self, "خطأ", f"تعذر تحميل الحجوزات: {exc}")
            return

        self._reservations_cache = rows
        self._render_reservations()
        self._set_loading(False)
        if not silent:
            emit_task_status("تم تحديث الحجوزات.", "success")

    def _render_reservations(self, *, select_id: int | None = None):
        self.table.setRowCount(len(self._reservations_cache))
        selected_row = 0
        for idx, row in enumerate(self._reservations_cache):
            self._set_row(idx, row)
            if select_id is not None and row.get("id") == select_id:
                selected_row = idx
        if self._reservations_cache:
            self.table.setCurrentCell(selected_row, 0)

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
        if row < 0 or row >= len(self._reservations_cache):
            return None
        return self._reservations_cache[row]

    def _create_reservation(self):
        dialog = _ReservationEditor(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        values = dialog.values
        if not values:
            return
        optimistic_row = {**values, "id": -1, "status": values.get("status", "pending")}
        self._reservations_cache.insert(0, optimistic_row)
        self._render_reservations(select_id=-1)
        emit_task_status("يتم إنشاء الحجز…", "info")
        try:
            new_id = reservations_service.create_reservation(**values)
        except Exception as exc:  # pragma: no cover - UI feedback
            if self._reservations_cache and self._reservations_cache[0].get("id") == -1:
                self._reservations_cache.pop(0)
                self._render_reservations()
            emit_task_status("تعذر إنشاء الحجز.", "error")
            QMessageBox.critical(self, "خطأ", f"تعذر إنشاء الحجز: {exc}")
            return

        optimistic_row["id"] = new_id
        self._reservations_cache[0] = optimistic_row
        self._render_reservations(select_id=new_id)
        emit_task_status("تم حفظ الحجز الجديد.", "success")

    def _update_status(self, status: str):
        res_id = self._current_reservation_id()
        if res_id is None:
            QMessageBox.information(self, "الحجوزات", "اختر حجزاً أولاً.")
            return
        row = self.table.currentRow()
        if row < 0 or row >= len(self._reservations_cache):
            QMessageBox.information(self, "الحجوزات", "اختر حجزاً أولاً.")
            return

        current = self._reservations_cache[row]
        if current.get("status") == status:
            return

        optimistic = {**current, "status": status}
        self._reservations_cache[row] = optimistic
        self._set_row(row, optimistic)
        emit_task_status("يتم تحديث حالة الحجز…", "info")

        try:
            reservations_service.update_status(res_id, status)
        except Exception as exc:  # pragma: no cover - UI feedback
            self._reservations_cache[row] = current
            self._set_row(row, current)
            emit_task_status("فشل تحديث حالة الحجز.", "error")
            QMessageBox.warning(self, "الحجوزات", f"تعذر تحديث حالة الحجز: {exc}")
            return

        emit_task_status("تم تحديث حالة الحجز.", "success")

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
        row = self.table.currentRow()
        removed = self._reservations_cache.pop(row) if 0 <= row < len(self._reservations_cache) else None
        if removed is not None:
            self.table.removeRow(row)
        emit_task_status("يتم حذف الحجز…", "info")
        try:
            reservations_service.delete_reservation(res_id)
        except Exception as exc:  # pragma: no cover - UI feedback
            if removed is not None:
                self._reservations_cache.insert(row, removed)
                self._render_reservations(select_id=removed.get("id"))
            emit_task_status("تعذر حذف الحجز.", "error")
            QMessageBox.critical(self, "خطأ", f"تعذر حذف الحجز: {exc}")
            return

        if not self._reservations_cache:
            self._load_reservations(silent=True)
        emit_task_status("تم حذف الحجز.", "success")


class _ReservationEditor(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إضافة حجز")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.values: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSpacing(12)
        layout.addLayout(form)

        def _configure_field(widget) -> None:
            widget.setMinimumWidth(240)
            if hasattr(widget, "setMinimumHeight"):
                widget.setMinimumHeight(34)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if isinstance(widget, (QLineEdit, QDateTimeEdit, QSpinBox)):
                widget.setStyleSheet("padding: 6px 10px;")

        self.name = QLineEdit()
        _configure_field(self.name)
        form.addRow("الاسم:", self.name)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("مثال: 01001234567")
        _configure_field(self.phone)
        form.addRow("الهاتف:", self.phone)

        self.party_size = QSpinBox()
        self.party_size.setRange(1, 30)
        _configure_field(self.party_size)
        form.addRow("عدد الأشخاص:", self.party_size)

        self.when = QDateTimeEdit(datetime.now())
        self.when.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.when.setCalendarPopup(True)
        _configure_field(self.when)
        form.addRow("التاريخ والوقت:", self.when)

        self.table_code = QLineEdit()
        _configure_field(self.table_code)
        form.addRow("الطاولة المخصصة:", self.table_code)

        self.notes = QLineEdit()
        self.notes.setPlaceholderText("ملاحظات إضافية")
        _configure_field(self.notes)
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

