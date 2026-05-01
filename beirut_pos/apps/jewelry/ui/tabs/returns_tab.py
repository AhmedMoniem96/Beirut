"""Returns tab for Jewelry app."""

from __future__ import annotations

from PyQt6.QtCore import QDate
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
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from ...services.db import (
    create_return_invoice_from_source,
    fetch_source_invoice_items_with_remaining_returnable_qty,
    link_return_invoice_to_source,
    list_full_invoice_history,
    list_linked_invoices,
    list_return_invoices,
    unlink_return_invoice_from_source,
)
from ...services.i18n import get_ui_language, t
from ...services.session import get_current_user
from .base_tab import BaseTabContainer


class ReturnsTab(BaseTabContainer):
    def __init__(self) -> None:
        super().__init__()
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
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        source_row = QHBoxLayout()
        self.source_invoice_edit = QLineEdit()
        self.source_invoice_edit.setPlaceholderText("Source sale invoice no")
        self.load_source_btn = QPushButton("Load")
        self.load_source_btn.clicked.connect(self.load_source_invoice)
        source_row.addWidget(self.source_invoice_edit)
        source_row.addWidget(self.load_source_btn)
        layout.addLayout(source_row)

        self.source_items_table = QTableWidget(0, 6)
        self.source_items_table.setHorizontalHeaderLabels(["Return?", "Item", "Sold", "Returned", "Remaining", "Qty to return"])
        self.source_items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.source_items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.source_items_table)

        action_row = QHBoxLayout()
        self.create_return_btn = QPushButton("Create Return Invoice")
        self.create_return_btn.clicked.connect(self.create_return_invoice)
        self.manual_source_edit = QLineEdit()
        self.manual_source_edit.setPlaceholderText("Manual source invoice")
        self.manual_return_edit = QLineEdit()
        self.manual_return_edit.setPlaceholderText("Manual return invoice")
        self.manual_link_btn = QPushButton("Link Return ↔ Source")
        self.manual_link_btn.clicked.connect(self.manual_link_return)
        action_row.addWidget(self.create_return_btn)
        action_row.addWidget(self.manual_source_edit)
        action_row.addWidget(self.manual_return_edit)
        action_row.addWidget(self.manual_link_btn)
        layout.addLayout(action_row)

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
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.history_table)

        admin_row = QHBoxLayout()
        self.view_links_btn = QPushButton("View Linked Invoices")
        self.unlink_btn = QPushButton("Unlink with Audit Log")
        self.view_links_btn.clicked.connect(self.view_linked_invoices)
        self.unlink_btn.clicked.connect(self.unlink_selected_link)
        admin_row.addWidget(self.view_links_btn)
        admin_row.addWidget(self.unlink_btn)
        layout.addLayout(admin_row)

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
            self.table.setItem(row, 5, QTableWidgetItem(invoice.return_reason))

    def load_source_invoice(self) -> None:
        invoice_no = self.source_invoice_edit.text().strip()
        if not invoice_no:
            return
        self._source_items = fetch_source_invoice_items_with_remaining_returnable_qty(invoice_no)
        self.source_items_table.setRowCount(0)
        for item in self._source_items:
            row = self.source_items_table.rowCount()
            self.source_items_table.insertRow(row)
            check_item = QTableWidgetItem()
            check_item.setCheckState(check_item.CheckState.Unchecked)
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
            if not check_item or check_item.checkState() != check_item.CheckState.Checked:
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
        try:
            invoice_no, _ = create_return_invoice_from_source(
                source_invoice_no=self.source_invoice_edit.text().strip(),
                cashier_name="Returns Tab",
                return_reason="Manual return from returns tab",
                selected_lines=lines,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        QMessageBox.information(self, "Success", f"Return invoice created: {invoice_no}")
        self.load_source_invoice()
        self.refresh()

    def manual_link_return(self) -> None:
        user = get_current_user()
        if not user or user.role != "Admin":
            QMessageBox.warning(self, "Admin only", "This action is admin-only.")
            return
        try:
            link_return_invoice_to_source(
                source_invoice_no=self.manual_source_edit.text(),
                return_invoice_no=self.manual_return_edit.text(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Link failed", str(exc))
            return
        QMessageBox.information(self, "Linked", "Return invoice linked to source successfully.")
        self.load_full_history()

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
                data.txn_type,
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

    def view_linked_invoices(self) -> None:
        user = get_current_user()
        if not user or user.role != "Admin":
            QMessageBox.warning(self, "Admin only", "This action is admin-only.")
            return
        row = self.history_table.currentRow()
        if row < 0:
            return
        invoice_no = self.history_table.item(row, 0).text()
        linked = list_linked_invoices(invoice_no)
        QMessageBox.information(self, "Linked invoices", "\n".join(linked) if linked else "No linked invoices.")

    def unlink_selected_link(self) -> None:
        user = get_current_user()
        if not user or user.role != "Admin":
            QMessageBox.warning(self, "Admin only", "This action is admin-only.")
            return
        source_no, ok1 = QInputDialog.getText(self, "Unlink", "Source invoice no:")
        if not ok1:
            return
        return_no, ok2 = QInputDialog.getText(self, "Unlink", "Return invoice no:")
        if not ok2:
            return
        reason, ok3 = QInputDialog.getText(self, "Audit reason", "Reason:")
        if not ok3:
            return
        try:
            unlink_return_invoice_from_source(source_no, return_no, actor=user.username, reason=reason)
        except Exception as exc:
            QMessageBox.critical(self, "Unlink failed", str(exc))
            return
        QMessageBox.information(self, "Unlinked", "Link removed and audit entry recorded.")
        self.load_full_history()
