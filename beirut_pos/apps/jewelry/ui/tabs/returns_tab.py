"""Returns tab for Jewelry app."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from beirut_pos.core.config_store import get_config_value
from ...services.db import (
    create_return_invoice_from_source,
    fetch_source_invoice_items_with_remaining_returnable_qty,
    list_full_invoice_history,
    list_return_invoices,
)
from ...services.i18n import get_ui_language, t
from .base_tab import BaseTabContainer


class ReturnsTab(BaseTabContainer):
    def __init__(self) -> None:
        super().__init__()
        print("LOADED RETURNS TAB FILE:", __file__)
        self._language = get_ui_language()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        filters = QHBoxLayout()
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDisplayFormat("dd/MM/yyyy")
        self.date_filter.setDate(QDate.currentDate())
        self.refresh_btn = QPushButton()
        self.refresh_btn.clicked.connect(self.refresh)
        self.date_label = QLabel()
        filters.addWidget(self.date_label)
        filters.addWidget(self.date_filter)
        filters.addWidget(self.refresh_btn)
        layout.addLayout(filters)

        self.table = QTableWidget(0, 6)
        self.table.setMinimumHeight(140)
        self.table.setMaximumHeight(160)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 140)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 100)
        layout.addWidget(self.table)
        source_row = QHBoxLayout()
        self.source_invoice_edit = QLineEdit()
        self.source_invoice_edit.setPlaceholderText("Source sale invoice no")
        self.source_invoice_edit.returnPressed.connect(self.load_source_invoice)
        self.load_source_btn = QPushButton("Load")
        self.load_source_btn.clicked.connect(self.load_source_invoice)
        source_row.addWidget(self.source_invoice_edit)
        source_row.addWidget(self.load_source_btn)
        layout.addLayout(source_row)

        self.stepper_label = QLabel("1) اختيار الفاتورة → 2) اختيار العناصر المرتجعة → 3) مرتجع نقدي")
        self.stepper_label.setStyleSheet("font-weight: 600; color: #1f2937;")
        layout.addWidget(self.stepper_label)

        self.source_items_table = QTableWidget(0, 6)
        self.source_items_table.setHorizontalHeaderLabels(["Return?", "Item", "Sold", "Returned", "Remaining", "Qty to return"])
        self.source_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.source_items_table.setMinimumHeight(200)
        self.source_items_table.setMaximumHeight(240)
        self.source_items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.source_items_table.horizontalHeader().setStretchLastSection(True)
        self.source_items_table.setColumnWidth(0, 80)
        self.source_items_table.setColumnWidth(1, 300)
        self.source_items_table.setColumnWidth(2, 90)
        self.source_items_table.setColumnWidth(3, 90)
        self.source_items_table.setColumnWidth(4, 90)
        layout.addWidget(self.source_items_table)
        self.source_hint_label = QLabel("Enter a sale invoice number to open it here, then select item(s) to return.")
        self.source_hint_label.setStyleSheet("color: #4b5563;")
        layout.addWidget(self.source_hint_label)

        action_row = QHBoxLayout()
        self.return_method_label = QLabel("Return Method / طريقة المرتجع")
        self.return_method_value = QLabel("Cash Return")
        self.return_method_value.setStyleSheet("font-weight: 600; color: #111827;")
        self.create_return_btn = QPushButton("مرتجع نقدي")
        self.create_return_btn.setMinimumWidth(140)
        self.create_return_btn.clicked.connect(self.create_return_invoice)
        action_row.addWidget(self.return_method_label)
        action_row.addWidget(self.return_method_value)
        action_row.addWidget(self.create_return_btn)
        layout.addLayout(action_row)

        self.summary_label = QLabel("Return Summary / ملخص المرتجع: 0.00")
        self.summary_label.setStyleSheet("font-weight: 600;")
        layout.addWidget(self.summary_label)

        history_filters = QHBoxLayout()
        self.history_from = QDateEdit()
        self.history_to = QDateEdit()
        self.history_from.setCalendarPopup(True)
        self.history_to.setCalendarPopup(True)
        self.history_from.setDate(QDate.currentDate().addMonths(-1))
        self.history_to.setDate(QDate.currentDate())
        self.history_customer = QLineEdit()
        self.history_customer.setPlaceholderText("Customer")
        self.history_status = QLineEdit()
        self.history_status.setPlaceholderText("Status")
        self.history_invoice = QLineEdit()
        self.history_invoice.setPlaceholderText("Invoice #")
        self.history_refresh_btn = QPushButton("Refresh Full History")
        self.history_refresh_btn.clicked.connect(self.load_full_history)
        for w in (self.history_from, self.history_to, self.history_customer, self.history_status, self.history_invoice, self.history_refresh_btn):
            history_filters.addWidget(w)
        layout.addLayout(history_filters)

        self.history_table = QTableWidget(0, 9)
        self.history_table.setHorizontalHeaderLabels(["Invoice", "Date", "Type", "Customer", "Total", "Status", "Link", "Linked Invoices", "Check"])
        self.history_table.setMinimumHeight(150)
        self.history_table.setMaximumHeight(180)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setColumnWidth(0, 150)
        self.history_table.setColumnWidth(1, 145)
        self.history_table.setColumnWidth(2, 80)
        self.history_table.setColumnWidth(3, 120)
        self.history_table.setColumnWidth(4, 85)
        self.history_table.setColumnWidth(5, 90)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.history_table)

        self.set_page_content_widget(content)
        self.apply_language(self._language)
        self.refresh()
        self._source_items = []
        self.load_full_history()

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
            self.table.setItem(row, 5, QTableWidgetItem(self._normalize_return_reason_label(invoice.return_reason)))


    def _normalize_return_reason_label(self, reason: str | None) -> str:
        text = (reason or "").strip()
        if "exchange" in text.lower():
            return text.replace("Exchange", "Return").replace("exchange", "return")
        return text

    def _normalize_txn_type_label(self, txn_type: str | None) -> str:
        text = (txn_type or "").strip()
        if text.lower() == "exchange":
            return "Return"
        return text

    def load_source_invoice(self) -> None:
        invoice_no = self.source_invoice_edit.text().strip()
        if not invoice_no:
            QMessageBox.information(self, "Validation", "Please enter an invoice number.")
            return
        logger = logging.getLogger(__name__)
        logger.debug("Returns load requested for invoice=%s", invoice_no)
        try:
            self._source_items = fetch_source_invoice_items_with_remaining_returnable_qty(invoice_no)
        except Exception as exc:
            logger.exception("Returns load failed for invoice=%s", invoice_no)
            QMessageBox.warning(self, "Load failed", f"Could not load invoice {invoice_no}: {exc}")
            return
        if not self._source_items:
            history = list_full_invoice_history(
                date_from="1900-01-01",
                date_to=QDate.currentDate().toString("yyyy-MM-dd"),
                invoice_no=invoice_no,
            )
            if not history:
                QMessageBox.information(self, "Not found", f"Invoice {invoice_no} was not found.")
            else:
                row = history[0]
                if (row.txn_type or "").strip().lower() != "sale":
                    QMessageBox.information(self, "Validation", f"Invoice {invoice_no} is not a sale invoice.")
                elif (row.payment_status or "").strip().upper() != "PAID":
                    QMessageBox.information(self, "Validation", f"Invoice {invoice_no} is not PAID yet.")
                else:
                    QMessageBox.information(
                        self,
                        "No returnable items",
                        f"Invoice {invoice_no} has no returnable quantity (already returned or no items).",
                    )
            logger.debug("Returns load produced no returnable items for invoice=%s", invoice_no)
        self.source_items_table.setRowCount(0)
        for item in self._source_items:
            row = self.source_items_table.rowCount()
            self.source_items_table.insertRow(row)
            check_item = QTableWidgetItem()
            check_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable |
                Qt.ItemFlag.ItemIsEnabled
            )
            check_item.setCheckState(Qt.CheckState.Unchecked)
            self.source_items_table.setItem(row, 0, check_item)
            self.source_items_table.setItem(row, 1, QTableWidgetItem(f"{item.product_name} ({item.product_code})"))
            self.source_items_table.setItem(row, 2, QTableWidgetItem(f"{item.sold_qty:.2f}"))
            self.source_items_table.setItem(row, 3, QTableWidgetItem(f"{item.returned_qty:.2f}"))
            self.source_items_table.setItem(row, 4, QTableWidgetItem(f"{item.remaining_qty:.2f}"))
            qty_spin = QDoubleSpinBox()
            qty_spin.setDecimals(3)
            qty_spin.setRange(0.0, item.remaining_qty)
            qty_spin.setValue(0.0)
            self.source_items_table.setCellWidget(row, 5, qty_spin)

    def create_return_invoice(self) -> None:
        lines = []
        for idx, item in enumerate(self._source_items):
            check_item = self.source_items_table.item(idx, 0)
            if not check_item or check_item.checkState() != Qt.CheckState.Checked:
                continue
            qty_widget = self.source_items_table.cellWidget(idx, 5)
            qty = float(qty_widget.value()) if isinstance(qty_widget, QDoubleSpinBox) else 0.0
            if qty <= 0 or qty > item.remaining_qty:
                QMessageBox.warning(self, "Validation", "Invalid return quantity selected.")
                return
            lines.append({"source_invoice_item_id": item.invoice_item_id, "qty": qty})
        if not lines:
            QMessageBox.warning(self, "Validation", "Select at least one line with quantity.")
            return
        return_total = self._compute_return_total(lines)
        ref = f"RET-{QDate.currentDate().toString('yyyyMMdd')}-{self.source_invoice_edit.text().strip()}"
        reason = "Return"
        summary_msg = f"Return Summary\nTotal return amount: {return_total:.2f}\nReference: {ref}"
        self._update_summary_label(return_total)
        QMessageBox.information(self, "Summary", summary_msg)
        try:
            invoice_no, _ = create_return_invoice_from_source(
                source_invoice_no=self.source_invoice_edit.text().strip(),
                cashier_name="Returns Tab",
                return_reason=f"{reason} | Ref: {ref}",
                selected_lines=lines,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Success", f"Return invoice created: {invoice_no}")
        QMessageBox.information(
            self,
            "Linked",
            f"Return invoice {invoice_no} is linked to source invoice {self.source_invoice_edit.text().strip()}",
        )
        self.load_source_invoice()
        self.refresh()
        self.load_full_history()

    def _compute_return_total(self, lines: list[dict]) -> float:
        pricing_basis = str(get_config_value("jw_return_pricing_basis", "original_sold_price") or "original_sold_price").strip().lower()
        if pricing_basis == "current_catalog_price":
            mapping = {}
            for item in self._source_items:
                mapping[item.invoice_item_id] = float(self._lookup_current_product_price(item.product_id))
        else:
            mapping = {item.invoice_item_id: float(item.unit_price) for item in self._source_items}
        return sum(float(line["qty"]) * mapping.get(line["source_invoice_item_id"], 0.0) for line in lines)

    def _lookup_current_product_price(self, product_id: int) -> float:
        for product in getattr(self, "_products", []):
            if int(getattr(product, "id", 0)) == int(product_id):
                return float(getattr(product, "price", 0.0) or 0.0)
        return 0.0

    def _update_summary_label(self, return_total: float = 0.0) -> None:
        self.summary_label.setText(f"Return Summary / ملخص المرتجع: {return_total:.2f}")

    def load_full_history(self) -> None:
        rows = list_full_invoice_history(
            date_from=self.history_from.date().toString("yyyy-MM-dd"),
            date_to=self.history_to.date().toString("yyyy-MM-dd"),
            customer=self.history_customer.text(),
            status=self.history_status.text(),
            invoice_no=self.history_invoice.text(),
        )
        self.history_table.setRowCount(0)
        for data in rows:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            values = [
                data.invoice_no,
                data.datetime,
                self._normalize_txn_type_label(data.txn_type),
                data.customer_name,
                f"{data.total:.2f}",
                data.payment_status,
                "🟢 Linked" if data.link_state == "linked" else "⚪ Unlinked",
                data.linked_invoice_nos or "-",
                "✅ OK" if data.consistency_ok else "❌ Inconsistent",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col == 6:
                    item.setBackground(QColor("#d1fae5" if data.link_state == "linked" else "#f3f4f6"))
                if col == 8 and not data.consistency_ok:
                    item.setBackground(QColor("#fee2e2"))
                self.history_table.setItem(row, col, item)

