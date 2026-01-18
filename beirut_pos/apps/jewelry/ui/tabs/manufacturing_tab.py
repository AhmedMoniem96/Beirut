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
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
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
from ...services.i18n import choose_name, get_ui_language, t
from .base_tab import BaseTabContainer


class ManufacturingTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._language = get_ui_language()
        layout = QVBoxLayout(self)
        header = QLabel()
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        self.header_label = header

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
        self.apply_language(self._language)

    def _build_materials_tab(self) -> None:
        self.materials_tab = QWidget()
        tab_layout = QVBoxLayout(self.materials_tab)
        tab_layout.setSpacing(12)

        form_box = QGroupBox()
        form_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.materials_box = form_box
        form_layout = QFormLayout(form_box)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
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
        self.material_name_ar_label = QLabel()
        self.material_name_en_label = QLabel()
        self.material_code_label = QLabel()
        self.material_qty_label = QLabel()
        self.material_unit_label = QLabel()
        self.material_min_qty_label = QLabel()
        self.material_cost_label = QLabel()
        form_layout.addRow(self.material_name_ar_label, self.material_name_ar)
        form_layout.addRow(self.material_name_en_label, self.material_name_en)
        form_layout.addRow(self.material_code_label, self.material_code)
        form_layout.addRow(self.material_qty_label, self.material_qty)
        form_layout.addRow(self.material_unit_label, self.material_unit)
        form_layout.addRow(self.material_min_qty_label, self.material_min_qty)
        form_layout.addRow(self.material_cost_label, self.material_cost)
        self.material_save_btn = QPushButton()
        self.material_delete_btn = QPushButton()
        self.material_clear_btn = QPushButton()
        self.material_save_btn.clicked.connect(self._save_material)
        self.material_delete_btn.clicked.connect(self._delete_material)
        self.material_clear_btn.clicked.connect(self._clear_material_form)

        self.materials_table = QTableWidget(0, 7)
        self.materials_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.materials_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.materials_table.setAlternatingRowColors(True)
        self.materials_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.materials_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.materials_table.cellClicked.connect(self._load_material)
        form_container = BaseTabContainer(show_header=False)
        form_container.content_layout.addWidget(form_box)
        form_container.content_layout.addStretch()
        form_container.footer_layout.addWidget(self.material_save_btn)
        form_container.footer_layout.addWidget(self.material_delete_btn)
        form_container.footer_layout.addWidget(self.material_clear_btn)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(form_container)
        splitter.addWidget(self.materials_table)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        tab_layout.addWidget(splitter)

        self.tabs.addTab(self.materials_tab, "")

        self._selected_material_id: Optional[int] = None

    def _build_boms_tab(self) -> None:
        self.boms_tab = QWidget()
        tab_layout = QVBoxLayout(self.boms_tab)
        tab_layout.setSpacing(12)

        form_box = QGroupBox()
        form_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.bom_box = form_box
        form_layout = QFormLayout(form_box)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.bom_product_combo = QComboBox()
        self.bom_name_input = QLineEdit()
        self.bom_active_check = QCheckBox()
        self.bom_product_label = QLabel()
        self.bom_name_label = QLabel()
        form_layout.addRow(self.bom_product_label, self.bom_product_combo)
        form_layout.addRow(self.bom_name_label, self.bom_name_input)
        form_layout.addRow("", self.bom_active_check)
        lines_box = QGroupBox()
        self.lines_box = lines_box
        lines_layout = QVBoxLayout(lines_box)
        add_line_layout = QHBoxLayout()
        self.bom_material_combo = QComboBox()
        self.bom_qty_input = QDoubleSpinBox()
        self.bom_qty_input.setRange(0.001, 999999)
        self.bom_qty_input.setDecimals(3)
        self.add_bom_line_btn = QPushButton()
        self.add_bom_line_btn.clicked.connect(self._add_bom_line)
        self.bom_material_label = QLabel()
        self.bom_qty_label = QLabel()
        add_line_layout.addWidget(self.bom_material_label)
        add_line_layout.addWidget(self.bom_material_combo)
        add_line_layout.addWidget(self.bom_qty_label)
        add_line_layout.addWidget(self.bom_qty_input)
        add_line_layout.addWidget(self.add_bom_line_btn)
        lines_layout.addLayout(add_line_layout)

        self.bom_lines_table = QTableWidget(0, 2)
        self.bom_lines_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bom_lines_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bom_lines_table.setAlternatingRowColors(True)
        self.bom_lines_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.bom_lines_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lines_layout.addWidget(self.bom_lines_table)

        remove_line_btn = QPushButton()
        remove_line_btn.clicked.connect(self._remove_bom_line)
        lines_layout.addWidget(remove_line_btn)
        self.remove_line_btn = remove_line_btn
        self.bom_save_btn = QPushButton()
        self.bom_delete_btn = QPushButton()
        self.bom_clear_btn = QPushButton()
        self.bom_save_btn.clicked.connect(self._save_bom)
        self.bom_delete_btn.clicked.connect(self._delete_bom)
        self.bom_clear_btn.clicked.connect(self._clear_bom_form)

        self.boms_table = QTableWidget(0, 3)
        self.boms_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.boms_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.boms_table.setAlternatingRowColors(True)
        self.boms_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.boms_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.boms_table.cellClicked.connect(self._load_bom)
        form_container = BaseTabContainer(show_header=False)
        form_container.content_layout.addWidget(form_box)
        form_container.content_layout.addWidget(lines_box)
        form_container.content_layout.addStretch()
        form_container.footer_layout.addWidget(self.bom_save_btn)
        form_container.footer_layout.addWidget(self.bom_delete_btn)
        form_container.footer_layout.addWidget(self.bom_clear_btn)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(form_container)
        splitter.addWidget(self.boms_table)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        tab_layout.addWidget(splitter)

        self.tabs.addTab(self.boms_tab, "")

        self._selected_bom_id: Optional[int] = None

    def _build_orders_tab(self) -> None:
        self.orders_tab = QWidget()
        tab_layout = QVBoxLayout(self.orders_tab)
        tab_layout.setSpacing(12)

        form_box = QGroupBox()
        form_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.orders_box = form_box
        form_layout = QFormLayout(form_box)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.order_no_label = QLabel("")
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
        self.order_notes_input.setMinimumHeight(90)
        self.order_notes_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.order_bom_combo.currentIndexChanged.connect(self._refresh_shortages)
        self.order_product_combo.currentIndexChanged.connect(self._refresh_bom_combo)
        self.order_no_text = QLabel()
        self.order_product_label = QLabel()
        self.order_bom_label = QLabel()
        self.order_qty_label = QLabel()
        self.order_labor_label = QLabel()
        self.order_overhead_label = QLabel()
        self.order_notes_label = QLabel()
        form_layout.addRow(self.order_no_text, self.order_no_label)
        form_layout.addRow(self.order_product_label, self.order_product_combo)
        form_layout.addRow(self.order_bom_label, self.order_bom_combo)
        form_layout.addRow(self.order_qty_label, self.order_qty_input)
        form_layout.addRow(self.order_labor_label, self.order_labor_input)
        form_layout.addRow(self.order_overhead_label, self.order_overhead_input)
        form_layout.addRow(self.order_notes_label, self.order_notes_input)

        self.order_create_btn = QPushButton()
        self.order_confirm_btn = QPushButton()
        self.order_done_btn = QPushButton()
        self.order_create_btn.clicked.connect(self._create_order)
        self.order_confirm_btn.clicked.connect(self._confirm_order)
        self.order_done_btn.clicked.connect(self._mark_done)

        self.orders_table = QTableWidget(0, 7)
        self.orders_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.orders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.orders_table.setAlternatingRowColors(True)
        self.orders_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.orders_table.cellClicked.connect(self._load_order)
        self.shortage_label = QLabel("")
        form_container = BaseTabContainer(show_header=False)
        form_container.content_layout.addWidget(form_box)
        form_container.content_layout.addWidget(self.shortage_label)
        form_container.content_layout.addStretch()
        form_container.footer_layout.addWidget(self.order_create_btn)
        form_container.footer_layout.addWidget(self.order_confirm_btn)
        form_container.footer_layout.addWidget(self.order_done_btn)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(form_container)
        splitter.addWidget(self.orders_table)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        tab_layout.addWidget(splitter)

        self.tabs.addTab(self.orders_tab, "")

        self._selected_order_id: Optional[int] = None

    def _build_reports_tab(self) -> None:
        self.reports_tab = QWidget()
        tab_layout = QVBoxLayout(self.reports_tab)
        tab_layout.setSpacing(12)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        tab_layout.addWidget(scroll_area)
        content = QWidget()
        scroll_area.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setSpacing(12)

        history_box = QGroupBox()
        self.history_box = history_box
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
        self.history_refresh_btn = QPushButton()
        self.history_refresh_btn.clicked.connect(self._refresh_history_report)
        self.history_from_label = QLabel()
        filter_row.addWidget(self.history_from_label)
        filter_row.addWidget(self.history_start)
        self.history_to_label = QLabel()
        filter_row.addWidget(self.history_to_label)
        filter_row.addWidget(self.history_end)
        self.history_status_label = QLabel()
        filter_row.addWidget(self.history_status_label)
        filter_row.addWidget(self.history_status)
        self.history_product_label = QLabel()
        filter_row.addWidget(self.history_product_label)
        filter_row.addWidget(self.history_product)
        filter_row.addWidget(self.history_refresh_btn)
        history_layout.addLayout(filter_row)

        self.history_table = QTableWidget(0, 7)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        history_layout.addWidget(self.history_table)

        usage_box = QGroupBox()
        self.usage_box = usage_box
        usage_layout = QVBoxLayout(usage_box)
        usage_filter = QHBoxLayout()
        self.usage_start = QDateEdit()
        self.usage_start.setCalendarPopup(True)
        self.usage_end = QDateEdit()
        self.usage_end.setCalendarPopup(True)
        self.usage_start.setDate(today.addDays(-30))
        self.usage_end.setDate(today)
        self.usage_refresh_btn = QPushButton()
        self.usage_refresh_btn.clicked.connect(self._refresh_usage_report)
        self.usage_from_label = QLabel()
        usage_filter.addWidget(self.usage_from_label)
        usage_filter.addWidget(self.usage_start)
        self.usage_to_label = QLabel()
        usage_filter.addWidget(self.usage_to_label)
        usage_filter.addWidget(self.usage_end)
        usage_filter.addWidget(self.usage_refresh_btn)
        usage_layout.addLayout(usage_filter)

        self.usage_table = QTableWidget(0, 3)
        self.usage_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.usage_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.usage_table.setAlternatingRowColors(True)
        self.usage_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.usage_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        usage_layout.addWidget(self.usage_table)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(history_box)
        splitter.addWidget(usage_box)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self.tabs.addTab(self.reports_tab, "")

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
            display = f"{choose_name(material.name_ar, material.name_en, language=self._language)} ({material.code})"
            self._material_map[display] = material.id

        self.bom_material_combo.clear()
        for label in self._material_map:
            self.bom_material_combo.addItem(label, self._material_map[label])

    def _refresh_products(self) -> None:
        products = list_products()
        self._product_map = {
            f"{choose_name(p.name_ar, p.name_en, language=self._language)} ({p.sku})": p.id for p in products
            for p in products
        }
        self.bom_product_combo.clear()
        self.order_product_combo.clear()
        self.history_product.clear()
        for label, product_id in self._product_map.items():
            self.bom_product_combo.addItem(label, product_id)
            self.order_product_combo.addItem(label, product_id)
        self.history_product.addItem(t("manufacturing.status_all", language=self._language), None)
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
                f"{t('common.product', language=self._language)} {bom.product_id}",
            )
            row = self.boms_table.rowCount()
            self.boms_table.insertRow(row)
            self.boms_table.setItem(row, 0, QTableWidgetItem(product_name))
            self.boms_table.setItem(row, 1, QTableWidgetItem(bom.name))
            self.boms_table.setItem(
                row,
                2,
                QTableWidgetItem(
                    t("common.yes", language=self._language)
                    if bom.active
                    else t("common.no", language=self._language)
                ),
            )
            self.boms_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, bom.id)
            display = f"{product_name} - {bom.name}"
            self._bom_entries.append((display, bom.id, bom.product_id))

        self._refresh_bom_combo()

    def _refresh_bom_combo(self) -> None:
        self.order_bom_combo.clear()
        self.order_bom_combo.addItem(t("manufacturing.select_bom_label", language=self._language), None)
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
                f"{t('common.product', language=self._language)} {order.product_id}",
            )
            row = self.orders_table.rowCount()
            self.orders_table.insertRow(row)
            self.orders_table.setItem(row, 0, QTableWidgetItem(order.order_no))
            self.orders_table.setItem(row, 1, QTableWidgetItem(order.datetime))
            self.orders_table.setItem(row, 2, QTableWidgetItem(self._status_label(order.status)))
            self.orders_table.setItem(row, 3, QTableWidgetItem(product_label))
            self.orders_table.setItem(row, 4, QTableWidgetItem(f"{order.qty_to_produce:.3f}"))
            self.orders_table.setItem(row, 5, QTableWidgetItem(f"{order.qty_produced:.3f}"))
            cost_total = order.labor_cost + order.overhead_cost
            self.orders_table.setItem(row, 6, QTableWidgetItem(f"{cost_total:.2f}"))
            self.orders_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, order.id)

    def _save_material(self) -> None:
        if not self.material_name_en.text().strip():
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.material_name_required", language=self._language),
            )
            return
        if not self.material_code.text().strip():
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.material_code_required", language=self._language),
            )
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
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("manufacturing.material_saved", language=self._language),
        )
        self._refresh_materials()
        self._clear_material_form()

    def _delete_material(self) -> None:
        if not self._selected_material_id:
            return
        confirm = QMessageBox.question(
            self,
            t("common.delete", language=self._language),
            t("manufacturing.delete_material", language=self._language),
        )
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
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.select_product", language=self._language),
            )
            return
        if not self.bom_name_input.text().strip():
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.bom_name_required", language=self._language),
            )
            return
        lines = []
        for row in range(self.bom_lines_table.rowCount()):
            material_id = self.bom_lines_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            qty_required = float(self.bom_lines_table.item(row, 1).text())
            lines.append((material_id, qty_required))
        if not lines:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.add_material_line", language=self._language),
            )
            return
        save_bom(
            self._selected_bom_id,
            product_id,
            self.bom_name_input.text().strip(),
            self.bom_active_check.isChecked(),
            lines,
        )
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("manufacturing.bom_saved", language=self._language),
        )
        self._refresh_boms()
        self._clear_bom_form()

    def _delete_bom(self) -> None:
        if not self._selected_bom_id:
            return
        confirm = QMessageBox.question(
            self,
            t("common.delete", language=self._language),
            t("manufacturing.delete_bom", language=self._language),
        )
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
                f"{t('manufacturing.material_label', language=self._language)} {line.material_id}",
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
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.select_product", language=self._language),
            )
            return
        if not bom_id:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.select_bom", language=self._language),
            )
            return
        if float(self.order_qty_input.value()) <= 0:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.enter_qty", language=self._language),
            )
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
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("manufacturing.order_created", language=self._language, order_no=order.order_no),
        )

    def _confirm_order(self) -> None:
        if not self._selected_order_id:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.select_order", language=self._language),
            )
            return
        try:
            confirm_production_order(self._selected_order_id)
        except ValueError:
            QMessageBox.warning(
                self,
                t("manufacturing.shortage", language=self._language),
                t("manufacturing.shortage_message", language=self._language),
            )
            return
        self._refresh_orders()
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("manufacturing.order_confirmed", language=self._language),
        )

    def _mark_done(self) -> None:
        if not self._selected_order_id:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.select_order", language=self._language),
            )
            return
        try:
            mark_production_done(self._selected_order_id)
        except ValueError:
            QMessageBox.warning(
                self,
                t("manufacturing.shortage", language=self._language),
                t("manufacturing.shortage_message", language=self._language),
            )
            return
        self._refresh_orders()
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("manufacturing.order_done", language=self._language),
        )

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
            self.shortage_label.setText(t("manufacturing.materials_ok", language=self._language))
            return
        details = ", ".join(
            [f"{name} ({available:.2f}/{required:.2f})" for name, available, required in shortages]
        )
        self.shortage_label.setText(
            t("manufacturing.shortages_label", language=self._language, details=details)
        )

    def _refresh_history_report(self) -> None:
        start_dt = datetime.combine(self.history_start.date().toPyDate(), time.min)
        end_dt = datetime.combine(self.history_end.date().toPyDate(), time.max)
        product_id = self.history_product.currentData()
        status_value = self.history_status.currentData() or "all"
        rows = production_history(
            start_dt.isoformat(timespec="seconds"),
            end_dt.isoformat(timespec="seconds"),
            status_value,
            product_id,
        )
        self.history_table.setRowCount(0)
        for row_data in rows:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)
            self.history_table.setItem(row, 0, QTableWidgetItem(row_data.order_no))
            self.history_table.setItem(row, 1, QTableWidgetItem(row_data.datetime))
            self.history_table.setItem(row, 2, QTableWidgetItem(self._status_label(row_data.status)))
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

    def _status_label(self, status: str) -> str:
        mapping = {
            "draft": t("manufacturing.status_draft", language=self._language),
            "confirmed": t("manufacturing.status_confirmed", language=self._language),
            "done": t("manufacturing.status_done", language=self._language),
            "cancelled": t("manufacturing.status_cancelled", language=self._language),
            "all": t("manufacturing.status_all", language=self._language),
        }
        return mapping.get(status, status)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("manufacturing.header", language=language))
        self.tabs.setTabText(0, t("manufacturing.tab.materials", language=language))
        self.tabs.setTabText(1, t("manufacturing.tab.boms", language=language))
        self.tabs.setTabText(2, t("manufacturing.tab.orders", language=language))
        self.tabs.setTabText(3, t("manufacturing.tab.reports", language=language))
        self.materials_box.setTitle(t("manufacturing.materials_box", language=language))
        self.material_name_ar_label.setText(t("manufacturing.material_name_ar", language=language))
        self.material_name_en_label.setText(t("manufacturing.material_name_en", language=language))
        self.material_code_label.setText(t("manufacturing.material_code", language=language))
        self.material_qty_label.setText(t("manufacturing.material_qty", language=language))
        self.material_unit_label.setText(t("manufacturing.material_unit", language=language))
        self.material_min_qty_label.setText(t("manufacturing.material_min_qty", language=language))
        self.material_cost_label.setText(t("manufacturing.material_cost", language=language))
        self.material_save_btn.setText(t("manufacturing.save_material", language=language))
        self.material_delete_btn.setText(t("manufacturing.delete", language=language))
        self.material_clear_btn.setText(t("manufacturing.clear", language=language))
        self.materials_table.setHorizontalHeaderLabels(
            [
                t("manufacturing.table_arabic", language=language),
                t("manufacturing.table_english", language=language),
                t("manufacturing.table_code", language=language),
                t("manufacturing.table_qty", language=language),
                t("manufacturing.table_unit", language=language),
                t("manufacturing.table_min", language=language),
                t("manufacturing.table_cost", language=language),
            ]
        )
        self.bom_box.setTitle(t("manufacturing.bom_box", language=language))
        self.bom_product_label.setText(t("manufacturing.bom_product", language=language))
        self.bom_name_label.setText(t("manufacturing.bom_name", language=language))
        self.bom_active_check.setText(t("manufacturing.bom_active", language=language))
        self.lines_box.setTitle(t("manufacturing.lines_box", language=language))
        self.bom_material_label.setText(t("manufacturing.material_label", language=language))
        self.bom_qty_label.setText(t("manufacturing.qty_required", language=language))
        self.add_bom_line_btn.setText(t("manufacturing.add_line", language=language))
        self.bom_lines_table.setHorizontalHeaderLabels(
            [
                t("manufacturing.material_label", language=language),
                t("manufacturing.qty_required", language=language),
            ]
        )
        self.remove_line_btn.setText(t("manufacturing.remove_line", language=language))
        self.bom_save_btn.setText(t("manufacturing.save_bom", language=language))
        self.bom_delete_btn.setText(t("manufacturing.delete_bom", language=language))
        self.bom_clear_btn.setText(t("manufacturing.clear", language=language))
        self.boms_table.setHorizontalHeaderLabels(
            [
                t("manufacturing.bom_table_product", language=language),
                t("manufacturing.bom_table_name", language=language),
                t("manufacturing.bom_table_active", language=language),
            ]
        )
        self.orders_box.setTitle(t("manufacturing.orders_box", language=language))
        self.order_no_text.setText(t("manufacturing.order_no", language=language))
        if not self.order_no_label.text().strip():
            self.order_no_label.setText(t("common.auto", language=language))
        self.order_product_label.setText(t("manufacturing.order_product", language=language))
        self.order_bom_label.setText(t("manufacturing.order_bom", language=language))
        self.order_qty_label.setText(t("manufacturing.order_qty", language=language))
        self.order_labor_label.setText(t("manufacturing.order_labor", language=language))
        self.order_overhead_label.setText(t("manufacturing.order_overhead", language=language))
        self.order_notes_label.setText(t("manufacturing.order_notes", language=language))
        self.order_create_btn.setText(t("manufacturing.create_draft", language=language))
        self.order_confirm_btn.setText(t("manufacturing.confirm", language=language))
        self.order_done_btn.setText(t("manufacturing.mark_done", language=language))
        self.orders_table.setHorizontalHeaderLabels(
            [
                t("manufacturing.orders_table_order", language=language),
                t("manufacturing.orders_table_date", language=language),
                t("manufacturing.orders_table_status", language=language),
                t("manufacturing.orders_table_product", language=language),
                t("manufacturing.orders_table_qty", language=language),
                t("manufacturing.orders_table_produced", language=language),
                t("manufacturing.orders_table_costs", language=language),
            ]
        )
        self.history_box.setTitle(t("manufacturing.history_box", language=language))
        self.history_from_label.setText(f"{t('common.from', language=language)}:")
        self.history_to_label.setText(f"{t('common.to', language=language)}:")
        self.history_status_label.setText(f"{t('manufacturing.history_status', language=language)}:")
        self.history_product_label.setText(f"{t('manufacturing.history_product', language=language)}:")
        self.history_refresh_btn.setText(t("manufacturing.history_refresh", language=language))
        self.history_table.setHorizontalHeaderLabels(
            [
                t("manufacturing.history_table_order", language=language),
                t("manufacturing.history_table_date", language=language),
                t("manufacturing.history_table_status", language=language),
                t("manufacturing.history_table_product", language=language),
                t("manufacturing.history_table_qty", language=language),
                t("manufacturing.history_table_produced", language=language),
                t("manufacturing.history_table_total_cost", language=language),
            ]
        )
        self.usage_box.setTitle(t("manufacturing.usage_box", language=language))
        self.usage_from_label.setText(f"{t('common.from', language=language)}:")
        self.usage_to_label.setText(f"{t('common.to', language=language)}:")
        self.usage_refresh_btn.setText(t("manufacturing.history_refresh", language=language))
        self.usage_table.setHorizontalHeaderLabels(
            [
                t("manufacturing.usage_table_material", language=language),
                t("manufacturing.usage_table_qty", language=language),
                t("manufacturing.usage_table_cost", language=language),
            ]
        )
        self.history_status.blockSignals(True)
        self.history_status.clear()
        for status in ["all", "draft", "confirmed", "done", "cancelled"]:
            self.history_status.addItem(self._status_label(status), status)
        self.history_status.blockSignals(False)
        self._refresh_materials()
        self._refresh_products()
        self._refresh_boms()
        self._refresh_orders()
