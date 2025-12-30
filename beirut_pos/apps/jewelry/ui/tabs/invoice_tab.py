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

from ...services.db import JewelryInvoiceItem, create_invoice, fetch_invoice_details, list_payment_methods, list_products
from ...services.pdf_exports import GalleryInfo, export_invoice_pdf
from ...services.settings import load_gallery_settings


class InvoiceTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._last_invoice_no: Optional[str] = None
        self._products = []

        layout = QVBoxLayout(self)
        header = QLabel("New Invoice (فاتورة جديدة)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        self.invoice_info_label = QLabel("Invoice No: Auto | رقم الفاتورة: تلقائي")
        layout.addWidget(self.invoice_info_label)

        form_box = QGroupBox("Invoice Info (بيانات الفاتورة)")
        form_layout = QFormLayout(form_box)
        self.cashier_input = QLineEdit()
        self.txn_type_combo = QComboBox()
        self.txn_type_combo.addItems(["Sale (بيع)", "Return (مرتجع)"])
        self.payment_combo = QComboBox()
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
        form_layout.addRow("Discount (خصم):", self.discount_input)
        form_layout.addRow("Notes (ملاحظات):", self.notes_input)
        form_layout.addRow("Return Reason (سبب المرتجع):", self.return_reason_input)
        layout.addWidget(form_box)

        product_box = QGroupBox("Products (المنتجات)")
        product_layout = QGridLayout(product_box)
        self.products_table = QTableWidget(0, 4)
        self.products_table.setHorizontalHeaderLabels(
            ["Name (الاسم)", "SKU (الكود)", "Price (السعر)", "Stock (المخزون)"]
        )
        self.products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.products_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.products_table.cellDoubleClicked.connect(self._add_selected_product)

        self.qty_input = QSpinBox()
        self.qty_input.setRange(1, 1000)
        self.add_btn = QPushButton("Add Item (إضافة)")
        self.add_btn.clicked.connect(self._add_selected_product)

        product_layout.addWidget(self.products_table, 0, 0, 1, 3)
        product_layout.addWidget(QLabel("Qty (الكمية):"), 1, 0)
        product_layout.addWidget(self.qty_input, 1, 1)
        product_layout.addWidget(self.add_btn, 1, 2)
        layout.addWidget(product_box)

        items_box = QGroupBox("Invoice Items (عناصر الفاتورة)")
        items_layout = QVBoxLayout(items_box)
        self.items_table = QTableWidget(0, 5)
        self.items_table.setHorizontalHeaderLabels(
            ["Product", "Code", "Qty", "Unit Price", "Line Total"]
        )
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        items_layout.addWidget(self.items_table)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove Item (حذف)")
        self.remove_btn.clicked.connect(self._remove_selected_item)
        btn_row.addWidget(self.remove_btn)
        items_layout.addLayout(btn_row)
        layout.addWidget(items_box)

        totals_box = QGroupBox("Totals (الإجماليات)")
        totals_layout = QHBoxLayout(totals_box)
        self.subtotal_label = QLabel("Subtotal: 0.00")
        self.total_label = QLabel("Net Total: 0.00")
        totals_layout.addWidget(self.subtotal_label)
        totals_layout.addWidget(self.total_label)
        layout.addWidget(totals_box)

        actions_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Invoice (حفظ الفاتورة)")
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
        layout.addLayout(actions_layout)

        self._refresh_payment_methods()
        self.refresh_products()

    def _refresh_payment_methods(self) -> None:
        self.payment_combo.clear()
        for _id, name_ar, name_en in list_payment_methods():
            self.payment_combo.addItem(f"{name_en} ({name_ar})", _id)

    def refresh_products(self) -> None:
        self._products = list_products()
        self.products_table.setRowCount(0)
        for product in self._products:
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            self.products_table.setItem(row, 0, QTableWidgetItem(f"{product.name_en} / {product.name_ar}"))
            self.products_table.setItem(row, 1, QTableWidgetItem(product.sku))
            self.products_table.setItem(row, 2, QTableWidgetItem(f"{product.price:.2f}"))
            self.products_table.setItem(row, 3, QTableWidgetItem(f"{product.qty_on_hand:.2f}"))
            self.products_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, product.id)

    def _handle_txn_type_change(self) -> None:
        is_return = self.txn_type_combo.currentIndex() == 1
        self.return_reason_input.setEnabled(is_return)

    def _add_selected_product(self) -> None:
        row = self.products_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Select", "Please select a product.")
            return
        product_id = self.products_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        product = next((p for p in self._products if p.id == product_id), None)
        if not product:
            return
        qty = float(self.qty_input.value())
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

    def _remove_selected_item(self) -> None:
        row = self.items_table.currentRow()
        if row >= 0:
            self.items_table.removeRow(row)
            self._recalculate_totals()

    def _recalculate_totals(self) -> None:
        subtotal = 0.0
        for row in range(self.items_table.rowCount()):
            subtotal += float(self.items_table.item(row, 4).text())
        discount = float(self.discount_input.value())
        total = max(subtotal - discount, 0.0)
        self.subtotal_label.setText(f"Subtotal: {subtotal:.2f}")
        self.total_label.setText(f"Net Total: {total:.2f}")

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
        discount = float(self.discount_input.value())
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
            invoice.total,
            invoice.payment_method,
            invoice.notes,
            invoice.return_reason,
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(tmp_path)))

    def _clear_invoice(self) -> None:
        self.items_table.setRowCount(0)
        self.discount_input.setValue(0.0)
        self.notes_input.clear()
        self.return_reason_input.clear()
        self._last_invoice_no = None
        self.invoice_info_label.setText("Invoice No: Auto | رقم الفاتورة: تلقائي")
        self._recalculate_totals()
