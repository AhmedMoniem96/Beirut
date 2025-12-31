"""Manufacturing tab for Jewelry app."""

from __future__ import annotations

from datetime import datetime, time
from typing import Dict, List, Optional

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...services.db import (
    check_material_availability,
    confirm_production_order,
    create_production_order,
    delete_bom,
    delete_material,
    fetch_production_order,
    list_bom_lines,
    list_boms,
    list_materials,
    list_products,
    list_production_orders,
    mark_production_done,
    save_bom,
    save_material,
)
from ...services.reports import material_usage, production_history


class ManufacturingTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        header = QLabel("Manufacturing (التصنيع)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._material_map: Dict[str, int] = {}
        self._product_map: Dict[str, int] = {}
        self._bom_entries: List[tuple[str, int, int]] = []

        self._build_materials_tab()
        self._build_boms_tab()
        self._build_orders_tab()
        self._build_reports_tab()

        self._refresh_materials()
        self._refresh_products()
        self._refresh_boms()
        self._refresh_orders()

    def _build_materials_tab(self) -> None:
        self.materials_tab = QWidget()
        layout = QVBoxLayout(self.materials_tab)

        form_box = QGroupBox("Materials (الخامات)")
        form_layout = QFormLayout(form_box)
        self.material_name_ar = QLineEdit()
        self.material_name_en = QLineEdit()
        self.material_code = QLineEdit()
        self.material_qty = QDoubleSpinBox()
        self.material_qty.setRange(0, 999999)
        self.material_qty.setDecimals(3)
        self.material_unit = QLineEdit()
        self.material_min_qty = QDoubleSpinBox()
        self.material_min_qty.setRange(0, 999999)
        self.material_min_qty.setDecimals(3)
        self.material_cost = QDoubleSpinBox()
        self.material_cost.setRange(0, 999999)
        self.material_cost.setDecimals(2)
        form_layout.addRow("Name Arabic (عربي):", self.material_name_ar)
        form_layout.addRow("Name English (EN):", self.material_name_en)
        form_layout.addRow("Code (كود):", self.material_code)
        form_layout.addRow("Qty On Hand (الكمية):", self.material_qty)
        form_layout.addRow("Unit (الوحدة):", self.material_unit)
        form_layout.addRow("Min Qty (الحد الأدنى):", self.material_min_qty)
        form_layout.addRow("Cost/Unit (تكلفة الوحدة):", self.material_cost)
        layout.addWidget(form_box)

        button_row = QHBoxLayout()
        self.material_save_btn = QPushButton("Save Material (حفظ خامة)")
        self.material_delete_btn = QPushButton("Delete (حذف)")
        self.material_clear_btn = QPushButton("Clear (مسح)")
        self.material_save_btn.clicked.connect(self._save_material)
        self.material_delete_btn.clicked.connect(self._delete_material)
        self.material_clear_btn.clicked.connect(self._clear_material_form)
        button_row.addWidget(self.material_save_btn)
        button_row.addWidget(self.material_delete_btn)
        button_row.addWidget(self.material_clear_btn)
        layout.addLayout(button_row)

        self.materials_table = QTableWidget(0, 7)
        self.materials_table.setHorizontalHeaderLabels(
            ["Arabic", "English", "Code", "Qty", "Unit", "Min", "Cost"]
        )
        self.materials_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.materials_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.materials_table.setAlternatingRowColors(True)
        self.materials_table.cellClicked.connect(self._load_material)
        layout.addWidget(self.materials_table)

        self.tabs.addTab(self.materials_tab, "Materials (الخامات)")

        self._selected_material_id: Optional[int] = None

    def _build_boms_tab(self) -> None:
        self.boms_tab = QWidget()
        layout = QVBoxLayout(self.boms_tab)

        form_box = QGroupBox("BOM / Recipe (وصفة الإنتاج)")
        form_layout = QFormLayout(form_box)
        self.bom_product_combo = QComboBox()
        self.bom_name_input = QLineEdit()
        self.bom_active_check = QCheckBox("Active (نشط)")
        form_layout.addRow("Product (المنتج):", self.bom_product_combo)
        form_layout.addRow("BOM Name (اسم الوصفة):", self.bom_name_input)
        form_layout.addRow("", self.bom_active_check)
        layout.addWidget(form_box)

        lines_box = QGroupBox("Materials Lines (مكونات الخامة)")
        lines_layout = QVBoxLayout(lines_box)
        add_line_layout = QHBoxLayout()
        self.bom_material_combo = QComboBox()
        self.bom_qty_input = QDoubleSpinBox()
        self.bom_qty_input.setRange(0.001, 999999)
        self.bom_qty_input.setDecimals(3)
        self.add_bom_line_btn = QPushButton("Add Line (إضافة خامة)")
        self.add_bom_line_btn.clicked.connect(self._add_bom_line)
        add_line_layout.addWidget(QLabel("Material (الخامة):"))
        add_line_layout.addWidget(self.bom_material_combo)
        add_line_layout.addWidget(QLabel("Qty Required (الكمية):"))
        add_line_layout.addWidget(self.bom_qty_input)
        add_line_layout.addWidget(self.add_bom_line_btn)
        lines_layout.addLayout(add_line_layout)

        self.bom_lines_table = QTableWidget(0, 2)
        self.bom_lines_table.setHorizontalHeaderLabels(["Material", "Qty Required"])
        self.bom_lines_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bom_lines_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bom_lines_table.setAlternatingRowColors(True)
        lines_layout.addWidget(self.bom_lines_table)

        remove_line_btn = QPushButton("Remove Line (حذف السطر)")
        remove_line_btn.clicked.connect(self._remove_bom_line)
        lines_layout.addWidget(remove_line_btn)
        layout.addWidget(lines_box)

        action_row = QHBoxLayout()
        self.bom_save_btn = QPushButton("Save BOM (حفظ الوصفة)")
        self.bom_delete_btn = QPushButton("Delete BOM (حذف الوصفة)")
        self.bom_clear_btn = QPushButton("Clear (مسح)")
        self.bom_save_btn.clicked.connect(self._save_bom)
        self.bom_delete_btn.clicked.connect(self._delete_bom)
        self.bom_clear_btn.clicked.connect(self._clear_bom_form)
        action_row.addWidget(self.bom_save_btn)
        action_row.addWidget(self.bom_delete_btn)
        action_row.addWidget(self.bom_clear_btn)
        layout.addLayout(action_row)

        self.boms_table = QTableWidget(0, 3)
        self.boms_table.setHorizontalHeaderLabels(["Product", "Name", "Active"])
        self.boms_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.boms_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.boms_table.setAlternatingRowColors(True)
        self.boms_table.cellClicked.connect(self._load_bom)
        layout.addWidget(self.boms_table)

        self.tabs.addTab(self.boms_tab, "BOMs (الوصفات)")

        self._selected_bom_id: Optional[int] = None

    def _build_orders_tab(self) -> None:
        self.orders_tab = QWidget()
        layout = QVBoxLayout(self.orders_tab)

        form_box = QGroupBox("Production Order (أمر إنتاج)")
        form_layout = QFormLayout(form_box)
        self.order_no_label = QLabel("Auto")
        self.order_product_combo = QComboBox()
        self.order_bom_combo = QComboBox()
        self.order_qty_input = QDoubleSpinBox()
        self.order_qty_input.setRange(0.01, 999999)
        self.order_qty_input.setDecimals(3)
        self.order_qty_input.valueChanged.connect(self._refresh_shortages)
        self.order_labor_input = QDoubleSpinBox()
        self.order_labor_input.setRange(0, 999999)
        self.order_labor_input.setDecimals(2)
        self.order_overhead_input = QDoubleSpinBox()
        self.order_overhead_input.setRange(0, 999999)
        self.order_overhead_input.setDecimals(2)
        self.order_notes_input = QTextEdit()
        self.order_notes_input.setFixedHeight(60)
        self.order_bom_combo.currentIndexChanged.connect(self._refresh_shortages)
        self.order_product_combo.currentIndexChanged.connect(self._refresh_bom_combo)
        form_layout.addRow("Order No (رقم الأمر):", self.order_no_label)
        form_layout.addRow("Product (المنتج):", self.order_product_combo)
        form_layout.addRow("BOM (الوصفة):", self.order_bom_combo)
        form_layout.addRow("Qty To Produce (الكمية):", self.order_qty_input)
        form_layout.addRow("Labor Cost (تكلفة العمالة):", self.order_labor_input)
        form_layout.addRow("Overhead Cost (تكلفة إضافية):", self.order_overhead_input)
        form_layout.addRow("Notes (ملاحظات):", self.order_notes_input)
        layout.addWidget(form_box)

        self.shortage_label = QLabel("")
        layout.addWidget(self.shortage_label)

        action_row = QHBoxLayout()
        self.order_create_btn = QPushButton("Create Draft (إنشاء مسودة)")
        self.order_confirm_btn = QPushButton("Confirm (تأكيد)")
        self.order_done_btn = QPushButton("Mark Done (إنهاء)")
        self.order_create_btn.clicked.connect(self._create_order)
        self.order_confirm_btn.clicked.connect(self._confirm_order)
        self.order_done_btn.clicked.connect(self._mark_done)
        action_row.addWidget(self.order_create_btn)
        action_row.addWidget(self.order_confirm_btn)
        action_row.addWidget(self.order_done_btn)
        layout.addLayout(action_row)

        self.orders_table = QTableWidget(0, 7)
        self.orders_table.setHorizontalHeaderLabels(
            ["Order No", "Date", "Status", "Product", "Qty", "Produced", "Costs"]
        )
        self.orders_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.orders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.orders_table.setAlternatingRowColors(True)
        self.orders_table.cellClicked.connect(self._load_order)
        layout.addWidget(self.orders_table)

        self.tabs.addTab(self.orders_tab, "Production Orders (أوامر الإنتاج)")

        self._selected_order_id: Optional[int] = None

    def _build_reports_tab(self) -> None:
        self.reports_tab = QWidget()
        layout = QVBoxLayout(self.reports_tab)

        history_box = QGroupBox("Production History (سجل الإنتاج)")
        history_layout = QVBoxLayout(history_box)
        filter_row = QHBoxLayout()
        self.history_start = QDateEdit()
        self.history_start.setCalendarPopup(True)
        self.history_end = QDateEdit()
        self.history_end.setCalendarPopup(True)
        today = QDate.currentDate()
        self.history_start.setDate(today.addDays(-30))
        self.history_end.setDate(today)
        self.history_status = QComboBox()
        self.history_status.addItems(["all", "draft", "confirmed", "done", "cancelled"])
        self.history_product = QComboBox()
        self.history_refresh_btn = QPushButton("Refresh (تحديث)")
        self.history_refresh_btn.clicked.connect(self._refresh_history_report)
        filter_row.addWidget(QLabel("From:"))
        filter_row.addWidget(self.history_start)
        filter_row.addWidget(QLabel("To:"))
        filter_row.addWidget(self.history_end)
        filter_row.addWidget(QLabel("Status:"))
        filter_row.addWidget(self.history_status)
        filter_row.addWidget(QLabel("Product:"))
        filter_row.addWidget(self.history_product)
        filter_row.addWidget(self.history_refresh_btn)
        history_layout.addLayout(filter_row)

        self.history_table = QTableWidget(0, 7)
        self.history_table.setHorizontalHeaderLabels(
            ["Order No", "Date", "Status", "Product", "Qty", "Produced", "Total Cost"]
        )
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        history_layout.addWidget(self.history_table)
        layout.addWidget(history_box)

        usage_box = QGroupBox("Material Usage (استهلاك الخامات)")
        usage_layout = QVBoxLayout(usage_box)
        usage_filter = QHBoxLayout()
        self.usage_start = QDateEdit()
        self.usage_start.setCalendarPopup(True)
        self.usage_end = QDateEdit()
        self.usage_end.setCalendarPopup(True)
        self.usage_start.setDate(today.addDays(-30))
        self.usage_end.setDate(today)
        self.usage_refresh_btn = QPushButton("Refresh (تحديث)")
        self.usage_refresh_btn.clicked.connect(self._refresh_usage_report)
        usage_filter.addWidget(QLabel("From:"))
        usage_filter.addWidget(self.usage_start)
        usage_filter.addWidget(QLabel("To:"))
        usage_filter.addWidget(self.usage_end)
        usage_filter.addWidget(self.usage_refresh_btn)
        usage_layout.addLayout(usage_filter)

        self.usage_table = QTableWidget(0, 3)
        self.usage_table.setHorizontalHeaderLabels(["Material", "Total Qty", "Total Cost"])
        self.usage_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.usage_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.usage_table.setAlternatingRowColors(True)
        usage_layout.addWidget(self.usage_table)
        layout.addWidget(usage_box)

        self.tabs.addTab(self.reports_tab, "Manufacturing Reports (تقارير)")

    def _refresh_materials(self) -> None:
        materials = list_materials()
        self.materials_table.setRowCount(0)
        self._material_map = {}
        for material in materials:
            row = self.materials_table.rowCount()
            self.materials_table.insertRow(row)
            self.materials_table.setItem(row, 0, QTableWidgetItem(material.name_ar))
            self.materials_table.setItem(row, 1, QTableWidgetItem(material.name_en))
            self.materials_table.setItem(row, 2, QTableWidgetItem(material.code))
            self.materials_table.setItem(row, 3, QTableWidgetItem(f"{material.qty_on_hand:.3f}"))
            self.materials_table.setItem(row, 4, QTableWidgetItem(material.unit))
            self.materials_table.setItem(row, 5, QTableWidgetItem(f"{material.min_qty:.3f}"))
            self.materials_table.setItem(row, 6, QTableWidgetItem(f"{material.cost_per_unit:.2f}"))
            self.materials_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, material.id)
            display = f"{material.name_en} ({material.code})"
            self._material_map[display] = material.id

        self.bom_material_combo.clear()
        for label in self._material_map:
            self.bom_material_combo.addItem(label, self._material_map[label])

    def _refresh_products(self) -> None:
        products = list_products()
        self._product_map = {
            f"{p.name_en} ({p.sku})": p.id for p in products
        }
        self.bom_product_combo.clear()
        self.order_product_combo.clear()
        self.history_product.clear()
        for label, product_id in self._product_map.items():
            self.bom_product_combo.addItem(label, product_id)
            self.order_product_combo.addItem(label, product_id)
        self.history_product.addItem("All", None)
        for label, product_id in self._product_map.items():
            self.history_product.addItem(label, product_id)
        self._refresh_bom_combo()

    def _refresh_boms(self) -> None:
        boms = list_boms()
        self._bom_entries = []
        self.boms_table.setRowCount(0)
        for bom in boms:
            product_name = next(
                (label for label, pid in self._product_map.items() if pid == bom.product_id),
                f"Product {bom.product_id}",
            )
            row = self.boms_table.rowCount()
            self.boms_table.insertRow(row)
            self.boms_table.setItem(row, 0, QTableWidgetItem(product_name))
            self.boms_table.setItem(row, 1, QTableWidgetItem(bom.name))
            self.boms_table.setItem(row, 2, QTableWidgetItem("Yes" if bom.active else "No"))
            self.boms_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, bom.id)
            display = f"{product_name} - {bom.name}"
            self._bom_entries.append((display, bom.id, bom.product_id))

        self._refresh_bom_combo()

    def _refresh_bom_combo(self) -> None:
        self.order_bom_combo.clear()
        self.order_bom_combo.addItem("Select BOM", None)
        selected_product_id = self.order_product_combo.currentData()
        for label, bom_id, product_id in self._bom_entries:
            if selected_product_id and product_id != selected_product_id:
                continue
            self.order_bom_combo.addItem(label, bom_id)

    def _refresh_orders(self) -> None:
        orders = list_production_orders()
        self.orders_table.setRowCount(0)
        for order in orders:
            product_label = next(
                (label for label, pid in self._product_map.items() if pid == order.product_id),
                f"Product {order.product_id}",
            )
            row = self.orders_table.rowCount()
            self.orders_table.insertRow(row)
            self.orders_table.setItem(row, 0, QTableWidgetItem(order.order_no))
            self.orders_table.setItem(row, 1, QTableWidgetItem(order.datetime))
            self.orders_table.setItem(row, 2, QTableWidgetItem(order.status))
            self.orders_table.setItem(row, 3, QTableWidgetItem(product_label))
            self.orders_table.setItem(row, 4, QTableWidgetItem(f"{order.qty_to_produce:.3f}"))
            self.orders_table.setItem(row, 5, QTableWidgetItem(f"{order.qty_produced:.3f}"))
            cost_total = order.labor_cost + order.overhead_cost
            self.orders_table.setItem(row, 6, QTableWidgetItem(f"{cost_total:.2f}"))
            self.orders_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, order.id)

    def _save_material(self) -> None:
        if not self.material_name_en.text().strip():
            QMessageBox.warning(self, "Missing", "Material English name required.")
            return
        if not self.material_code.text().strip():
            QMessageBox.warning(self, "Missing", "Material code required.")
            return
        save_material(
            self._selected_material_id,
            self.material_name_ar.text().strip(),
            self.material_name_en.text().strip(),
            self.material_code.text().strip(),
            float(self.material_qty.value()),
            self.material_unit.text().strip(),
            float(self.material_min_qty.value()),
            float(self.material_cost.value()),
        )
        QMessageBox.information(self, "Saved", "Material saved.")
        self._refresh_materials()
        self._clear_material_form()

    def _delete_material(self) -> None:
        if not self._selected_material_id:
            return
        confirm = QMessageBox.question(self, "Delete", "Delete this material?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_material(self._selected_material_id)
        self._refresh_materials()
        self._clear_material_form()

    def _clear_material_form(self) -> None:
        self._selected_material_id = None
        self.material_name_ar.clear()
        self.material_name_en.clear()
        self.material_code.clear()
        self.material_qty.setValue(0)
        self.material_unit.clear()
        self.material_min_qty.setValue(0)
        self.material_cost.setValue(0)

    def _load_material(self, row: int) -> None:
        self._selected_material_id = self.materials_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.material_name_ar.setText(self.materials_table.item(row, 0).text())
        self.material_name_en.setText(self.materials_table.item(row, 1).text())
        self.material_code.setText(self.materials_table.item(row, 2).text())
        self.material_qty.setValue(float(self.materials_table.item(row, 3).text()))
        self.material_unit.setText(self.materials_table.item(row, 4).text())
        self.material_min_qty.setValue(float(self.materials_table.item(row, 5).text()))
        self.material_cost.setValue(float(self.materials_table.item(row, 6).text()))

    def _add_bom_line(self) -> None:
        material_id = self.bom_material_combo.currentData()
        if not material_id:
            return
        qty_required = float(self.bom_qty_input.value())
        row = self.bom_lines_table.rowCount()
        self.bom_lines_table.insertRow(row)
        self.bom_lines_table.setItem(row, 0, QTableWidgetItem(self.bom_material_combo.currentText()))
        self.bom_lines_table.setItem(row, 1, QTableWidgetItem(f"{qty_required:.3f}"))
        self.bom_lines_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, material_id)

    def _remove_bom_line(self) -> None:
        row = self.bom_lines_table.currentRow()
        if row >= 0:
            self.bom_lines_table.removeRow(row)

    def _save_bom(self) -> None:
        product_id = self.bom_product_combo.currentData()
        if not product_id:
            QMessageBox.warning(self, "Missing", "Select a product.")
            return
        if not self.bom_name_input.text().strip():
            QMessageBox.warning(self, "Missing", "BOM name required.")
            return
        lines = []
        for row in range(self.bom_lines_table.rowCount()):
            material_id = self.bom_lines_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            qty_required = float(self.bom_lines_table.item(row, 1).text())
            lines.append((material_id, qty_required))
        if not lines:
            QMessageBox.warning(self, "Missing", "Add at least one material line.")
            return
        save_bom(
            self._selected_bom_id,
            product_id,
            self.bom_name_input.text().strip(),
            self.bom_active_check.isChecked(),
            lines,
        )
        QMessageBox.information(self, "Saved", "BOM saved.")
        self._refresh_boms()
        self._clear_bom_form()

    def _delete_bom(self) -> None:
        if not self._selected_bom_id:
            return
        confirm = QMessageBox.question(self, "Delete", "Delete this BOM?")
        if confirm != QMessageBox.StandardButton.Yes:
            return
        delete_bom(self._selected_bom_id)
        self._refresh_boms()
        self._clear_bom_form()

    def _clear_bom_form(self) -> None:
        self._selected_bom_id = None
        self.bom_product_combo.setCurrentIndex(0)
        self.bom_name_input.clear()
        self.bom_active_check.setChecked(False)
        self.bom_lines_table.setRowCount(0)

    def _load_bom(self, row: int) -> None:
        self._selected_bom_id = self.boms_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        bom = next((b for b in list_boms() if b.id == self._selected_bom_id), None)
        if not bom:
            return
        product_index = self.bom_product_combo.findData(bom.product_id)
        if product_index >= 0:
            self.bom_product_combo.setCurrentIndex(product_index)
        self.bom_name_input.setText(bom.name)
        self.bom_active_check.setChecked(bom.active)
        self.bom_lines_table.setRowCount(0)
        for line in list_bom_lines(bom.id):
            material_label = next(
                (label for label, mid in self._material_map.items() if mid == line.material_id),
                f"Material {line.material_id}",
            )
            row_idx = self.bom_lines_table.rowCount()
            self.bom_lines_table.insertRow(row_idx)
            self.bom_lines_table.setItem(row_idx, 0, QTableWidgetItem(material_label))
            self.bom_lines_table.setItem(row_idx, 1, QTableWidgetItem(f"{line.qty_required:.3f}"))
            self.bom_lines_table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, line.material_id)

    def _create_order(self) -> None:
        product_id = self.order_product_combo.currentData()
        bom_id = self.order_bom_combo.currentData()
        if not product_id:
            QMessageBox.warning(self, "Missing", "Select a product.")
            return
        if not bom_id:
            QMessageBox.warning(self, "Missing", "Select a BOM.")
            return
        if float(self.order_qty_input.value()) <= 0:
            QMessageBox.warning(self, "Missing", "Enter quantity to produce.")
            return
        order = create_production_order(
            product_id=product_id,
            qty_to_produce=float(self.order_qty_input.value()),
            labor_cost=float(self.order_labor_input.value()),
            overhead_cost=float(self.order_overhead_input.value()),
            notes=self.order_notes_input.toPlainText().strip(),
            bom_id=bom_id,
        )
        self.order_no_label.setText(order.order_no)
        self._refresh_orders()
        QMessageBox.information(self, "Created", f"Order created: {order.order_no}")

    def _confirm_order(self) -> None:
        if not self._selected_order_id:
            QMessageBox.warning(self, "Select", "Select an order.")
            return
        try:
            confirm_production_order(self._selected_order_id)
        except ValueError:
            QMessageBox.warning(self, "Shortage", "Not enough material stock.")
            return
        self._refresh_orders()
        QMessageBox.information(self, "Confirmed", "Order confirmed.")

    def _mark_done(self) -> None:
        if not self._selected_order_id:
            QMessageBox.warning(self, "Select", "Select an order.")
            return
        try:
            mark_production_done(self._selected_order_id)
        except ValueError:
            QMessageBox.warning(self, "Shortage", "Not enough material stock.")
            return
        self._refresh_orders()
        QMessageBox.information(self, "Done", "Order completed and stock updated.")

    def _load_order(self, row: int) -> None:
        self._selected_order_id = self.orders_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        order = fetch_production_order(self._selected_order_id)
        if not order:
            return
        self.order_no_label.setText(order.order_no)
        product_index = self.order_product_combo.findData(order.product_id)
        if product_index >= 0:
            self.order_product_combo.setCurrentIndex(product_index)
        bom_index = self.order_bom_combo.findData(order.bom_id)
        if bom_index >= 0:
            self.order_bom_combo.setCurrentIndex(bom_index)
        self.order_qty_input.setValue(order.qty_to_produce)
        self.order_labor_input.setValue(order.labor_cost)
        self.order_overhead_input.setValue(order.overhead_cost)
        self.order_notes_input.setPlainText(order.notes)
        self._refresh_shortages()

    def _refresh_shortages(self) -> None:
        bom_id = self.order_bom_combo.currentData()
        qty = float(self.order_qty_input.value())
        if not bom_id or qty <= 0:
            self.shortage_label.setText("")
            return
        shortages = check_material_availability(bom_id, qty)
        if not shortages:
            self.shortage_label.setText("Materials OK ✅")
            return
        details = ", ".join(
            [f"{name} ({available:.2f}/{required:.2f})" for name, available, required in shortages]
        )
        self.shortage_label.setText(f"Shortages: {details}")

    def _refresh_history_report(self) -> None:
        start_dt = datetime.combine(self.history_start.date().toPyDate(), time.min)
        end_dt = datetime.combine(self.history_end.date().toPyDate(), time.max)
        product_id = self.history_product.currentData()
        rows = production_history(
            start_dt.isoformat(timespec="seconds"),
            end_dt.isoformat(timespec="seconds"),
            self.history_status.currentText(),
            product_id,
        )
        self.history_table.setRowCount(0)
        for row_data in rows:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            self.history_table.setItem(row, 0, QTableWidgetItem(row_data.order_no))
            self.history_table.setItem(row, 1, QTableWidgetItem(row_data.datetime))
            self.history_table.setItem(row, 2, QTableWidgetItem(row_data.status))
            self.history_table.setItem(row, 3, QTableWidgetItem(row_data.product_name))
            self.history_table.setItem(row, 4, QTableWidgetItem(f"{row_data.qty_to_produce:.3f}"))
            self.history_table.setItem(row, 5, QTableWidgetItem(f"{row_data.qty_produced:.3f}"))
            self.history_table.setItem(row, 6, QTableWidgetItem(f"{row_data.total_cost:.2f}"))

    def _refresh_usage_report(self) -> None:
        start_dt = datetime.combine(self.usage_start.date().toPyDate(), time.min)
        end_dt = datetime.combine(self.usage_end.date().toPyDate(), time.max)
        rows = material_usage(
            start_dt.isoformat(timespec="seconds"),
            end_dt.isoformat(timespec="seconds"),
        )
        self.usage_table.setRowCount(0)
        for row_data in rows:
            row = self.usage_table.rowCount()
            self.usage_table.insertRow(row)
            self.usage_table.setItem(row, 0, QTableWidgetItem(row_data.material_name))
            self.usage_table.setItem(row, 1, QTableWidgetItem(f"{row_data.total_qty:.3f}"))
            self.usage_table.setItem(row, 2, QTableWidgetItem(f"{row_data.total_cost:.2f}"))
