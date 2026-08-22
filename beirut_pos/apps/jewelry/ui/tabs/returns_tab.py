"""Returns tab for Jewelry app."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
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
    fetch_return_source_invoice,
    fetch_source_invoice_items_with_remaining_returnable_qty,
    list_full_invoice_history,
    list_return_invoices,
)
from ...services.i18n import get_ui_language, t
from .base_tab import BaseTabContainer


class ReturnsTab(BaseTabContainer):
    inventory_changed = pyqtSignal()
    RETURN_METHODS = ("Cash Return", "Exchange", "Credit / Customer Balance")
    RETURN_REASONS = ("Return", "Defective item", "Wrong item", "Customer request")

    def __init__(self) -> None:
        super().__init__()
        self._language = get_ui_language()
        self._source_items = []

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        lookup_group = QGroupBox("1 — Invoice Lookup")
        lookup_layout = QVBoxLayout(lookup_group)
        lookup_layout.setSpacing(8)
        source_row = QHBoxLayout()
        source_row.setSpacing(8)
        self.source_invoice_edit = QLineEdit()
        self.source_invoice_edit.setPlaceholderText("Invoice Number")
        self.source_invoice_edit.setClearButtonEnabled(True)
        self.source_invoice_edit.returnPressed.connect(self.load_source_invoice)
        self.load_source_btn = QPushButton("Load")
        self.load_source_btn.setMinimumWidth(100)
        self.load_source_btn.clicked.connect(self.load_source_invoice)
        source_row.addWidget(self.source_invoice_edit, 1)
        source_row.addWidget(self.load_source_btn)
        lookup_layout.addLayout(source_row)

        self.invoice_info = QFrame()
        self.invoice_info.setObjectName("invoiceInfo")
        self.invoice_info.setStyleSheet(
            "QFrame#invoiceInfo { background: #f8fafc; border: 1px solid #e2e8f0; "
            "border-radius: 6px; } QLabel { border: none; }"
        )
        info_layout = QGridLayout(self.invoice_info)
        info_layout.setContentsMargins(12, 8, 12, 8)
        info_layout.setHorizontalSpacing(20)
        self.invoice_info_values = {}
        for index, (key, title) in enumerate((
            ("invoice_no", "Invoice Number"), ("customer", "Customer"),
            ("date", "Date"), ("payment_method", "Payment Method"), ("total", "Total"),
        )):
            column = (index % 3) * 2
            row = index // 3
            title_label = QLabel(f"{title}:")
            title_label.setStyleSheet("font-weight: 600; color: #475569;")
            value_label = QLabel("—")
            value_label.setStyleSheet("font-weight: 600; color: #0f172a;")
            info_layout.addWidget(title_label, row, column)
            info_layout.addWidget(value_label, row, column + 1)
            self.invoice_info_values[key] = value_label
        self.invoice_info.hide()
        lookup_layout.addWidget(self.invoice_info)
        layout.addWidget(lookup_group)

        items_group = QGroupBox("2 — Return Items")
        items_layout = QVBoxLayout(items_group)
        items_layout.setContentsMargins(8, 10, 8, 8)
        self.source_items_table = QTableWidget(0, 6)
        self.source_items_table.setHorizontalHeaderLabels(
            ["Return ✓", "Item", "Sold Qty", "Previously Returned", "Remaining", "Return Qty"]
        )
        self.source_items_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.source_items_table.setAlternatingRowColors(True)
        self.source_items_table.setMinimumHeight(190)
        self.source_items_table.verticalHeader().setVisible(False)
        header = self.source_items_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.source_items_table.itemChanged.connect(self._selection_changed)
        items_layout.addWidget(self.source_items_table)
        self.source_hint_label = QLabel("Load a paid sale invoice to select items for return.")
        self.source_hint_label.setStyleSheet("color: #64748b;")
        items_layout.addWidget(self.source_hint_label)
        layout.addWidget(items_group)

        options_group = QGroupBox("3 — Return Options")
        options_layout = QHBoxLayout(options_group)
        options_layout.setSpacing(24)
        controls = QFormLayout()
        controls.setHorizontalSpacing(12)
        self.return_method_combo = QComboBox()
        self.return_method_combo.addItems(self.RETURN_METHODS)
        self.return_method_combo.currentTextChanged.connect(self._selection_changed)
        self.return_reason_combo = QComboBox()
        self.return_reason_combo.addItems(self.RETURN_REASONS)
        controls.addRow("Return Method", self.return_method_combo)
        controls.addRow("Return Reason", self.return_reason_combo)
        options_layout.addLayout(controls, 1)

        summary = QFrame()
        summary.setObjectName("returnSummary")
        summary.setStyleSheet(
            "QFrame#returnSummary { background: #eff6ff; border: 1px solid #bfdbfe; "
            "border-radius: 6px; } QLabel { border: none; }"
        )
        summary_layout = QGridLayout(summary)
        summary_title = QLabel("Return Summary")
        summary_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e3a8a;")
        summary_layout.addWidget(summary_title, 0, 0, 1, 2)
        self.items_selected_value = QLabel("0")
        self.return_total_value = QLabel("0.00")
        self.summary_method_value = QLabel(self.return_method_combo.currentText())
        for row, (title, value) in enumerate((
            ("Items Selected", self.items_selected_value),
            ("Total Return Amount", self.return_total_value),
            ("Return Method", self.summary_method_value),
        ), start=1):
            summary_layout.addWidget(QLabel(title), row, 0)
            value.setStyleSheet("font-weight: 700; color: #0f172a;")
            summary_layout.addWidget(value, row, 1, alignment=Qt.AlignmentFlag.AlignRight)
        options_layout.addWidget(summary, 1)
        layout.addWidget(options_group)

        self.create_return_btn = QPushButton("Execute Return")
        self.create_return_btn.setMinimumHeight(46)
        self.create_return_btn.setStyleSheet(
            "QPushButton { background: #2563eb; color: white; border: none; border-radius: 6px; "
            "font-size: 15px; font-weight: 700; padding: 10px 18px; }"
            "QPushButton:hover { background: #1d4ed8; } QPushButton:pressed { background: #1e40af; }"
        )
        self.create_return_btn.clicked.connect(self.create_return_invoice)
        layout.addWidget(self.create_return_btn)

        self.history_group = QGroupBox("Return History")
        self.history_group.setCheckable(True)
        self.history_group.setChecked(False)
        history_layout = QVBoxLayout(self.history_group)
        self.history_content = QWidget()
        history_content_layout = QVBoxLayout(self.history_content)
        history_content_layout.setContentsMargins(0, 4, 0, 0)

        daily_filters = QHBoxLayout()
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDisplayFormat("dd/MM/yyyy")
        self.date_filter.setDate(QDate.currentDate())
        self.refresh_btn = QPushButton()
        self.refresh_btn.clicked.connect(self.refresh)
        self.date_label = QLabel()
        daily_filters.addWidget(self.date_label)
        daily_filters.addWidget(self.date_filter)
        daily_filters.addWidget(self.refresh_btn)
        daily_filters.addStretch()
        history_content_layout.addLayout(daily_filters)

        self.table = QTableWidget(0, 6)
        self.table.setMinimumHeight(140)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        history_content_layout.addWidget(self.table)

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
        for widget in (self.history_from, self.history_to, self.history_customer, self.history_status,
                       self.history_invoice, self.history_refresh_btn):
            history_filters.addWidget(widget)
        history_content_layout.addLayout(history_filters)

        self.history_table = QTableWidget(0, 9)
        self.history_table.setHorizontalHeaderLabels(
            ["Invoice", "Date", "Type", "Customer", "Total", "Status", "Link", "Linked Invoices", "Check"]
        )
        self.history_table.setMinimumHeight(170)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        history_content_layout.addWidget(self.history_table)
        history_layout.addWidget(self.history_content)
        self.history_content.hide()
        self.history_group.toggled.connect(self.history_content.setVisible)
        layout.addWidget(self.history_group)

        self.set_page_content_widget(content)
        self.apply_language(self._language)
        self.refresh()
        self.load_full_history()
        self._update_summary()

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("returns.header", language=language))
        self.refresh_btn.setText(t("returns.refresh", language=language))
        self.date_label.setText(f"{t('common.date', language=language)}:")
        self.table.setHorizontalHeaderLabels([
            t("returns.table_invoice", language=language), t("returns.table_date", language=language),
            t("returns.table_cashier", language=language), t("returns.table_total", language=language),
            t("returns.table_method", language=language), t("returns.table_reason", language=language),
        ])

    def refresh(self) -> None:
        returns = list_return_invoices(self.date_filter.date().toString("yyyy-MM-dd"))
        self.table.setRowCount(0)
        for invoice in returns:
            row = self.table.rowCount()
            self.table.insertRow(row)
            values = (invoice.invoice_no, invoice.datetime, invoice.cashier_name, f"{invoice.total:.2f}",
                      invoice.payment_method, self._normalize_return_reason_label(invoice.return_reason))
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))

    def _normalize_return_reason_label(self, reason: str | None) -> str:
        text = (reason or "").strip()
        if "exchange" in text.lower():
            return text.replace("Exchange", "Return").replace("exchange", "return")
        return text

    def _normalize_txn_type_label(self, txn_type: str | None) -> str:
        text = (txn_type or "").strip()
        return "Return" if text.lower() == "exchange" else text

    def load_source_invoice(self) -> None:
        invoice_no = self.source_invoice_edit.text().strip()
        if not invoice_no:
            QMessageBox.information(self, "Validation", "Please enter an invoice number.")
            return
        logger = logging.getLogger(__name__)
        logger.debug("Returns load requested for invoice=%s", invoice_no)
        try:
            source_items = fetch_source_invoice_items_with_remaining_returnable_qty(invoice_no)
        except Exception as exc:
            logger.exception("Returns load failed for invoice=%s", invoice_no)
            QMessageBox.warning(self, "Load failed", f"Could not load invoice {invoice_no}: {exc}")
            return

        if not source_items:
            history = list_full_invoice_history(
                date_from="1900-01-01", date_to=QDate.currentDate().toString("yyyy-MM-dd"), invoice_no=invoice_no,
            )
            if not history:
                QMessageBox.information(self, "Not found", f"Invoice {invoice_no} was not found.")
            else:
                row = next((entry for entry in history if entry.invoice_no == invoice_no), history[0])
                if (row.txn_type or "").strip().lower() != "sale":
                    QMessageBox.information(self, "Validation", f"Invoice {invoice_no} is not a sale invoice.")
                elif (row.payment_status or "").strip().upper() != "PAID":
                    QMessageBox.information(self, "Validation", f"Invoice {invoice_no} is not PAID yet.")
                else:
                    QMessageBox.information(self, "No returnable items",
                                            f"Invoice {invoice_no} has no returnable quantity (already returned or no items).")
            logger.debug("Returns load produced no returnable items for invoice=%s", invoice_no)
            self._clear_loaded_invoice()
            return

        source = fetch_return_source_invoice(invoice_no)
        self._source_items = source_items
        self._show_invoice_info(source)
        self._populate_source_items()
        self.source_hint_label.setText("Select the items and quantities to return.")
        self._update_summary()

    def _show_invoice_info(self, source) -> None:
        if source is None:
            self.invoice_info.hide()
            return
        self.invoice_info_values["invoice_no"].setText(source.invoice_no)
        self.invoice_info_values["customer"].setText(source.customer_name or "Walk-in Customer")
        self.invoice_info_values["date"].setText(source.datetime)
        self.invoice_info_values["payment_method"].setText(source.payment_method or "—")
        self.invoice_info_values["total"].setText(f"{source.total:.2f}")
        self.invoice_info.show()

    def _populate_source_items(self) -> None:
        self.source_items_table.blockSignals(True)
        self.source_items_table.setRowCount(0)
        single_item = len(self._source_items) == 1
        for item in self._source_items:
            row = self.source_items_table.rowCount()
            self.source_items_table.insertRow(row)
            check_item = QTableWidgetItem()
            check_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check_item.setCheckState(Qt.CheckState.Checked if single_item else Qt.CheckState.Unchecked)
            self.source_items_table.setItem(row, 0, check_item)
            for column, value in enumerate((
                f"{item.product_name} ({item.product_code})", f"{item.sold_qty:.2f}",
                f"{item.returned_qty:.2f}", f"{item.remaining_qty:.2f}",
            ), start=1):
                table_item = QTableWidgetItem(value)
                table_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.source_items_table.setItem(row, column, table_item)
            qty_spin = QDoubleSpinBox()
            qty_spin.setDecimals(3)
            qty_spin.setRange(0.0, item.remaining_qty)
            qty_spin.setValue(item.remaining_qty if single_item else 0.0)
            qty_spin.valueChanged.connect(self._selection_changed)
            self.source_items_table.setCellWidget(row, 5, qty_spin)
        self.source_items_table.blockSignals(False)

    def _selected_lines(self, *, validate: bool = False) -> list[dict]:
        lines = []
        for index, item in enumerate(self._source_items):
            check_item = self.source_items_table.item(index, 0)
            if not check_item or check_item.checkState() != Qt.CheckState.Checked:
                continue
            qty_widget = self.source_items_table.cellWidget(index, 5)
            qty = float(qty_widget.value()) if isinstance(qty_widget, QDoubleSpinBox) else 0.0
            if validate and (qty <= 0 or qty > item.remaining_qty):
                raise ValueError("Invalid return quantity selected.")
            if qty > 0:
                lines.append({"source_invoice_item_id": item.invoice_item_id, "qty": qty})
        return lines

    def _selection_changed(self, *_args) -> None:
        self._update_summary()

    def _update_summary(self) -> None:
        lines = self._selected_lines()
        self.items_selected_value.setText(str(len(lines)))
        self.return_total_value.setText(f"{self._compute_return_total(lines):.2f}")
        self.summary_method_value.setText(self.return_method_combo.currentText())

    def create_return_invoice(self) -> None:
        try:
            lines = self._selected_lines(validate=True)
        except ValueError as exc:
            QMessageBox.warning(self, "Validation", str(exc))
            return
        if not lines:
            QMessageBox.warning(self, "Validation", "Select at least one line with quantity.")
            return
        return_total = self._compute_return_total(lines)
        source_invoice_no = self.source_invoice_edit.text().strip()
        ref = f"RET-{QDate.currentDate().toString('yyyyMMdd')}-{source_invoice_no}"
        reason = self.return_reason_combo.currentText()
        method = self.return_method_combo.currentText()
        QMessageBox.information(
            self, "Summary",
            f"Return Summary\nItems selected: {len(lines)}\nTotal return amount: {return_total:.2f}\n"
            f"Return method: {method}\nReference: {ref}",
        )
        try:
            invoice_no, _ = create_return_invoice_from_source(
                source_invoice_no=source_invoice_no,
                cashier_name="Returns Tab",
                return_reason=f"{reason} | Ref: {ref}",
                selected_lines=lines,
                payment_method=method,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return

        QMessageBox.information(self, "Success", f"Return invoice created: {invoice_no}")
        QMessageBox.information(self, "Linked",
                                f"Return invoice {invoice_no} is linked to source invoice {source_invoice_no}")
        self._reset_after_success()
        self.refresh()
        self.load_full_history()
        self.inventory_changed.emit()

    def _reset_after_success(self) -> None:
        self._clear_loaded_invoice()
        self.return_method_combo.setCurrentIndex(0)
        self.return_reason_combo.setCurrentIndex(0)
        self.source_invoice_edit.setFocus()
        self.source_invoice_edit.selectAll()

    def _clear_loaded_invoice(self) -> None:
        self._source_items = []
        self.source_items_table.setRowCount(0)
        self.invoice_info.hide()
        for label in self.invoice_info_values.values():
            label.setText("—")
        self.source_hint_label.setText("Load a paid sale invoice to select items for return.")
        self._update_summary()

    def _compute_return_total(self, lines: list[dict]) -> float:
        pricing_basis = str(get_config_value("jw_return_pricing_basis", "original_sold_price") or
                            "original_sold_price").strip().lower()
        if pricing_basis == "current_catalog_price":
            mapping = {item.invoice_item_id: float(self._lookup_current_product_price(item.product_id))
                       for item in self._source_items}
        else:
            mapping = {item.invoice_item_id: float(item.unit_price) for item in self._source_items}
        return sum(float(line["qty"]) * mapping.get(line["source_invoice_item_id"], 0.0) for line in lines)

    def _lookup_current_product_price(self, product_id: int) -> float:
        for product in getattr(self, "_products", []):
            if int(getattr(product, "id", 0)) == int(product_id):
                return float(getattr(product, "price", 0.0) or 0.0)
        return 0.0

    def load_full_history(self) -> None:
        rows = list_full_invoice_history(
            date_from=self.history_from.date().toString("yyyy-MM-dd"),
            date_to=self.history_to.date().toString("yyyy-MM-dd"),
            customer=self.history_customer.text(), status=self.history_status.text(),
            invoice_no=self.history_invoice.text(),
        )
        self.history_table.setRowCount(0)
        for data in rows:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            values = [
                data.invoice_no, data.datetime, self._normalize_txn_type_label(data.txn_type), data.customer_name,
                f"{data.total:.2f}", data.payment_status,
                "🟢 Linked" if data.link_state == "linked" else "⚪ Unlinked",
                data.linked_invoice_nos or "-", "✅ OK" if data.consistency_ok else "❌ Inconsistent",
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 6:
                    item.setBackground(QColor("#d1fae5" if data.link_state == "linked" else "#f3f4f6"))
                if column == 8 and not data.consistency_ok:
                    item.setBackground(QColor("#fee2e2"))
                self.history_table.setItem(row, column, item)
