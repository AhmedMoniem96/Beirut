"""Inventory tab for Jewelry app."""

from __future__ import annotations

from PyQt6.QtCore import QElapsedTimer, QEvent, Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from ...services.db import barcode_exists, delete_product, list_products, save_product
from ...services.pdf_exports import export_barcode_labels_pdf


class InventoryTab(QWidget):
    def __init__(self, on_products_changed=None) -> None:
        super().__init__()
        self._on_products_changed = on_products_changed
        self._selected_product_id = None
        self._products = []
        self._allow_edit = True
        self._scan_buffer = ""
        self._scan_timer = QElapsedTimer()
        self._scan_timer.start()
        QApplication.instance().installEventFilter(self)

        layout = QVBoxLayout(self)
        header = QLabel("Inventory (المخزون)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Scan to search / ابحث بالاسم أو الكود أو الباركود")
        self.search_input.textChanged.connect(self.refresh)
        search_layout.addWidget(QLabel("Search (بحث):"))
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        form_box = QGroupBox("Product Details (تفاصيل المنتج)")
        form_layout = QFormLayout(form_box)
        self.name_ar_input = QLineEdit()
        self.name_en_input = QLineEdit()
        self.sku_input = QLineEdit()
        self.barcode_input = QLineEdit()
        self.barcode_type_input = QLineEdit()
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 999999)
        self.price_input.setDecimals(2)
        self.qty_input = QDoubleSpinBox()
        self.qty_input.setRange(0, 999999)
        self.qty_input.setDecimals(2)
        self.min_qty_input = QDoubleSpinBox()
        self.min_qty_input.setRange(0, 999999)
        self.min_qty_input.setDecimals(2)
        self.category_input = QLineEdit()
        self.handmade_check = QCheckBox("Handmade (صناعة يدوية)")
        self.stone_type_input = QLineEdit()
        self.color_input = QLineEdit()

        form_layout.addRow("Name Arabic (الاسم عربي):", self.name_ar_input)
        form_layout.addRow("Name English (الاسم EN):", self.name_en_input)
        form_layout.addRow("SKU/Code (الكود):", self.sku_input)
        form_layout.addRow("Barcode (باركود):", self.barcode_input)
        form_layout.addRow("Barcode Type (نوع الباركود):", self.barcode_type_input)
        form_layout.addRow("Price (السعر):", self.price_input)
        form_layout.addRow("Qty On Hand (الكمية):", self.qty_input)
        form_layout.addRow("Min Qty (الحد الأدنى):", self.min_qty_input)
        form_layout.addRow("Category/Type (الفئة):", self.category_input)
        form_layout.addRow("", self.handmade_check)
        form_layout.addRow("Stone Type (نوع الحجر):", self.stone_type_input)
        form_layout.addRow("Color (اللون):", self.color_input)

        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save Product (حفظ المنتج)")
        self.save_btn.clicked.connect(self._save_product)
        self.delete_btn = QPushButton("Delete (حذف)")
        self.delete_btn.clicked.connect(self._delete_product)
        self.clear_btn = QPushButton("Clear (مسح)")
        self.clear_btn.clicked.connect(self._clear_form)
        self.print_barcode_btn = QPushButton("Print Barcode Label (طباعة باركود)")
        self.print_barcode_btn.clicked.connect(self._print_barcode_label)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addWidget(self.clear_btn)
        buttons.addWidget(self.print_barcode_btn)

        layout.addWidget(form_box)
        layout.addLayout(buttons)

        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels(
            [
                "Arabic",
                "English",
                "SKU",
                "Barcode",
                "Type",
                "Price",
                "Qty",
                "Min",
                "Category",
                "Handmade",
                "Stone",
                "Color",
            ]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellClicked.connect(self._load_selected_product)
        layout.addWidget(self.table)

        self.alerts_box = QGroupBox("Stock Alerts (تنبيهات المخزون)")
        alerts_layout = QVBoxLayout(self.alerts_box)
        self.alerts_table = QTableWidget(0, 5)
        self.alerts_table.setHorizontalHeaderLabels(
            ["Name", "SKU", "Qty", "Min", "Status"]
        )
        self.alerts_table.setAlternatingRowColors(True)
        alerts_layout.addWidget(self.alerts_table)
        layout.addWidget(self.alerts_box)

        self.refresh()

    def set_edit_permissions(self, allow_edit: bool) -> None:
        self._allow_edit = allow_edit
        form_widgets = [
            self.name_ar_input,
            self.name_en_input,
            self.sku_input,
            self.barcode_input,
            self.barcode_type_input,
            self.category_input,
            self.stone_type_input,
            self.color_input,
        ]
        for widget in form_widgets:
            widget.setReadOnly(not allow_edit)
        for widget in [
            self.price_input,
            self.qty_input,
            self.min_qty_input,
            self.handmade_check,
        ]:
            widget.setEnabled(allow_edit)
        for button in [self.save_btn, self.delete_btn, self.clear_btn]:
            button.setEnabled(True)

    def refresh(self, _text: str | None = None) -> None:
        search = self.search_input.text().strip()
        products = list_products(search=search if search else None)
        self._products = products
        self.table.setRowCount(0)
        self.alerts_table.setRowCount(0)
        for product in products:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(product.name_ar))
            self.table.setItem(row, 1, QTableWidgetItem(product.name_en))
            self.table.setItem(row, 2, QTableWidgetItem(product.sku))
            self.table.setItem(row, 3, QTableWidgetItem(product.barcode))
            self.table.setItem(row, 4, QTableWidgetItem(product.barcode_type))
            self.table.setItem(row, 5, QTableWidgetItem(f"{product.price:.2f}"))
            self.table.setItem(row, 6, QTableWidgetItem(f"{product.qty_on_hand:.2f}"))
            self.table.setItem(row, 7, QTableWidgetItem(f"{product.min_qty:.2f}"))
            self.table.setItem(row, 8, QTableWidgetItem(product.category))
            self.table.setItem(row, 9, QTableWidgetItem("Yes" if product.handmade_flag else "No"))
            self.table.setItem(row, 10, QTableWidgetItem(product.stone_type))
            self.table.setItem(row, 11, QTableWidgetItem(product.color))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, product.id)

            if product.qty_on_hand <= 0 or product.qty_on_hand <= product.min_qty:
                alert_row = self.alerts_table.rowCount()
                self.alerts_table.insertRow(alert_row)
                self.alerts_table.setItem(
                    alert_row,
                    0,
                    QTableWidgetItem(f"{product.name_en} / {product.name_ar}"),
                )
                self.alerts_table.setItem(alert_row, 1, QTableWidgetItem(product.sku))
                self.alerts_table.setItem(
                    alert_row, 2, QTableWidgetItem(f"{product.qty_on_hand:.2f}")
                )
                self.alerts_table.setItem(
                    alert_row, 3, QTableWidgetItem(f"{product.min_qty:.2f}")
                )
                status = "Out" if product.qty_on_hand <= 0 else "Near"
                self.alerts_table.setItem(alert_row, 4, QTableWidgetItem(status))

    def _load_selected_product(self, row: int) -> None:
        self._selected_product_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.name_ar_input.setText(self.table.item(row, 0).text())
        self.name_en_input.setText(self.table.item(row, 1).text())
        self.sku_input.setText(self.table.item(row, 2).text())
        self.barcode_input.setText(self.table.item(row, 3).text())
        self.barcode_type_input.setText(self.table.item(row, 4).text())
        self.price_input.setValue(float(self.table.item(row, 5).text()))
        self.qty_input.setValue(float(self.table.item(row, 6).text()))
        self.min_qty_input.setValue(float(self.table.item(row, 7).text()))
        self.category_input.setText(self.table.item(row, 8).text())
        self.handmade_check.setChecked(self.table.item(row, 9).text() == "Yes")
        self.stone_type_input.setText(self.table.item(row, 10).text())
        self.color_input.setText(self.table.item(row, 11).text())

    def _save_product(self) -> None:
        if not self._allow_edit:
            QMessageBox.information(self, "Access Restricted", "Inventory adjustments are admin-only.")
            return
        if not self.name_ar_input.text().strip() or not self.name_en_input.text().strip():
            QMessageBox.warning(self, "Missing", "Arabic & English names are required.")
            return
        if not self.sku_input.text().strip():
            QMessageBox.warning(self, "Missing", "SKU is required.")
            return
        barcode_value = self.barcode_input.text().strip()
        if barcode_value and barcode_exists(barcode_value, exclude_product_id=self._selected_product_id):
            QMessageBox.warning(self, "Duplicate", "Barcode already exists on another product.")
            return
        save_product(
            self._selected_product_id,
            self.name_ar_input.text().strip(),
            self.name_en_input.text().strip(),
            self.sku_input.text().strip(),
            barcode_value,
            self.barcode_type_input.text().strip(),
            float(self.price_input.value()),
            float(self.qty_input.value()),
            float(self.min_qty_input.value()),
            self.category_input.text().strip(),
            self.handmade_check.isChecked(),
            self.stone_type_input.text().strip(),
            self.color_input.text().strip(),
        )
        QMessageBox.information(self, "Saved", "Product saved.")
        self.refresh()
        if self._on_products_changed:
            self._on_products_changed()

    def _delete_product(self) -> None:
        if not self._allow_edit:
            QMessageBox.information(self, "Access Restricted", "Inventory adjustments are admin-only.")
            return
        if not self._selected_product_id:
            return
        confirm = QMessageBox.question(self, "Delete", "Delete this product?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_product(self._selected_product_id)
        self._clear_form()
        self.refresh()
        if self._on_products_changed:
            self._on_products_changed()

    def _clear_form(self) -> None:
        if not self._allow_edit:
            QMessageBox.information(self, "Access Restricted", "Inventory adjustments are admin-only.")
            return
        self._selected_product_id = None
        self.name_ar_input.clear()
        self.name_en_input.clear()
        self.sku_input.clear()
        self.barcode_input.clear()
        self.barcode_type_input.clear()
        self.price_input.setValue(0)
        self.qty_input.setValue(0)
        self.min_qty_input.setValue(0)
        self.category_input.clear()
        self.handmade_check.setChecked(False)
        self.stone_type_input.clear()
        self.color_input.clear()

    def _print_barcode_label(self) -> None:
        if not self._selected_product_id:
            QMessageBox.warning(self, "Select", "Select a product first.")
            return
        product = next((p for p in self._products if p.id == self._selected_product_id), None)
        if not product:
            return
        if not product.barcode:
            QMessageBox.warning(self, "Missing", "Set a barcode before printing.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Barcode Labels",
            f"{product.sku}_barcode_labels.pdf",
            "PDF Files (*.pdf)",
        )
        if not path:
            return
        export_barcode_labels_pdf(
            path,
            f"{product.name_en} / {product.name_ar}",
            product.sku,
            product.barcode,
            product.barcode_type,
        )
        QMessageBox.information(self, "Export", "Barcode labels exported.")

    def handle_scan(self, code: str) -> str:
        normalized_code = self._normalize_scan_text(code)
        self.search_input.setText(normalized_code)
        self.refresh()
        return f"Search: {normalized_code}"

    def _normalize_scan_text(self, code: str) -> str:
        return code.rstrip("\r\n")

    def _dispatch_scan(self, code: str) -> None:
        message = self.handle_scan(code)
        if message and hasattr(self.window(), "statusBar"):
            status_bar = self.window().statusBar()
            if status_bar:
                status_bar.showMessage(message, 3000)

    def eventFilter(self, source, event):  # noqa: N802 - Qt naming convention
        if not self.isVisible():
            return super().eventFilter(source, event)
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._scan_timer.elapsed() < 500 and len(self._scan_buffer) >= 2:
                    self._dispatch_scan(self._scan_buffer)
                    self._scan_buffer = ""
                    return True
                self._scan_buffer = ""
            else:
                if self._scan_timer.elapsed() > 400:
                    self._scan_buffer = ""
                text = event.text()
                if text:
                    self._scan_buffer += text
                    self._scan_timer.restart()
        return super().eventFilter(source, event)
