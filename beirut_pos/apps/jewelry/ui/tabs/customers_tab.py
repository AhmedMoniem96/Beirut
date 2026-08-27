from __future__ import annotations

from PyQt6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QMessageBox
)

from .base_tab import BaseTabContainer
from ...services.i18n import get_ui_language, t
from ...services.db import (
    get_customer_invoices,
    get_loyalty_history,
    get_customer_summary_rows,
    get_loyalty_balance,
    save_customer,
)
from ..dialogs.invoice_details_dialog import InvoiceDetailsDialog


class CustomersTab(BaseTabContainer):
    def __init__(self) -> None:
        super().__init__()
        self._language = get_ui_language()
        root = QWidget()
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        self.search_input = QLineEdit()
        self.refresh_btn = QPushButton()
        self.add_btn = QPushButton()
        top.addWidget(self.search_input, 1)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([""] * 7)
        layout.addWidget(self.table)

        details = QFormLayout()
        self.name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.address_input = QLineEdit()
        self.notes_input = QLineEdit()
        self.points_input = QLineEdit("0")
        self.points_input.setReadOnly(True)
        self.customer_name_label = QLabel()
        self.phone_label = QLabel()
        self.address_label = QLabel()
        self.notes_label = QLabel()
        self.loyalty_points_label = QLabel()
        details.addRow(self.customer_name_label, self.name_input)
        details.addRow(self.phone_label, self.phone_input)
        details.addRow(self.address_label, self.address_input)
        details.addRow(self.notes_label, self.notes_input)
        details.addRow(self.loyalty_points_label, self.points_input)
        layout.addLayout(details)

        self.invoices_table = QTableWidget(0, 4)
        self.invoices_table.setHorizontalHeaderLabels([""] * 4)
        self.invoices_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.invoices_table.cellDoubleClicked.connect(self._view_selected_invoice)
        layout.addWidget(self.invoices_table)

        self.loyalty_history_table = QTableWidget(0, 4)
        self.loyalty_history_table.setHorizontalHeaderLabels([
            "Date", "Invoice No", "Reason", "Points Delta"
        ])
        layout.addWidget(self.loyalty_history_table)

        actions = QHBoxLayout()
        self.save_btn = QPushButton()
        self.delete_btn = QPushButton()
        self.refresh_inv_btn = QPushButton()
        self.view_invoice_btn = QPushButton("View Details")
        actions.addWidget(self.save_btn)
        actions.addWidget(self.delete_btn)
        actions.addWidget(self.refresh_inv_btn)
        actions.addWidget(self.view_invoice_btn)
        layout.addLayout(actions)

        self.set_page_content_widget(root)
        self._rows = []
        self._selected_customer_id = ""
        self._is_new_customer_mode = True

        self.refresh_btn.clicked.connect(self.refresh)
        self.search_input.returnPressed.connect(self.refresh)
        self.add_btn.clicked.connect(self._new_customer)
        self.table.itemSelectionChanged.connect(self._on_selected)
        self.save_btn.clicked.connect(self._save_customer)
        self.refresh_inv_btn.clicked.connect(self._refresh_invoices)
        self.delete_btn.clicked.connect(self._delete_not_supported)
        self.view_invoice_btn.clicked.connect(self._view_selected_invoice)

        self.apply_language(self._language)
        self.refresh()

    def apply_language(self, language: str) -> None:
        self._language = language
        self.search_input.setPlaceholderText(t("customers.search_placeholder", language=self._language))
        self.refresh_btn.setText(t("common.refresh", language=self._language))
        self.add_btn.setText(t("customers.add_customer", language=self._language))
        self.save_btn.setText(t("customers.save_customer", language=self._language))
        self.delete_btn.setText(t("customers.delete_customer", language=self._language))
        self.refresh_inv_btn.setText(t("customers.customer_invoices", language=self._language))
        self.table.setHorizontalHeaderLabels([
            t("customers.customer_name", language=self._language),
            t("customers.phone", language=self._language),
            t("customers.loyalty_points", language=self._language),
            t("customers.total_spend", language=self._language),
            t("customers.invoice_count", language=self._language),
            t("customers.last_invoice_date", language=self._language),
            t("customers.notes", language=self._language),
        ])
        self.invoices_table.setHorizontalHeaderLabels([
            t("customers.invoice_no", language=self._language),
            t("customers.date", language=self._language),
            t("customers.total", language=self._language),
            t("customers.status", language=self._language),
        ])
        self.customer_name_label.setText(t("customers.customer_name", language=self._language))
        self.phone_label.setText(t("customers.phone", language=self._language))
        self.address_label.setText(t("customers.address", language=self._language))
        self.notes_label.setText(t("customers.notes", language=self._language))
        self.loyalty_points_label.setText(t("customers.loyalty_points", language=self._language))

    def refresh(self) -> None:
        term = self.search_input.text().strip() or None
        self._rows = get_customer_summary_rows(term)
        self.table.setRowCount(0)
        for row_data in self._rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            points = get_loyalty_balance(row_data["phone"])
            values = [
                row_data["name"], row_data["phone"], f"{points:.2f}", f"{row_data['total_spend']:.2f}",
                str(row_data["invoice_count"]), row_data["last_invoice_date"], row_data.get("notes", "")
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))

    def _on_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return
        c = self._rows[row]
        self._selected_customer_id = c["phone"]
        self._is_new_customer_mode = False
        self.name_input.setText(c["name"])
        self.phone_input.setText(c["phone"])
        self.address_input.setText(c.get("address", ""))
        self.notes_input.setText(c.get("notes", ""))
        self.points_input.setText(f"{get_loyalty_balance(c['phone']):.2f}")
        self._refresh_invoices()

    def _refresh_invoices(self) -> None:
        self.invoices_table.setRowCount(0)
        self.loyalty_history_table.setRowCount(0)
        if not self._selected_customer_id:
            return
        rows = get_customer_invoices(self._selected_customer_id)
        for entry in rows:
            row = self.invoices_table.rowCount()
            self.invoices_table.insertRow(row)
            values = [entry["invoice_no"], entry["date"], f"{entry['total']:.2f}", entry["status"]]
            for col, value in enumerate(values):
                self.invoices_table.setItem(row, col, QTableWidgetItem(str(value)))
        history = get_loyalty_history(self._selected_customer_id)
        for entry in history:
            row = self.loyalty_history_table.rowCount()
            self.loyalty_history_table.insertRow(row)
            values = [entry["created_at"], entry["invoice_no"], entry["reason"], f"{entry['points_delta']:.2f}"]
            for col, value in enumerate(values):
                self.loyalty_history_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _view_selected_invoice(self, *_args) -> None:
        row = self.invoices_table.currentRow()
        item = self.invoices_table.item(row, 0) if row >= 0 else None
        if item is not None:
            InvoiceDetailsDialog(item.text(), self).exec()

    def _save_customer(self) -> None:
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        if not name or not phone:
            QMessageBox.warning(self, t("customers.title", language=self._language), t("customers.required_name_phone", language=self._language))
            return
        is_new_customer = self._is_new_customer_mode
        cid = save_customer(
            name=name,
            phone=phone,
            address=self.address_input.text().strip(),
            notes=self.notes_input.text().strip(),
            selected_phone=self._selected_customer_id if not self._is_new_customer_mode else "",
        )
        if not cid:
            QMessageBox.warning(self, t("customers.title", language=self._language), t("customers.required_name_phone", language=self._language))
            return
        self._is_new_customer_mode = False
        self._selected_customer_id = cid
        self.refresh()
        self._select_customer_in_table(cid)
        self._refresh_invoices()
        message_key = (
            "customers.created_successfully"
            if is_new_customer
            else "customers.updated_successfully"
        )
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t(message_key, language=self._language),
        )

    def _new_customer(self) -> None:
        self.table.clearSelection()
        self._selected_customer_id = ""
        self._is_new_customer_mode = True
        self.name_input.clear()
        self.phone_input.clear()
        self.address_input.clear()
        self.notes_input.clear()
        self.points_input.setText("0")
        self.invoices_table.setRowCount(0)
        self.loyalty_history_table.setRowCount(0)
        self.name_input.setFocus()

    def _select_customer_in_table(self, customer_phone: str) -> None:
        for index, row in enumerate(self._rows):
            if row.get("phone") == customer_phone:
                self.table.selectRow(index)
                return

    def _delete_not_supported(self) -> None:
        QMessageBox.information(
            self,
            t("customers.title", language=self._language),
            t("customers.delete_not_supported", language=self._language),
        )
