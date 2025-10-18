from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from ..services.reports import load_end_of_day


class EndOfDayDialog(QDialog):
    """Display the daily summary totals in a simple form."""

    def __init__(self, parent=None, day: date | None = None):
        super().__init__(parent)
        self.setWindowTitle("ملخص نهاية اليوم")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(420, 480)

        summary = load_end_of_day(day)
        summary_dict = summary.as_dict()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        header = QLabel(f"ملخص يوم {summary.day.strftime('%Y-%m-%d')}")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        form = QFormLayout()
        form.setSpacing(8)
        form.addRow("إجمالي المبيعات:", QLabel(summary_dict["total_sales"]))
        form.addRow("المبالغ المرتجعة:", QLabel(summary_dict["refunds"]))
        form.addRow("النقد في الدرج:", QLabel(summary_dict["cash_in_drawer"]))
        form.addRow("إجمالي المشتريات:", QLabel(summary_dict["total_purchases"]))
        layout.addLayout(form)

        methods_label = QLabel("تفاصيل طرق الدفع:")
        methods_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(methods_label)

        method_list = QListWidget()
        for row in summary_dict["by_method"]:
            item = QListWidgetItem(f"{row['method']}: {row['amount']}")
            method_list.addItem(item)
        layout.addWidget(method_list)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("إغلاق")
        buttons.button(QDialogButtonBox.StandardButton.Close).clicked.connect(self.accept)
        layout.addWidget(buttons)
