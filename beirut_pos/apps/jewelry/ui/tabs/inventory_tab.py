"""Inventory tab for Jewelry app."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
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
)

from ...services.db import delete_product, list_products, save_product


class InventoryTab(QWidget):
    def __init__(self, on_products_changed=None) -> None:
        super().__init__()
        self._on_products_changed = on_products_changed
        self._selected_product_id = None

        layout = QVBoxLayout(self)
        header = QLabel("Inventory (المخزون)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        form_box = QGroupBox("Product Details (تفاصيل المنتج)")
        form_layout = QFormLayout(form_box)
        self.name_ar_input = QLineEdit()
        self.name_en_input = QLineEdit()
        self.sku_input = QLineEdit()
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
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.delete_btn)
        buttons.addWidget(self.clear_btn)

        layout.addWidget(form_box)
        layout.addLayout(buttons)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "Arabic",
                "English",
                "SKU",
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
        self.table.cellClicked.connect(self._load_selected_product)
        layout.addWidget(self.table)

        self.alerts_box = QGroupBox("Stock Alerts (تنبيهات المخزون)")
        alerts_layout = QVBoxLayout(self.alerts_box)
        self.alerts_table = QTableWidget(0, 5)
        self.alerts_table.setHorizontalHeaderLabels(
            ["Name", "SKU", "Qty", "Min", "Status"]
        )
        alerts_layout.addWidget(self.alerts_table)
        layout.addWidget(self.alerts_box)

        self.refresh()

    def refresh(self) -> None:
        products = list_products()
        self.table.setRowCount(0)
        self.alerts_table.setRowCount(0)
        for product in products:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(product.name_ar))
            self.table.setItem(row, 1, QTableWidgetItem(product.name_en))
            self.table.setItem(row, 2, QTableWidgetItem(product.sku))
            self.table.setItem(row, 3, QTableWidgetItem(f"{product.price:.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{product.qty_on_hand:.2f}"))
            self.table.setItem(row, 5, QTableWidgetItem(f"{product.min_qty:.2f}"))
            self.table.setItem(row, 6, QTableWidgetItem(product.category))
            self.table.setItem(row, 7, QTableWidgetItem("Yes" if product.handmade_flag else "No"))
            self.table.setItem(row, 8, QTableWidgetItem(product.stone_type))
            self.table.setItem(row, 9, QTableWidgetItem(product.color))
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
        self.price_input.setValue(float(self.table.item(row, 3).text()))
        self.qty_input.setValue(float(self.table.item(row, 4).text()))
        self.min_qty_input.setValue(float(self.table.item(row, 5).text()))
        self.category_input.setText(self.table.item(row, 6).text())
        self.handmade_check.setChecked(self.table.item(row, 7).text() == "Yes")
        self.stone_type_input.setText(self.table.item(row, 8).text())
        self.color_input.setText(self.table.item(row, 9).text())

    def _save_product(self) -> None:
        if not self.name_ar_input.text().strip() or not self.name_en_input.text().strip():
            QMessageBox.warning(self, "Missing", "Arabic & English names are required.")
            return
        if not self.sku_input.text().strip():
            QMessageBox.warning(self, "Missing", "SKU is required.")
            return
        save_product(
            self._selected_product_id,
            self.name_ar_input.text().strip(),
            self.name_en_input.text().strip(),
            self.sku_input.text().strip(),
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
        self._selected_product_id = None
        self.name_ar_input.clear()
        self.name_en_input.clear()
        self.sku_input.clear()
        self.price_input.setValue(0)
        self.qty_input.setValue(0)
        self.min_qty_input.setValue(0)
        self.category_input.clear()
        self.handmade_check.setChecked(False)
        self.stone_type_input.clear()
        self.color_input.clear()
