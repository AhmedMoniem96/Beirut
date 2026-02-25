from __future__ import annotations

import sys
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from beirut_pos.core.bus import bus
from beirut_pos.core.db import setting_get, setting_set

from .common.async_utils import Debouncer
from ..services.printer import printer


def _list_printers() -> list[str]:
    if not sys.platform.startswith("win"):
        return []
    try:
        import win32print

        return [
            p[2]
            for p in win32print.EnumPrinters(
                win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
            )
        ]
    except Exception:
        return []


class PrinterQuickDialog(QDialog):
    """Focused printer quick settings with auto-save feedback."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("إعدادات الطابعات السريعة")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.bar_prn = QComboBox()
        self.bar_prn.setEditable(True)
        self.cash_prn = QComboBox()
        self.cash_prn.setEditable(True)

        self._reload_printer_names()
        self.bar_prn.setCurrentText(setting_get("bar_printer", ""))
        self.cash_prn.setCurrentText(setting_get("cashier_printer", ""))

        form.addRow("طابعة البار:", self.bar_prn)
        form.addRow("طابعة الكاشير:", self.cash_prn)
        layout.addLayout(form)

        self.saved_status = QLabel("جاهز")
        self.saved_status.setStyleSheet("color: #5f6c7b;")
        layout.addWidget(self.saved_status)

        controls = QHBoxLayout()
        self.btn_refresh = QPushButton("تحديث الطابعات")
        self.btn_refresh.clicked.connect(self._on_refresh_printers)
        controls.addWidget(self.btn_refresh)

        self.btn_test = QPushButton("اختبار الطباعة")
        self.btn_test.clicked.connect(self._on_test_print)
        controls.addWidget(self.btn_test)

        controls.addStretch(1)

        self.btn_save = QPushButton("حفظ الآن")
        self.btn_save.clicked.connect(self._save_now)
        controls.addWidget(self.btn_save)

        self.btn_close = QPushButton("إغلاق")
        self.btn_close.clicked.connect(self.accept)
        controls.addWidget(self.btn_close)

        layout.addLayout(controls)

        self._save_debouncer = Debouncer(self._save_now, delay_ms=350, parent=self)
        self.bar_prn.currentTextChanged.connect(self._on_changed)
        self.cash_prn.currentTextChanged.connect(self._on_changed)

        bar_edit = self.bar_prn.lineEdit()
        if bar_edit:
            bar_edit.editingFinished.connect(self._save_now)
        cash_edit = self.cash_prn.lineEdit()
        if cash_edit:
            cash_edit.editingFinished.connect(self._save_now)

    def _reload_printer_names(self) -> None:
        names = _list_printers()
        bar_current = self.bar_prn.currentText().strip() if hasattr(self, "bar_prn") else ""
        cash_current = self.cash_prn.currentText().strip() if hasattr(self, "cash_prn") else ""

        self.bar_prn.blockSignals(True)
        self.cash_prn.blockSignals(True)
        self.bar_prn.clear()
        self.cash_prn.clear()
        self.bar_prn.addItems(names)
        self.cash_prn.addItems(names)
        self.bar_prn.setCurrentText(bar_current)
        self.cash_prn.setCurrentText(cash_current)
        self.bar_prn.blockSignals(False)
        self.cash_prn.blockSignals(False)

    def _on_refresh_printers(self) -> None:
        self._reload_printer_names()
        self.saved_status.setText("تم تحديث قائمة الطابعات")
        self.saved_status.setStyleSheet("color: #3e6b9a;")

    def _on_test_print(self) -> None:
        ok = printer.test_print()
        if ok:
            self.saved_status.setText("نجح اختبار الطباعة")
            self.saved_status.setStyleSheet("color: #1f7a1f;")
        else:
            QMessageBox.warning(self, "اختبار الطابعة", "تعذر إرسال اختبار الطباعة.")
            self.saved_status.setText("فشل اختبار الطباعة")
            self.saved_status.setStyleSheet("color: #b22a2a;")

    def _on_changed(self, _value: str) -> None:
        self.saved_status.setText("...جارٍ الحفظ")
        self.saved_status.setStyleSheet("color: #8a6d3b;")
        self._save_debouncer.trigger()

    def _save_now(self) -> None:
        bar = self.bar_prn.currentText().strip()
        cash = self.cash_prn.currentText().strip()
        setting_set("bar_printer", bar)
        setting_set("cashier_printer", cash)
        bus.emit("printers_changed", bar, cash)
        stamp = datetime.now().strftime("%I:%M:%S %p")
        self.saved_status.setText(f"تم الحفظ تلقائياً ({stamp})")
        self.saved_status.setStyleSheet("color: #1f7a1f;")
