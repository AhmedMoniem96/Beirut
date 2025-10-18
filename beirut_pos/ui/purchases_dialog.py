# beirut_pos/ui/purchases_dialog.py
from __future__ import annotations

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateTimeEdit,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .common.big_dialog import BigDialog
from ..services import purchases
from ..utils.currency import format_pounds


class PurchasesDialog(BigDialog):
    def __init__(self, actor: str, parent=None):
        super().__init__("المشتريات", remember_key="purchases", parent=parent)
        self._actor = actor

        root = QVBoxLayout(self)

        intro = QLabel(
            "سجّل كل مشتريات المخزون هنا لتبقى حساباتك دقيقة وتتبع المصروفات بسهولة."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.table = QTableWidget(0, 6)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignRight)
        self.table.verticalHeader().setVisible(False)
        self.table.setHorizontalHeaderLabels(
            [
                "التاريخ",
                "المورد",
                "رقم الفاتورة",
                "المبلغ",
                "ملاحظات",
                "أضيف بواسطة",
            ]
        )
        root.addWidget(self.table, 1)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.when = QDateTimeEdit(QDateTime.currentDateTime())
        self.when.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.when.setCalendarPopup(True)
        form.addRow("تاريخ الشراء:", self.when)

        self.supplier = QLineEdit()
        self.supplier.setPlaceholderText("اسم المورد أو الجهة")
        form.addRow("المورد:", self.supplier)

        self.invoice = QLineEdit()
        self.invoice.setPlaceholderText("رقم الفاتورة أو المرجع (اختياري)")
        form.addRow("رقم الفاتورة:", self.invoice)

        self.amount = QSpinBox()
        self.amount.setRange(0, 50_000_000)
        self.amount.setSuffix(" ج.م")
        self.amount.setSingleStep(10)
        form.addRow("المبلغ بالجنيه:", self.amount)

        self.notes = QTextEdit()
        self.notes.setPlaceholderText("ملاحظات حول الشراء، البنود أو طريقة الدفع…")
        self.notes.setMaximumHeight(90)
        form.addRow("ملاحظات:", self.notes)

        root.addWidget(form_host, 0)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_refresh = QPushButton("تحديث السجل")
        self.btn_refresh.clicked.connect(self._refresh)
        buttons.addWidget(self.btn_refresh)
        self.btn_save = QPushButton("حفظ الشراء")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save.setDefault(True)
        buttons.addWidget(self.btn_save)
        root.addLayout(buttons)

        self._refresh()

    def _refresh(self) -> None:
        try:
            records = purchases.list_purchases()
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "خطأ", f"تعذر تحميل المشتريات: {exc}")
            return

        self.table.setRowCount(0)
        for record in records:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_row_values(row, record)

    def _on_save(self) -> None:
        supplier = self.supplier.text().strip()
        if not supplier:
            QMessageBox.warning(self, "معلومات ناقصة", "يرجى إدخال اسم المورد أولاً.")
            return

        amount_pounds = self.amount.value()
        if amount_pounds <= 0:
            QMessageBox.warning(self, "مبلغ غير صالح", "أدخل مبلغاً أكبر من صفر بالجنيه.")
            return

        when_dt = self.when.dateTime().toPyDateTime()
        invoice = self.invoice.text().strip()
        notes = self.notes.toPlainText().strip()

        try:
            record = purchases.create_purchase(
                supplier=supplier,
                amount_cents=amount_pounds * 100,
                invoice_no=invoice,
                notes=notes,
                recorded_by=self._actor,
                purchased_at=when_dt,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "مدخلات غير صحيحة", str(exc))
            return
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "خطأ", f"تعذر حفظ الشراء: {exc}")
            return

        self.table.insertRow(0)
        self._set_row_values(0, record)
        self._clear_form()
        QMessageBox.information(self, "تم الحفظ", "تم تسجيل عملية الشراء بنجاح.")

    def _set_row_values(self, row: int, record: purchases.PurchaseRecord) -> None:
        values = (
            record.purchased_at.strftime("%Y-%m-%d %H:%M"),
            record.supplier,
            record.invoice_no,
            format_pounds(record.amount_cents),
            record.display_notes,
            record.recorded_by or "",
        )
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            if col == 3:
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, col, item)

    def _clear_form(self) -> None:
        self.when.setDateTime(QDateTime.currentDateTime())
        self.supplier.clear()
        self.invoice.clear()
        self.amount.setValue(0)
        self.notes.clear()
        self.supplier.setFocus()

