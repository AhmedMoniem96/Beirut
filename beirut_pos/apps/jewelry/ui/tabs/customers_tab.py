from __future__ import annotations

from PyQt6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QMessageBox
)

from .base_tab import BaseTabContainer
from ...services.db import (
    get_customer_invoices,
    get_loyalty_history,
    get_customer_summary_rows,
    get_loyalty_balance,
    save_customer,
)


class CustomersTab(BaseTabContainer):
    def __init__(self) -> None:
        super().__init__()
        root = QWidget()
        layout = QVBoxLayout(root)

        top = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name or phone")
        self.refresh_btn = QPushButton("Refresh")
        self.add_btn = QPushButton("Add Customer")
        top.addWidget(self.search_input, 1)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.add_btn)
        layout.addLayout(top)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Name", "Phone", "Loyalty Points", "Total Spend", "Invoice Count", "Last Invoice Date", "Notes"
        ])
        layout.addWidget(self.table)

        details = QFormLayout()
        self.name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.address_input = QLineEdit()
        self.notes_input = QLineEdit()
        self.points_input = QLineEdit("0")
        self.points_input.setReadOnly(True)
        details.addRow("Customer Name", self.name_input)
        details.addRow("Phone", self.phone_input)
        details.addRow("Address", self.address_input)
        details.addRow("Notes", self.notes_input)
        details.addRow("Loyalty Points", self.points_input)
        layout.addLayout(details)

        self.invoices_table = QTableWidget(0, 6)
        self.invoices_table.setHorizontalHeaderLabels([
            "Invoice No", "Date", "Total", "Status", "Payment Method", "Loyalty Earned/Redeemed"
        ])
        layout.addWidget(self.invoices_table)

        self.loyalty_history_table = QTableWidget(0, 4)
        self.loyalty_history_table.setHorizontalHeaderLabels([
            "Date", "Invoice No", "Reason", "Points Delta"
        ])
        layout.addWidget(self.loyalty_history_table)

        actions = QHBoxLayout()
        self.save_btn = QPushButton("Save Customer")
        self.delete_btn = QPushButton("Delete Customer")
        self.refresh_inv_btn = QPushButton("View Invoices / Refresh Invoices")
        actions.addWidget(self.save_btn)
        actions.addWidget(self.delete_btn)
        actions.addWidget(self.refresh_inv_btn)
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

        self.refresh()

    def apply_language(self, _language: str) -> None:
        return

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
            loyalty = f"{entry['loyalty_earned']:.0f}/{entry['loyalty_redeemed']:.0f}"
            values = [entry["invoice_no"], entry["date"], f"{entry['total']:.2f}", entry["status"], entry["payment_method"], loyalty]
            for col, value in enumerate(values):
                self.invoices_table.setItem(row, col, QTableWidgetItem(str(value)))
        history = get_loyalty_history(self._selected_customer_id)
        for entry in history:
            row = self.loyalty_history_table.rowCount()
            self.loyalty_history_table.insertRow(row)
            values = [entry["created_at"], entry["invoice_no"], entry["reason"], f"{entry['points_delta']:.2f}"]
            for col, value in enumerate(values):
                self.loyalty_history_table.setItem(row, col, QTableWidgetItem(str(value)))

    def _save_customer(self) -> None:
        name = self.name_input.text().strip()
        phone = self.phone_input.text().strip()
        if not name or not phone:
            QMessageBox.warning(self, "Customer", "Name and phone are required")
            return
        cid = save_customer(
            name=name,
            phone=phone,
            address=self.address_input.text().strip(),
            notes=self.notes_input.text().strip(),
            selected_phone=self._selected_customer_id if not self._is_new_customer_mode else "",
        )
        if not cid:
            QMessageBox.warning(self, "Customer", "Name and phone are required")
            return
        self._is_new_customer_mode = False
        self._selected_customer_id = cid
        self.refresh()
        self._select_customer_in_table(cid)
        self._refresh_invoices()

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
        QMessageBox.information(self, "Customers", "Delete is not currently supported.")
