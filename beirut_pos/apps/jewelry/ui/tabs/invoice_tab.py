"""Invoice tab for Jewelry app."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
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
    QFileDialog,
)

from ...services.db import (
    JewelryInvoiceItem,
    create_invoice,
    fetch_invoice_details,
    find_product_by_code,
    list_payment_methods,
    list_products,
)
from ...services.pdf_exports import GalleryInfo, export_invoice_pdf
from ...services.session import get_current_user
from ...services.settings import load_gallery_settings


class InvoiceTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._last_invoice_no: Optional[str] = None
        self._products = []

        layout = QHBoxLayout(self)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        header = QLabel("New Invoice (فاتورة جديدة)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        left_layout.addWidget(header)

        self.invoice_info_label = QLabel("Invoice No: Auto | رقم الفاتورة: تلقائي")
        left_layout.addWidget(self.invoice_info_label)

        form_box = QGroupBox("Invoice Info (بيانات الفاتورة)")
        form_layout = QFormLayout(form_box)
        self.cashier_input = QLineEdit()
        self.cashier_input.setReadOnly(True)
        self.txn_type_combo = QComboBox()
        self.txn_type_combo.addItems(["Sale (بيع)", "Return (مرتجع)"])
        self.payment_combo = QComboBox()
        self.payment_combo.currentTextChanged.connect(self._refresh_summary_labels)
        self.discount_type_combo = QComboBox()
        self.discount_type_combo.addItem("Amount (قيمة)", "amount")
        self.discount_type_combo.addItem("Percent (%)", "percent")
        self.discount_type_combo.currentIndexChanged.connect(self._handle_discount_type_change)
        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0, 999999)
        self.discount_input.setDecimals(2)
        self.discount_input.valueChanged.connect(self._recalculate_totals)
        self.notes_input = QTextEdit()
        self.notes_input.setFixedHeight(50)
        self.return_reason_input = QLineEdit()
        self.return_reason_input.setPlaceholderText("Reason (سبب المرتجع)")
        self.return_reason_input.setEnabled(False)
        self.txn_type_combo.currentIndexChanged.connect(self._handle_txn_type_change)

        form_layout.addRow("Cashier (الكاشير):", self.cashier_input)
        form_layout.addRow("Transaction (العملية):", self.txn_type_combo)
        form_layout.addRow("Payment Method (طريقة الدفع):", self.payment_combo)
        form_layout.addRow("Discount Type (نوع الخصم):", self.discount_type_combo)
        form_layout.addRow("Discount Value (قيمة الخصم):", self.discount_input)
        form_layout.addRow("Notes (ملاحظات):", self.notes_input)
        form_layout.addRow("Return Reason (سبب المرتجع):", self.return_reason_input)
        left_layout.addWidget(form_box)

        product_box = QGroupBox("Products (المنتجات)")
        product_layout = QGridLayout(product_box)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name, SKU, barcode...")
        self.search_input.textChanged.connect(self.refresh_products)
        product_layout.addWidget(QLabel("Search (بحث):"), 0, 0)
        product_layout.addWidget(self.search_input, 0, 1, 1, 2)

        self.products_table = QTableWidget(0, 5)
        self.products_table.setHorizontalHeaderLabels(
            ["Name (الاسم)", "SKU (الكود)", "Barcode", "Price (السعر)", "Stock (المخزون)"]
        )
        self.products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.products_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.products_table.setAlternatingRowColors(True)
        self.products_table.cellDoubleClicked.connect(self._add_selected_product)

        self.qty_input = QSpinBox()
        self.qty_input.setRange(1, 1000)
        self.add_btn = QPushButton("Add Item (إضافة)")
        self.add_btn.clicked.connect(self._add_selected_product)

        product_layout.addWidget(self.products_table, 1, 0, 1, 3)
        product_layout.addWidget(QLabel("Qty (الكمية):"), 2, 0)
        product_layout.addWidget(self.qty_input, 2, 1)
        product_layout.addWidget(self.add_btn, 2, 2)
        left_layout.addWidget(product_box)

        items_box = QGroupBox("Invoice Items (عناصر الفاتورة)")
        items_layout = QVBoxLayout(items_box)
        self.items_table = QTableWidget(0, 5)
        self.items_table.setHorizontalHeaderLabels(
            ["Product", "Code", "Qty", "Unit Price", "Line Total"]
        )
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.setAlternatingRowColors(True)
        items_layout.addWidget(self.items_table)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove Item (حذف)")
        self.remove_btn.clicked.connect(self._remove_selected_item)
        btn_row.addWidget(self.remove_btn)
        items_layout.addLayout(btn_row)
        left_layout.addWidget(items_box)

        layout.addLayout(left_layout, stretch=3)

        totals_box = QGroupBox("Summary (ملخص)")
        totals_layout = QVBoxLayout(totals_box)
        self.subtotal_label = QLabel("Subtotal: 0.00")
        self.discount_summary_label = QLabel("Discount: 0.00")
        self.total_label = QLabel("Net Total: 0.00")
        self.payment_label = QLabel("Payment: -")
        totals_layout.addWidget(self.subtotal_label)
        totals_layout.addWidget(self.discount_summary_label)
        totals_layout.addWidget(self.total_label)
        totals_layout.addWidget(self.payment_label)
        right_layout.addWidget(totals_box)

        actions_layout = QVBoxLayout()
        self.save_btn = QPushButton("Save Invoice (حفظ الفاتورة)")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save_invoice)
        self.export_btn = QPushButton("Export PDF (تصدير PDF)")
        self.export_btn.clicked.connect(self._export_invoice_pdf)
        self.print_btn = QPushButton("Print (طباعة)")
        self.print_btn.clicked.connect(self._print_invoice)
        self.clear_btn = QPushButton("New Invoice (فاتورة جديدة)")
        self.clear_btn.clicked.connect(self._clear_invoice)
        actions_layout.addWidget(self.save_btn)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addWidget(self.print_btn)
        actions_layout.addWidget(self.clear_btn)
        right_layout.addLayout(actions_layout)
        right_layout.addStretch()
        layout.addLayout(right_layout, stretch=1)

        self._refresh_payment_methods()
        self.refresh_products()
        self._initialize_cashier()

    def _initialize_cashier(self) -> None:
        user = get_current_user()
        if user:
            self.set_cashier_name(user.full_name)

    def set_cashier_name(self, name: str) -> None:
        self.cashier_input.setText(name)

    def _refresh_payment_methods(self) -> None:
        self.payment_combo.clear()
        for _id, name_ar, name_en in list_payment_methods():
            self.payment_combo.addItem(f"{name_en} ({name_ar})", _id)
        self._refresh_summary_labels()

    def refresh_products(self, _text: str | None = None) -> None:
        search = self.search_input.text().strip()
        self._products = list_products(search=search if search else None)
        self.products_table.setRowCount(0)
        for product in self._products:
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            self.products_table.setItem(row, 0, QTableWidgetItem(f"{product.name_en} / {product.name_ar}"))
            self.products_table.setItem(row, 1, QTableWidgetItem(product.sku))
            self.products_table.setItem(row, 2, QTableWidgetItem(product.barcode))
            self.products_table.setItem(row, 3, QTableWidgetItem(f"{product.price:.2f}"))
            self.products_table.setItem(row, 4, QTableWidgetItem(f"{product.qty_on_hand:.2f}"))
            self.products_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, product.id)

    def _handle_txn_type_change(self) -> None:
        is_return = self.txn_type_combo.currentIndex() == 1
        self.return_reason_input.setEnabled(is_return)
        self._refresh_summary_labels()

    def _handle_discount_type_change(self) -> None:
        if self._discount_type() == "percent":
            self.discount_input.setRange(0, 100)
            self.discount_input.setSuffix("%")
        else:
            self.discount_input.setRange(0, 999999)
            self.discount_input.setSuffix("")
        self._recalculate_totals()

    def _discount_type(self) -> str:
        return self.discount_type_combo.currentData() or "amount"

    def _calculate_discount_amount(self, subtotal: float) -> float:
        discount_value = float(self.discount_input.value())
        if self._discount_type() == "percent":
            return max(subtotal * (discount_value / 100.0), 0.0)
        return max(discount_value, 0.0)

    def _add_selected_product(self) -> None:
        row = self.products_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select", "Please select a product.")
            return
        product_id = self.products_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        product = next((p for p in self._products if p.id == product_id), None)
        if not product:
            return
        self._add_product_to_invoice(product, float(self.qty_input.value()))

    def _remove_selected_item(self) -> None:
        row = self.items_table.currentRow()
        if row >= 0:
            self.items_table.removeRow(row)
            self._recalculate_totals()

    def _recalculate_totals(self) -> None:
        subtotal = 0.0
        for row in range(self.items_table.rowCount()):
            subtotal += float(self.items_table.item(row, 4).text())
        discount = self._calculate_discount_amount(subtotal)
        total = max(subtotal - discount, 0.0)
        self.subtotal_label.setText(f"Subtotal: {subtotal:.2f}")
        self.total_label.setText(f"Net Total: {total:.2f}")
        self._refresh_summary_labels()

    def _calculate_subtotal(self) -> float:
        subtotal = 0.0
        for row in range(self.items_table.rowCount()):
            subtotal += float(self.items_table.item(row, 4).text())
        return subtotal

    def _collect_items(self) -> List[JewelryInvoiceItem]:
        items = []
        for row in range(self.items_table.rowCount()):
            product_id = self.items_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            name = self.items_table.item(row, 0).text()
            code = self.items_table.item(row, 1).text()
            qty = float(self.items_table.item(row, 2).text())
            unit_price = float(self.items_table.item(row, 3).text())
            line_total = float(self.items_table.item(row, 4).text())
            items.append(
                JewelryInvoiceItem(
                    product_id=product_id,
                    product_name=name,
                    product_code=code,
                    qty=qty,
                    unit_price=unit_price,
                    line_total=line_total,
                )
            )
        return items

    def _save_invoice(self) -> None:
        if self.items_table.rowCount() == 0:
            QMessageBox.warning(self, "Missing Items", "Add at least one item.")
            return
        cashier = self.cashier_input.text().strip() or "N/A"
        txn_type = "return" if self.txn_type_combo.currentIndex() == 1 else "sale"
        subtotal = self._calculate_subtotal()
        discount_type = self._discount_type()
        discount_value = float(self.discount_input.value())
        discount = self._calculate_discount_amount(subtotal)
        total = max(subtotal - discount, 0.0)
        payment_method = self.payment_combo.currentText()
        notes = self.notes_input.toPlainText().strip()
        return_reason = self.return_reason_input.text().strip() if txn_type == "return" else ""
        items = self._collect_items()
        invoice_no = create_invoice(
            cashier,
            txn_type,
            subtotal,
            discount,
            discount_type,
            discount_value,
            total,
            payment_method,
            notes,
            return_reason,
            items,
        )
        self._last_invoice_no = invoice_no
        self.invoice_info_label.setText(f"Invoice No: {invoice_no}")
        QMessageBox.information(self, "Saved", f"Invoice saved: {invoice_no}")
        self.refresh_products()

    def _export_invoice_pdf(self) -> None:
        if not self._last_invoice_no:
            QMessageBox.warning(self, "Export", "Save invoice first.")
            return
        invoice, items = fetch_invoice_details(self._last_invoice_no)
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Invoice PDF",
            f"{invoice.invoice_no}.pdf",
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        gallery_settings = load_gallery_settings()
        gallery = GalleryInfo(
            name_en=gallery_settings.name_en,
            name_ar=gallery_settings.name_ar,
            address=gallery_settings.address,
            phone=gallery_settings.phone,
            logo_path=gallery_settings.logo_path or None,
            font_path=gallery_settings.font_path or None,
        )
        export_invoice_pdf(
            path,
            gallery,
            invoice.invoice_no,
            invoice.datetime,
            invoice.cashier_name,
            invoice.txn_type,
            [(i.product_name, i.product_code, i.qty, i.unit_price, i.line_total) for i in items],
            invoice.subtotal,
            invoice.discount,
            invoice.discount_type,
            invoice.discount_value,
            invoice.total,
            invoice.payment_method,
            invoice.notes,
            invoice.return_reason,
        )
        QMessageBox.information(self, "Export", "Invoice PDF exported.")

    def _print_invoice(self) -> None:
        if not self._last_invoice_no:
            QMessageBox.warning(self, "Print", "Save invoice first.")
            return
        tmp_path = Path.cwd() / f"{self._last_invoice_no}.pdf"
        invoice, items = fetch_invoice_details(self._last_invoice_no)
        gallery_settings = load_gallery_settings()
        gallery = GalleryInfo(
            name_en=gallery_settings.name_en,
            name_ar=gallery_settings.name_ar,
            address=gallery_settings.address,
            phone=gallery_settings.phone,
            logo_path=gallery_settings.logo_path or None,
            font_path=gallery_settings.font_path or None,
        )
        export_invoice_pdf(
            str(tmp_path),
            gallery,
            invoice.invoice_no,
            invoice.datetime,
            invoice.cashier_name,
            invoice.txn_type,
            [(i.product_name, i.product_code, i.qty, i.unit_price, i.line_total) for i in items],
            invoice.subtotal,
            invoice.discount,
            invoice.discount_type,
            invoice.discount_value,
            invoice.total,
            invoice.payment_method,
            invoice.notes,
            invoice.return_reason,
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(tmp_path)))

    def _clear_invoice(self) -> None:
        self.items_table.setRowCount(0)
        self.discount_type_combo.setCurrentIndex(0)
        self.discount_input.setValue(0.0)
        self.notes_input.clear()
        self.return_reason_input.clear()
        self._last_invoice_no = None
        self.invoice_info_label.setText("Invoice No: Auto | رقم الفاتورة: تلقائي")
        self._recalculate_totals()

    def _add_product_to_invoice(self, product, qty: float) -> None:
        for row in range(self.items_table.rowCount()):
            if self.items_table.item(row, 0).data(Qt.ItemDataRole.UserRole) == product.id:
                existing_qty = float(self.items_table.item(row, 2).text())
                new_qty = existing_qty + qty
                self.items_table.setItem(row, 2, QTableWidgetItem(f"{new_qty:.2f}"))
                line_total = new_qty * product.price
                self.items_table.setItem(row, 4, QTableWidgetItem(f"{line_total:.2f}"))
                self._recalculate_totals()
                return
        line_total = qty * product.price
        item_row = self.items_table.rowCount()
        self.items_table.insertRow(item_row)
        self.items_table.setItem(item_row, 0, QTableWidgetItem(f"{product.name_en} / {product.name_ar}"))
        self.items_table.setItem(item_row, 1, QTableWidgetItem(product.sku))
        self.items_table.setItem(item_row, 2, QTableWidgetItem(f"{qty:.2f}"))
        self.items_table.setItem(item_row, 3, QTableWidgetItem(f"{product.price:.2f}"))
        self.items_table.setItem(item_row, 4, QTableWidgetItem(f"{line_total:.2f}"))
        self.items_table.item(item_row, 0).setData(Qt.ItemDataRole.UserRole, product.id)
        self._recalculate_totals()

    def handle_scan(self, code: str) -> str:
        product = find_product_by_code(code)
        if not product:
            return f"Unknown barcode: {code}"
        self._add_product_to_invoice(product, 1.0)
        return f"Added: {product.name_en}"

    def _refresh_summary_labels(self) -> None:
        subtotal = self._calculate_subtotal()
        discount_amount = self._calculate_discount_amount(subtotal)
        if self._discount_type() == "percent":
            discount_value = float(self.discount_input.value())
            discount_text = f"{discount_value:.2f}% ({discount_amount:.2f})"
        else:
            discount_text = f"{discount_amount:.2f}"
        self.discount_summary_label.setText(f"Discount: {discount_text}")
        self.payment_label.setText(f"Payment: {self.payment_combo.currentText() or '-'}")
