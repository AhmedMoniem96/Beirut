"""Returns tab for Jewelry app."""

from __future__ import annotations

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...services.db import list_return_invoices
from ...services.i18n import get_ui_language, t


class ReturnsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._language = get_ui_language()
        layout = QVBoxLayout(self)
        header = QLabel()
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        self.header_label = header

        filters = QHBoxLayout()
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        self.refresh_btn = QPushButton()
        self.refresh_btn.clicked.connect(self.refresh)
        self.date_label = QLabel()
        filters.addWidget(self.date_label)
        filters.addWidget(self.date_filter)
        filters.addWidget(self.refresh_btn)
        layout.addLayout(filters)

        self.table = QTableWidget(0, 6)
        layout.addWidget(self.table)

        self.apply_language(self._language)
        self.refresh()

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("returns.header", language=language))
        self.refresh_btn.setText(t("returns.refresh", language=language))
        self.date_label.setText(f"{t('common.date', language=language)}:")
        self.table.setHorizontalHeaderLabels(
            [
                t("returns.table_invoice", language=language),
                t("returns.table_date", language=language),
                t("returns.table_cashier", language=language),
                t("returns.table_total", language=language),
                t("returns.table_method", language=language),
                t("returns.table_reason", language=language),
            ]
        )

    def refresh(self) -> None:
        date_iso = self.date_filter.date().toString("yyyy-MM-dd")
        returns = list_return_invoices(date_iso)
        self.table.setRowCount(0)
        for invoice in returns:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(invoice.invoice_no))
            self.table.setItem(row, 1, QTableWidgetItem(invoice.datetime))
            self.table.setItem(row, 2, QTableWidgetItem(invoice.cashier_name))
            self.table.setItem(row, 3, QTableWidgetItem(f"{invoice.total:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(invoice.payment_method))
            self.table.setItem(row, 5, QTableWidgetItem(invoice.return_reason))
