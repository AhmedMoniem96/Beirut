"""Shared, read-only historical invoice details dialog."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QLabel, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from ...services.db import (
    attach_customer_to_invoice, fetch_invoice_details, find_customer_by_phone,
    list_customers, list_linked_invoices, save_customer,
)
from .quick_customer_dialog import QuickCustomerDialog


class InvoiceDetailsDialog(QDialog):
    """Display immutable invoice financials while allowing customer correction."""

    def __init__(self, invoice_no: str, parent=None) -> None:
        super().__init__(parent)
        self.invoice_no = invoice_no
        self.setWindowTitle("View Invoice Details")
        self.resize(850, 560)
        layout = QVBoxLayout(self)
        self.summary = QFormLayout()
        self.values = {key: QLabel() for key in (
            "invoice", "date", "customer", "payment", "subtotal", "discount", "total", "returns"
        )}
        labels = {"invoice": "Invoice #", "date": "Date", "customer": "Customer",
                  "payment": "Payment Method", "subtotal": "Subtotal",
                  "discount": "Invoice Discount", "total": "Grand / Net Total",
                  "returns": "Linked Returns"}
        for key, value in self.values.items():
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.summary.addRow(labels[key], value)
        layout.addLayout(self.summary)

        customer_actions = QHBoxLayout()
        self.customer_combo = QComboBox()
        self.customer_combo.setMinimumWidth(300)
        self.attach_btn = QPushButton("Attach / Change Customer")
        self.new_btn = QPushButton("Create Customer")
        self.edit_btn = QPushButton("Edit Customer Details")
        customer_actions.addWidget(self.customer_combo, 1)
        customer_actions.addWidget(self.attach_btn)
        customer_actions.addWidget(self.new_btn)
        customer_actions.addWidget(self.edit_btn)
        layout.addLayout(customer_actions)

        self.items_table = QTableWidget(0, 7)
        self.items_table.setHorizontalHeaderLabels(
            ["Item", "SKU / Code", "Quantity", "Unit", "Unit Price", "Discount", "Line Total"]
        )
        self.items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.items_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.items_table, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.attach_btn.clicked.connect(self._attach_customer)
        self.new_btn.clicked.connect(self._create_customer)
        self.edit_btn.clicked.connect(self._edit_customer)
        self.reload()

    def _load_customers(self, selected_phone: str = "") -> None:
        self.customer_combo.clear()
        self.customer_combo.addItem("Select customer", "")
        for customer in list_customers():
            self.customer_combo.addItem(f"{customer.name} — {customer.phone}", customer.phone)
        index = self.customer_combo.findData(selected_phone)
        self.customer_combo.setCurrentIndex(index if index >= 0 else 0)

    def reload(self) -> None:
        invoice, items = fetch_invoice_details(self.invoice_no)
        self.invoice = invoice
        self.values["invoice"].setText(invoice.invoice_no)
        self.values["date"].setText(invoice.datetime)
        self.values["customer"].setText(invoice.customer_name or "Walk-in Customer")
        self.values["payment"].setText(invoice.payment_method or "—")
        self.values["subtotal"].setText(f"{invoice.subtotal:.2f}")
        self.values["discount"].setText(f"{invoice.discount:.2f}")
        self.values["total"].setText(f"{invoice.total:.2f}")
        self.values["returns"].setText(", ".join(list_linked_invoices(invoice.invoice_no)) or "—")
        self.items_table.setRowCount(0)
        for item in items:
            row = self.items_table.rowCount()
            self.items_table.insertRow(row)
            quantity = f"{item.qty:.3f}" if item.item_type == "material" else f"{item.qty:g}"
            values = [item.product_name, item.product_code, quantity, item.unit,
                      f"{item.unit_price:.2f}", "—", f"{item.line_total:.2f}"]
            for column, value in enumerate(values):
                self.items_table.setItem(row, column, QTableWidgetItem(value))
        self._load_customers(str(invoice.customer_id or invoice.customer_phone or ""))
        self.edit_btn.setEnabled(bool(invoice.customer_id or invoice.customer_phone))

    def _attach_customer(self) -> None:
        phone = self.customer_combo.currentData()
        if not phone:
            return
        attach_customer_to_invoice(self.invoice_no, phone)
        self.reload()

    def _customer_dialog(self, customer=None) -> QuickCustomerDialog:
        dialog = QuickCustomerDialog(
            self, name=customer.name if customer else "", phone=customer.phone if customer else ""
        )
        if customer:
            dialog.email_input.setText(customer.email)
            dialog.notes_input.setText(customer.notes)
            # The phone is the customer primary key; relationship changes use
            # the dedicated Attach / Change action instead.
            dialog.phone_input.setReadOnly(True)
        return dialog

    def _create_customer(self) -> None:
        dialog = self._customer_dialog()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        phone = save_customer(**values)
        if not phone:
            QMessageBox.warning(self, "Customer", "Name and phone are required.")
            return
        attach_customer_to_invoice(self.invoice_no, phone)
        self.reload()

    def _edit_customer(self) -> None:
        phone = str(self.invoice.customer_id or self.invoice.customer_phone or "")
        customer = find_customer_by_phone(phone)
        if customer is None:
            return
        dialog = self._customer_dialog(customer)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        new_phone = save_customer(**values, selected_phone=customer.phone)
        if new_phone:
            attach_customer_to_invoice(self.invoice_no, new_phone)
            self.reload()
