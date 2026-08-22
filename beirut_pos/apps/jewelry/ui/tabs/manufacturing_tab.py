"""Manufacturing tab for Jewelry app."""

from __future__ import annotations

from datetime import datetime, time
from typing import Dict, List, Optional

import re

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QInputDialog,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...services.db import (
    delete_bom,
    delete_material,
    list_bom_lines,
    list_boms,
    list_materials,
    list_products,
    list_production_consumption,
    list_production_orders,
    produce_from_bom,
    save_product_design,
    save_material,
)
from ...services.reports import production_history
from ...services.i18n import choose_name, get_ui_language, t
from .base_tab import BaseTabContainer


class ManufacturingTab(BaseTabContainer):
    inventory_changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._language = get_ui_language()
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)
        self.set_page_content_widget(content)

        self.tabs = QTabWidget()
        content_layout.addWidget(self.tabs, 1)

        self._material_map: Dict[str, int] = {}
        self._product_map: Dict[str, int] = {}
        self._bom_entries: List[tuple[str, int, int]] = []
        self._editing_product_id: Optional[int] = None

        self._build_design_tab()
        self._build_materials_tab()
        self._build_history_tab()

        self._refresh_materials()
        self._refresh_design_products()
        self._refresh_history_products()
        self._refresh_boms()
        self._disable_spinbox_arrows()
        self.apply_language(self._language)

    def on_activated(self) -> None:
        """Reload manufacturing data changed elsewhere without rebuilding the tab."""
        self._refresh_materials()
        self._refresh_design_products()
        self._refresh_history_products()
        self._refresh_boms()
        self._refresh_history_report()
        self._refresh_design_cost_summary()


    def _disable_spinbox_arrows(self) -> None:
        for widget_name in (
            "material_qty",
            "material_min_qty",
            "material_cost",
            "design_product_price",
            "design_labor_cost",
            "design_packaging_cost",
            "design_other_cost",
            "design_profit_pct",
            "bom_qty_input",
            "produced_qty_input",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

    def _build_materials_tab(self) -> None:
        self.materials_tab = QWidget()
        tab_layout = QVBoxLayout(self.materials_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(8)

        form_box = QGroupBox()
        form_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.materials_box = form_box
        form_layout = QGridLayout(form_box)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(8)
        for column in range(3):
            form_layout.setColumnStretch(column, 1)

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

        form_fields = [
            (self.material_name_ar_label, self.material_name_ar),
            (self.material_name_en_label, self.material_name_en),
            (self.material_code_label, self.material_code),
            (self.material_qty_label, self.material_qty),
            (self.material_unit_label, self.material_unit),
            (self.material_cost_label, self.material_cost),
            (self.material_min_qty_label, self.material_min_qty),
        ]
        for index, (label, widget) in enumerate(form_fields):
            row = (index // 3) * 2
            column = index % 3
            form_layout.addWidget(label, row, column)
            form_layout.addWidget(widget, row + 1, column)

        self.material_save_btn = QPushButton()
        self.material_delete_btn = QPushButton()
        self.material_clear_btn = QPushButton()
        self.material_adjust_stock_btn = QPushButton()
        self.material_edit_indicator = QLabel()
        self.material_save_btn.clicked.connect(self._save_material)
        self.material_delete_btn.clicked.connect(self._delete_material)
        self.material_clear_btn.clicked.connect(self._clear_material_form)
        self.material_adjust_stock_btn.clicked.connect(self._adjust_material_stock)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        actions_row.addWidget(self.material_clear_btn)
        actions_row.addWidget(self.material_save_btn)
        actions_row.addWidget(self.material_adjust_stock_btn)
        actions_row.addWidget(self.material_delete_btn)
        actions_row.addStretch(1)

        self.materials_table = QTableWidget(0, 7)
        self.materials_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.materials_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.materials_table.setAlternatingRowColors(True)
        self.materials_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.materials_table.verticalHeader().setVisible(False)
        header = self.materials_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.materials_table.cellClicked.connect(self._load_material)

        form_and_actions = QWidget()
        form_and_actions_layout = QVBoxLayout(form_and_actions)
        form_and_actions_layout.setContentsMargins(0, 0, 0, 0)
        form_and_actions_layout.setSpacing(8)
        form_and_actions_layout.addWidget(form_box)
        form_and_actions_layout.addWidget(self.material_edit_indicator)
        form_and_actions_layout.addLayout(actions_row)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(form_and_actions)
        splitter.addWidget(self.materials_table)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        tab_layout.addWidget(splitter)

        self.tabs.addTab(self.materials_tab, "")

        self._selected_material_id: Optional[int] = None
        self._editing_material_id: Optional[int] = None

    def _build_design_tab(self) -> None:
        self.boms_tab = QWidget()
        tab_layout = QVBoxLayout(self.boms_tab)
        tab_layout.setSpacing(8)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        mode_layout = QHBoxLayout()
        self.new_design_btn = QPushButton()
        self.edit_design_btn = QPushButton()
        self.new_design_btn.setCheckable(True)
        self.edit_design_btn.setCheckable(True)
        self.new_design_btn.clicked.connect(self._start_new_design)
        self.edit_design_btn.clicked.connect(self._show_design_picker)
        mode_layout.addWidget(self.new_design_btn)
        mode_layout.addWidget(self.edit_design_btn)
        mode_layout.addStretch(1)
        tab_layout.addLayout(mode_layout)

        self.design_picker = QWidget()
        picker_layout = QVBoxLayout(self.design_picker)
        picker_layout.setContentsMargins(0, 0, 0, 0)
        self.design_search_input = QLineEdit()
        self.design_search_results = QListWidget()
        self.design_search_results.setMaximumHeight(160)
        self.design_search_input.textChanged.connect(self._populate_design_picker)
        self.design_search_results.itemClicked.connect(self._load_picker_design)
        picker_layout.addWidget(self.design_search_input)
        picker_layout.addWidget(self.design_search_results)
        self.design_picker.setVisible(False)
        tab_layout.addWidget(self.design_picker)

        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)

        left_layout = QVBoxLayout()
        left_layout.setSpacing(8)

        self.bom_box = QGroupBox("Final Product")
        self.bom_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        form_layout = QGridLayout(self.bom_box)
        form_layout.setHorizontalSpacing(10)
        form_layout.setVerticalSpacing(8)

        self.bom_product_combo = QComboBox()
        self.design_product_name_ar = QLineEdit()
        self.design_product_name_en = QLineEdit()
        self.design_product_sku = QLineEdit()
        self.design_product_barcode = QLineEdit()
        self.design_product_price = QDoubleSpinBox(); self.design_product_price.setRange(0, 999999); self.design_product_price.setDecimals(2)
        self.design_labor_cost = QDoubleSpinBox(); self.design_labor_cost.setRange(0, 999999)
        self.design_packaging_cost = QDoubleSpinBox(); self.design_packaging_cost.setRange(0, 999999)
        self.design_other_cost = QDoubleSpinBox(); self.design_other_cost.setRange(0, 999999)
        self.design_profit_pct = QDoubleSpinBox(); self.design_profit_pct.setRange(0, 1000); self.design_profit_pct.setValue(25)
        self.bom_name_input = QLineEdit()
        self.bom_active_check = QCheckBox()
        self.bom_product_label = QLabel()
        self.bom_name_label = QLabel()

        fields = [
            ("product", self.bom_product_combo),
            ("product_name_ar", self.design_product_name_ar),
            ("product_name_en", self.design_product_name_en),
            ("design_name", self.bom_name_input),
            ("sku_code", self.design_product_sku),
            ("barcode", self.design_product_barcode),
            ("selling_price", self.design_product_price),
            ("labor_cost", self.design_labor_cost),
            ("packaging_cost", self.design_packaging_cost),
            ("other_cost", self.design_other_cost),
        ]
        self._design_field_labels: dict[str, QLabel] = {}
        for i, (label_key, widget) in enumerate(fields):
            r = i // 2
            c = (i % 2) * 2
            label = self.bom_name_label if label_key == "design_name" else QLabel()
            self._design_field_labels[label_key] = label
            form_layout.addWidget(label, r, c)
            form_layout.addWidget(widget, r, c + 1)
        left_layout.addWidget(self.bom_box)

        self.lines_box = QGroupBox("Materials Used")
        lines_layout = QVBoxLayout(self.lines_box)
        lines_layout.setSpacing(8)
        add_line_layout = QHBoxLayout()
        add_line_layout.setSpacing(8)
        self.bom_material_combo = QComboBox()
        self.bom_material_combo.currentIndexChanged.connect(
            self._update_bom_available_qty
        )
        self.bom_available_qty_label = QLabel()
        self.bom_available_qty_value = QLabel("0.000")
        self.bom_qty_input = QDoubleSpinBox(); self.bom_qty_input.setRange(0.001, 999999); self.bom_qty_input.setDecimals(3)
        self.add_bom_line_btn = QPushButton("Add Material")
        self.add_bom_line_btn.clicked.connect(self._add_bom_line)
        self.bom_material_label = QLabel()
        self.bom_qty_label = QLabel()
        add_line_layout.addWidget(self.bom_material_label); add_line_layout.addWidget(self.bom_material_combo)
        add_line_layout.addWidget(self.bom_available_qty_label); add_line_layout.addWidget(self.bom_available_qty_value)
        add_line_layout.addWidget(self.bom_qty_label); add_line_layout.addWidget(self.bom_qty_input)
        add_line_layout.addWidget(self.add_bom_line_btn)
        lines_layout.addLayout(add_line_layout)

        self.bom_lines_table = QTableWidget(0, 5)
        self.bom_lines_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bom_lines_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.bom_lines_table.setAlternatingRowColors(True)
        self.bom_lines_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.bom_lines_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lines_layout.addWidget(self.bom_lines_table)

        self.remove_line_btn = QPushButton("Remove Material")
        self.remove_line_btn.clicked.connect(self._remove_bom_line)
        lines_layout.addWidget(self.remove_line_btn)
        left_layout.addWidget(self.lines_box, 1)

        self.cost_summary_box = QGroupBox("Cost Summary")
        self.cost_summary_box.setFixedWidth(300)
        self.cost_summary_box.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        cost_layout = QFormLayout(self.cost_summary_box)
        cost_layout.setHorizontalSpacing(10)
        cost_layout.setVerticalSpacing(8)
        self.summary_material_cost = QLabel("0.00")
        self.summary_labor_cost = QLabel("0.00")
        self.summary_packaging_cost = QLabel("0.00")
        self.summary_other_cost = QLabel("0.00")
        self.summary_total_cost = QLabel("0.00")
        self.summary_selling_price = QLabel("0.00")
        self.summary_profit = QLabel("0.00")
        self.summary_margin = QLabel("0.00%")
        self.summary_material_cost_label = QLabel()
        self.summary_labor_cost_label = QLabel()
        self.summary_packaging_cost_label = QLabel()
        self.summary_other_cost_label = QLabel()
        self.summary_total_cost_label = QLabel()
        self.summary_selling_price_label = QLabel()
        self.summary_profit_label = QLabel()
        self.summary_margin_label = QLabel()
        cost_layout.addRow(self.summary_material_cost_label, self.summary_material_cost)
        cost_layout.addRow(self.summary_labor_cost_label, self.summary_labor_cost)
        cost_layout.addRow(self.summary_packaging_cost_label, self.summary_packaging_cost)
        cost_layout.addRow(self.summary_other_cost_label, self.summary_other_cost)
        cost_layout.addRow(self.summary_total_cost_label, self.summary_total_cost)
        cost_layout.addRow(self.summary_selling_price_label, self.summary_selling_price)
        cost_layout.addRow(self.summary_profit_label, self.summary_profit)
        cost_layout.addRow(self.summary_margin_label, self.summary_margin)

        left_wrap = QWidget(); left_wrap.setLayout(left_layout)
        main_layout.addWidget(left_wrap, 3)
        main_layout.addWidget(self.cost_summary_box, 1)
        tab_layout.addLayout(main_layout, 1)

        self.boms_table = QTableWidget(0, 3)
        self.boms_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.boms_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.boms_table.setAlternatingRowColors(True)
        self.boms_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.boms_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.boms_table.cellClicked.connect(self._load_bom)
        tab_layout.addWidget(self.boms_table, 1)

        self.bom_save_btn = QPushButton()
        self.produce_design_btn = QPushButton()
        self.produce_design_btn.setProperty("secondary", True)
        self.produce_design_btn.setEnabled(False)
        self.duplicate_design_btn = QPushButton("Duplicate Design")
        self.bom_delete_btn = QPushButton()
        self.bom_clear_btn = QPushButton()
        self.bom_save_btn.clicked.connect(self._save_bom)
        self.produce_design_btn.clicked.connect(self._open_production_for_selected_design)
        self.duplicate_design_btn.clicked.connect(self._open_duplicate_design_picker)
        self.bom_delete_btn.clicked.connect(self._delete_bom)
        self.bom_clear_btn.clicked.connect(self._clear_bom_form)

        footer = QHBoxLayout(); footer.addStretch(1)
        footer.addWidget(self.bom_clear_btn); footer.addWidget(self.duplicate_design_btn); footer.addWidget(self.produce_design_btn); footer.addWidget(self.bom_save_btn)
        tab_layout.addLayout(footer)

        self.tabs.addTab(self.boms_tab, "")

        self._selected_bom_id: Optional[int] = None
        self.new_design_btn.setChecked(True)
        self.design_product_name_ar.textEdited.connect(self._suggest_design_name)
        self.design_labor_cost.valueChanged.connect(self._refresh_design_cost_summary)
        self.design_packaging_cost.valueChanged.connect(self._refresh_design_cost_summary)
        self.design_other_cost.valueChanged.connect(self._refresh_design_cost_summary)
        self.design_product_price.valueChanged.connect(self._refresh_design_cost_summary)
        self._refresh_design_cost_summary()

    def _suggest_design_name(self, product_name: str) -> None:
        """Suggest a design name without overwriting a name entered by the user."""
        if product_name.strip() and not self.bom_name_input.text().strip():
            self.bom_name_input.setText(f"{product_name.strip()} - Design")

    def _build_history_tab(self) -> None:
        self.reports_tab = QWidget()
        tab_layout = QVBoxLayout(self.reports_tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.setSpacing(8)

        history_box = QGroupBox()
        self.history_box = history_box
        history_layout = QVBoxLayout(history_box)
        history_layout.setSpacing(8)
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
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
        self.history_view_btn = QPushButton("View Details")
        self.history_view_btn.clicked.connect(self._view_history_details)
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
        filter_row.addWidget(self.history_view_btn)
        history_layout.addLayout(filter_row)
        self.history_help = QLabel()
        self.history_help.setWordWrap(True)
        history_layout.addWidget(self.history_help)

        self.history_table = QTableWidget(0, 9)
        self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        history_layout.addWidget(self.history_table, 1)

        usage_box = QGroupBox()
        self.usage_box = usage_box
        usage_layout = QVBoxLayout(usage_box)
        usage_layout.setContentsMargins(10, 10, 10, 10)
        usage_layout.setSpacing(8)
        self.usage_table = QTableWidget(0, 3)
        self.usage_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.usage_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.usage_table.setAlternatingRowColors(True)
        self.usage_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.usage_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        usage_layout.addWidget(self.usage_table)
        self.usage_box.setVisible(False)
        self.history_table.itemSelectionChanged.connect(self._refresh_selected_history_usage)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(history_box)
        splitter.addWidget(usage_box)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        tab_layout.addWidget(splitter, 1)

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
            self.materials_table.setItem(row, 5, QTableWidgetItem(f"{material.cost_per_unit:.2f}"))
            self.materials_table.setItem(row, 6, QTableWidgetItem(f"{material.min_qty:.3f}"))
            self.materials_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, material.id)
            display = f"{choose_name(material.name_ar, material.name_en, language=self._language)} ({material.code})"
            self._material_map[display] = material.id

        self.bom_material_combo.clear()
        for label in self._material_map:
            self.bom_material_combo.addItem(label, self._material_map[label])
        self._update_bom_available_qty()

    def _update_bom_available_qty(self) -> None:
        """Show current stock for the material selected for the BOM line."""
        material_id = self.bom_material_combo.currentData()
        material = next(
            (record for record in list_materials() if record.id == material_id),
            None,
        )
        available_qty = material.qty_on_hand if material is not None else 0.0
        self.bom_available_qty_value.setText(f"{available_qty:.3f}")

    def _refresh_products(self) -> None:
        """Backward-compatible wrapper for older call sites."""
        self._refresh_design_products()
        self._refresh_history_products()

    def _refresh_design_products(self) -> None:
        products = list_products()
        self._product_map = {
            f"{choose_name(p.name_ar, p.name_en, language=self._language)} ({p.sku})": p.id
            for p in products
        }
        self.bom_product_combo.clear()
        self.bom_product_combo.addItem("", None)
        for label, product_id in self._product_map.items():
            self.bom_product_combo.addItem(label, product_id)

    def _refresh_history_products(self) -> None:
        if not hasattr(self, "history_product"):
            return
        self.history_product.clear()
        self.history_product.addItem(t("manufacturing.status_all", language=self._language), None)
        for label, product_id in self._product_map.items():
            self.history_product.addItem(label, product_id)

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

        if hasattr(self, "design_search_results"):
            self._populate_design_picker(self.design_search_input.text())

    def _populate_design_picker(self, filter_text: str = "") -> None:
        """Populate the design-first picker with exact BOM identities."""
        self.design_search_results.clear()
        products = {product.id: product for product in list_products()}
        needle = filter_text.strip().casefold()
        for bom in list_boms():
            product = products.get(bom.product_id)
            product_name = " / ".join(
                value for value in (
                    (product.name_ar or "").strip() if product else "",
                    (product.name_en or "").strip() if product else "",
                ) if value
            ) or f"Product {bom.product_id}"
            sku = (product.sku or "").strip() if product else ""
            label = f"{bom.name} | {product_name} | SKU: {sku or '-'}"
            if needle and needle not in label.casefold():
                continue
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, bom.id)
            self.design_search_results.addItem(item)

    def _show_design_picker(self) -> None:
        self.new_design_btn.setChecked(False)
        self.edit_design_btn.setChecked(True)
        self.design_picker.setVisible(True)
        self._populate_design_picker(self.design_search_input.text())
        self.design_search_input.setFocus()

    def _load_picker_design(self, item: QListWidgetItem) -> None:
        self._load_design_by_id(int(item.data(Qt.ItemDataRole.UserRole)))

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
            self._editing_material_id,
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
            t("manufacturing.material_saved_successfully", language=self._language),
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

    def _adjust_material_stock(self) -> None:
        if not self._selected_material_id:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                "اختر خامة أولاً." if self._language == "ar" else "Select a material first.",
            )
            return

        material = next(
            (
                record
                for record in list_materials()
                if record.id == self._selected_material_id
            ),
            None,
        )
        if material is None:
            return

        is_arabic = self._language == "ar"
        dialog = QDialog(self)
        dialog.setWindowTitle("تعديل الرصيد" if is_arabic else "Adjust Stock")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        current_qty = QLabel(f"{material.qty_on_hand:.3f}")
        new_qty_input = QDoubleSpinBox()
        new_qty_input.setRange(0, 999999)
        new_qty_input.setDecimals(3)
        new_qty_input.setValue(float(material.qty_on_hand))
        new_qty_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        reason_combo = QComboBox()
        reasons = (
            ("Opening Balance", "رصيد افتتاحي"),
            ("Inventory Count", "جرد المخزون"),
            ("Correction", "تصحيح"),
            ("Other", "أخرى"),
        )
        for english_label, arabic_label in reasons:
            reason_combo.addItem(arabic_label if is_arabic else english_label, english_label)

        form.addRow("الكمية الحالية" if is_arabic else "Current Qty", current_qty)
        form.addRow("الكمية الجديدة" if is_arabic else "New Qty", new_qty_input)
        form.addRow("السبب" if is_arabic else "Reason", reason_combo)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        confirm_button = QPushButton("تأكيد" if is_arabic else "Confirm")
        cancel_button = QPushButton("إلغاء" if is_arabic else "Cancel")
        confirm_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        buttons.addWidget(confirm_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        new_qty = float(new_qty_input.value())
        save_material(
            material.id,
            material.name_ar,
            material.name_en,
            material.code,
            new_qty,
            material.unit,
            material.min_qty,
            material.cost_per_unit,
        )
        self.material_qty.setValue(new_qty)
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            "تم تعديل الرصيد." if is_arabic else "Stock adjusted.",
        )
        self._refresh_materials()
        self._update_material_edit_ui()

    def _clear_material_form(self) -> None:
        self._selected_material_id = None
        self._editing_material_id = None
        self.materials_table.clearSelection()
        self.material_name_ar.clear()
        self.material_name_en.clear()
        self.material_code.clear()
        self.material_qty.setValue(0)
        self.material_unit.clear()
        self.material_min_qty.setValue(0)
        self.material_cost.setValue(0)
        self._update_material_edit_ui()

    def _update_material_edit_ui(self) -> None:
        in_edit_mode = self._editing_material_id is not None
        self.material_save_btn.setText("حفظ خامة" if self._language == "ar" else "Save Material")
        has_selection = self._selected_material_id is not None
        self.material_adjust_stock_btn.setEnabled(has_selection)
        self.material_delete_btn.setEnabled(has_selection)
        if in_edit_mode:
            name = self.material_name_en.text().strip() or self.material_name_ar.text().strip() or "-"
            self.material_edit_indicator.setText(f"Editing Material: {name}")
        else:
            self.material_edit_indicator.clear()

    def _load_material(self, row: int) -> None:
        self._selected_material_id = self.materials_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self._editing_material_id = self._selected_material_id
        self.material_name_ar.setText(self.materials_table.item(row, 0).text())
        self.material_name_en.setText(self.materials_table.item(row, 1).text())
        self.material_code.setText(self.materials_table.item(row, 2).text())
        self.material_qty.setValue(float(self.materials_table.item(row, 3).text()))
        self.material_unit.setText(self.materials_table.item(row, 4).text())
        self.material_cost.setValue(float(self.materials_table.item(row, 5).text()))
        self.material_min_qty.setValue(float(self.materials_table.item(row, 6).text()))
        self._update_material_edit_ui()

    def _add_bom_line(self) -> None:
        material_id = self.bom_material_combo.currentData()
        if not material_id:
            return
        qty_required = float(self.bom_qty_input.value())
        if qty_required <= 0:
            QMessageBox.warning(
                self,
                "Validation" if self._language != "ar" else "التحقق",
                (
                    "Qty Used Per Unit must be strictly greater than zero."
                    if self._language != "ar"
                    else "يجب أن تكون الكمية المستخدمة لكل وحدة أكبر من صفر."
                ),
            )
            return

        material = next(
            (record for record in list_materials() if record.id == material_id),
            None,
        )
        available_qty = material.qty_on_hand if material is not None else 0.0
        if qty_required > available_qty:
            QMessageBox.warning(
                self,
                "Availability Warning" if self._language != "ar" else "تحذير التوفر",
                (
                    f"Qty Used Per Unit ({qty_required:.3f}) exceeds the current "
                    f"Available Qty ({available_qty:.3f}). The design can still be "
                    "saved because saving a design does not consume stock; stock is "
                    "consumed only during production."
                    if self._language != "ar"
                    else f"الكمية المستخدمة لكل وحدة ({qty_required:.3f}) تتجاوز "
                    f"الكمية المتاحة حاليًا ({available_qty:.3f}). لا يزال بإمكانك "
                    "حفظ التصميم لأن حفظ التصميم لا يستهلك المخزون؛ يُستهلك المخزون "
                    "فقط أثناء الإنتاج."
                ),
            )
        row = self.bom_lines_table.rowCount()
        self.bom_lines_table.insertRow(row)
        self.bom_lines_table.setItem(row, 0, QTableWidgetItem(self.bom_material_combo.currentText()))
        self.bom_lines_table.setItem(row, 1, QTableWidgetItem("0.000"))
        self.bom_lines_table.setItem(row, 2, QTableWidgetItem(f"{qty_required:.3f}"))
        self.bom_lines_table.setItem(row, 3, QTableWidgetItem("0.00"))
        self.bom_lines_table.setItem(row, 4, QTableWidgetItem("0.00"))
        self.bom_lines_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, material_id)
        self._refresh_design_cost_summary()

    def _remove_bom_line(self) -> None:
        row = self.bom_lines_table.currentRow()
        if row >= 0:
            self.bom_lines_table.removeRow(row)
            self._refresh_design_cost_summary()

    def _refresh_design_cost_summary(self) -> None:
        materials = {m.id: m for m in list_materials()}
        material_total_cost = 0.0
        for row in range(self.bom_lines_table.rowCount()):
            material_id = self.bom_lines_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            qty_used = float(self.bom_lines_table.item(row, 2).text())
            material = materials.get(material_id)
            if not material:
                continue
            line_total_cost = qty_used * material.cost_per_unit
            material_total_cost += line_total_cost
            self.bom_lines_table.setItem(row, 1, QTableWidgetItem(f"{material.qty_on_hand:.3f}"))
            self.bom_lines_table.setItem(row, 3, QTableWidgetItem(f"{material.cost_per_unit:.2f}"))
            self.bom_lines_table.setItem(row, 4, QTableWidgetItem(f"{line_total_cost:.2f}"))
        labor_cost = float(self.design_labor_cost.value())
        packaging_cost = float(self.design_packaging_cost.value())
        other_cost = float(self.design_other_cost.value())
        total_cost = material_total_cost + labor_cost + packaging_cost + other_cost
        selling_price = float(self.design_product_price.value())
        profit = selling_price - total_cost
        margin = (profit / selling_price * 100.0) if selling_price > 0 else 0.0
        self.summary_material_cost.setText(f"{material_total_cost:.2f}")
        self.summary_labor_cost.setText(f"{labor_cost:.2f}")
        self.summary_packaging_cost.setText(f"{packaging_cost:.2f}")
        self.summary_other_cost.setText(f"{other_cost:.2f}")
        self.summary_total_cost.setText(f"{total_cost:.2f}")
        self.summary_selling_price.setText(f"{selling_price:.2f}")
        self.summary_profit.setText(f"{profit:.2f}")
        self.summary_margin.setText(f"{margin:.2f}%")

    def _clear_design_cost_estimates(self) -> None:
        """Reset per-unit estimates for a brand-new design."""
        self.design_labor_cost.setValue(0.0)
        self.design_packaging_cost.setValue(0.0)
        self.design_other_cost.setValue(0.0)

    def _save_bom(self) -> None:
        name_ar = self.design_product_name_ar.text().strip()
        name_en = self.design_product_name_en.text().strip()
        name = name_ar or name_en
        sku = self.design_product_sku.text().strip()
        design_name = self.bom_name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Product name is required.")
            return
        if not design_name:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.bom_name_required", language=self._language),
            )
            return
        if not sku:
            sku = re.sub(r"[^A-Z0-9]+", "-", name.upper()).strip("-")[:20]
            sku = sku or f"DES-{datetime.now().strftime('%H%M%S')}"
            self.design_product_sku.setText(sku)

        lines = []
        for row in range(self.bom_lines_table.rowCount()):
            material_id = self.bom_lines_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            qty_required = float(self.bom_lines_table.item(row, 2).text())
            lines.append((material_id, qty_required))
        if not lines:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("manufacturing.add_material_line", language=self._language),
            )
            return

        products = list_products()
        explicit_product_id = self._editing_product_id
        if explicit_product_id is None and self._selected_bom_id is not None:
            selected_bom = next(
                (bom for bom in list_boms() if bom.id == self._selected_bom_id),
                None,
            )
            explicit_product_id = selected_bom.product_id if selected_bom else None
        existing = next((p for p in products if p.id == explicit_product_id), None)
        sku_product = next(
            (p for p in products if (p.sku or "").strip().casefold() == sku.casefold()),
            None,
        )
        if existing and sku_product and sku_product.id != existing.id:
            QMessageBox.warning(self, "Validation", "SKU/code already belongs to another product.")
            return
        existing = existing or sku_product

        saved_product_id, _saved_bom_id = save_product_design(
            product_id=existing.id if existing else None,
            bom_id=self._selected_bom_id,
            name_ar=name_ar,
            name_en=name_en,
            sku=sku,
            barcode=self.design_product_barcode.text().strip(),
            price=float(self.design_product_price.value()),
            design_name=design_name,
            active=self.bom_active_check.isChecked(),
            lines=lines,
            labor_cost=float(self.design_labor_cost.value()),
            packaging_cost=float(self.design_packaging_cost.value()),
            other_cost=float(self.design_other_cost.value()),
        )
        product_id = saved_product_id or (existing.id if existing else None)
        if product_id is None:
            product = next(
                (
                    p
                    for p in list_products()
                    if (p.sku or "").strip().casefold() == sku.casefold()
                ),
                None,
            )
            product_id = product.id if product else None
        if product_id is None:
            QMessageBox.warning(self, "Error", "Could not save product.")
            return

        self._editing_product_id = int(product_id)
        self._refresh_products()
        product_index = self.bom_product_combo.findData(product_id)
        if product_index >= 0:
            self.bom_product_combo.setCurrentIndex(product_index)
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("manufacturing.bom_saved", language=self._language),
        )
        self._refresh_boms()
        self.inventory_changed.emit()
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
        self._start_new_design()

    def _start_new_design(self) -> None:
        """Reset every persisted and session-only field to an unsaved design."""
        self._selected_bom_id = None
        self._editing_product_id = None
        self.boms_table.clearSelection()
        self.design_search_results.clearSelection()
        self.design_picker.setVisible(False)
        self.new_design_btn.setChecked(True)
        self.edit_design_btn.setChecked(False)
        self.produce_design_btn.setEnabled(False)
        self.bom_product_combo.setCurrentIndex(0)
        self.design_product_name_ar.clear()
        self.design_product_name_en.clear()
        self.design_product_sku.clear()
        self.design_product_barcode.clear()
        self.design_product_price.setValue(0.0)
        self.bom_name_input.clear()
        self.bom_active_check.setChecked(False)
        self.bom_lines_table.setRowCount(0)
        self._clear_design_cost_estimates()
        self.design_profit_pct.setValue(25.0)
        self._refresh_design_cost_summary()

    def _load_bom(self, row: int) -> None:
        """Table adapter for the same exact-BOM loader used by the picker."""
        item = self.boms_table.item(row, 0)
        if item is not None:
            self._load_design_by_id(int(item.data(Qt.ItemDataRole.UserRole)))

    def _load_design_by_id(self, bom_id: int) -> None:
        """Load one BOM and its linked product without product-first ambiguity."""
        bom = next((candidate for candidate in list_boms() if candidate.id == bom_id), None)
        if bom is None:
            QMessageBox.warning(self, "Edit Design", "Could not load selected design.")
            return
        product = next((candidate for candidate in list_products() if candidate.id == bom.product_id), None)
        if product is None:
            QMessageBox.warning(self, "Edit Design", "Could not load the design's linked product.")
            return

        self._selected_bom_id = bom.id
        self._editing_product_id = product.id
        self.new_design_btn.setChecked(False)
        self.edit_design_btn.setChecked(True)
        self.design_picker.setVisible(True)
        self.produce_design_btn.setEnabled(True)
        self.design_product_name_ar.setText(product.name_ar or "")
        self.design_product_name_en.setText(product.name_en or "")
        self.design_product_sku.setText(product.sku or "")
        self.design_product_barcode.setText(product.barcode or "")
        self.design_product_price.setValue(float(product.price or 0.0))
        product_index = self.bom_product_combo.findData(product.id)
        if product_index >= 0:
            self.bom_product_combo.setCurrentIndex(product_index)
        self.bom_name_input.setText(bom.name)
        self.bom_active_check.setChecked(bom.active)
        self.bom_lines_table.setRowCount(0)
        for line in list_bom_lines(bom.id):
            material_label = next(
                (label for label, material_id in self._material_map.items() if material_id == line.material_id),
                "خامة غير متاحة" if self._language == "ar" else "Unavailable Material",
            )
            row = self.bom_lines_table.rowCount()
            self.bom_lines_table.insertRow(row)
            values = (material_label, "0.000", f"{line.qty_required:.3f}", "0.00", "0.00")
            for column, value in enumerate(values):
                self.bom_lines_table.setItem(row, column, QTableWidgetItem(value))
            self.bom_lines_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, line.material_id)
        self.design_labor_cost.setValue(float(getattr(bom, "labor_cost", 0.0) or 0.0))
        self.design_packaging_cost.setValue(float(getattr(bom, "packaging_cost", 0.0) or 0.0))
        self.design_other_cost.setValue(float(getattr(bom, "other_cost", 0.0) or 0.0))
        self._refresh_design_cost_summary()

    def _open_production_for_selected_design(self) -> None:
        """Open the focused quantity dialog for the currently selected BOM."""
        selected_bom_id = self._selected_bom_id
        bom = next((item for item in list_boms() if item.id == selected_bom_id), None)
        if bom is None:
            self.produce_design_btn.setEnabled(False)
            return
        product = next((item for item in list_products() if item.id == bom.product_id), None)
        if product is None:
            QMessageBox.warning(self, "Production", "Could not load the linked product.")
            return

        language = self._language
        dialog = QDialog(self)
        dialog.setObjectName("producedQuantityDialog")
        dialog.setModal(True)
        dialog.setWindowTitle("إضافة كمية منتجة" if language == "ar" else "Add Produced Quantity")
        dialog.resize(620, 440)
        layout = QVBoxLayout(dialog)
        details = QFormLayout()
        bom_name_label = QLabel(bom.name)
        details.addRow("اسم التصميم" if language == "ar" else "Design Name", bom_name_label)
        product_name = choose_name(product.name_ar, product.name_en, language=language)
        product_name_label = QLabel(product_name)
        details.addRow("المنتج المرتبط" if language == "ar" else "Linked Product", product_name_label)
        product_stock_label = QLabel(f"{product.qty_on_hand:.3f}")
        details.addRow(
            "المخزون النهائي الحالي" if language == "ar" else "Current Finished Stock",
            product_stock_label,
        )
        self.produced_qty_input = QDoubleSpinBox()
        self.produced_qty_input.setObjectName("producedQuantityInput")
        self.produced_qty_input.setRange(0.001, 999999)
        self.produced_qty_input.setDecimals(3)
        self.produced_qty_input.setValue(1.0)
        self.produced_qty_input.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        details.addRow("الكمية" if language == "ar" else "Quantity", self.produced_qty_input)
        layout.addLayout(details)

        materials_title = QLabel("الخامات المطلوبة" if language == "ar" else "Required Materials")
        layout.addWidget(materials_title)
        preview = QTableWidget(0, 4)
        preview.setObjectName("requiredMaterialsPreview")
        preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        preview.setHorizontalHeaderLabels(
            ["الخامة", "لكل وحدة", "المطلوب", "المتاح"] if language == "ar"
            else ["Material", "Per Unit", "Required", "Available"]
        )
        preview.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(preview, 1)

        dialog._is_submitting = False

        def refresh_preview() -> None:
            # Refresh every input to the calculation.  In particular, do not
            # retain quantities from a failed production transaction.
            current_bom = next((item for item in list_boms() if item.id == selected_bom_id), None)
            current_product = None
            if current_bom is not None:
                current_product = next(
                    (item for item in list_products() if item.id == current_bom.product_id), None
                )
            lines = list_bom_lines(selected_bom_id)
            materials = {material.id: material for material in list_materials()}
            if current_bom is not None:
                bom_name_label.setText(current_bom.name)
            if current_product is not None:
                product_name_label.setText(
                    choose_name(current_product.name_ar, current_product.name_en, language=language)
                )
                product_stock_label.setText(f"{current_product.qty_on_hand:.3f}")
            quantity = float(self.produced_qty_input.value())
            preview.setRowCount(0)
            for line in lines:
                material = materials.get(line.material_id)
                row = preview.rowCount()
                preview.insertRow(row)
                name = (
                    choose_name(material.name_ar, material.name_en, language=language)
                    if material else ("خامة غير متاحة" if language == "ar" else "Unavailable Material")
                )
                available = float(material.qty_on_hand) if material else 0.0
                values = (name, f"{line.qty_required:.3f}",
                          f"{line.qty_required * quantity:.3f}", f"{available:.3f}")
                for column, value in enumerate(values):
                    preview.setItem(row, column, QTableWidgetItem(value))

        def confirm_production() -> None:
            if dialog._is_submitting:
                return
            dialog._is_submitting = True
            confirm.setEnabled(False)
            quantity = float(self.produced_qty_input.value())
            try:
                result = produce_from_bom(selected_bom_id, quantity)
            except Exception as exc:
                refresh_preview()
                QMessageBox.warning(
                    dialog,
                    "خطأ في الإنتاج" if language == "ar" else "Production Error",
                    str(exc),
                )
            else:
                if result.get("success"):
                    dialog.accept()
                    self.on_activated()
                    self.inventory_changed.emit()
                    message = (
                        f"تمت إضافة {quantity:g} قطعة إلى المخزون بنجاح"
                        if language == "ar"
                        else f"Successfully added {quantity:g} units to inventory"
                    )
                    QMessageBox.information(self, "نجاح" if language == "ar" else "Success", message)
                    return

                refresh_preview()
                shortage_lines = []
                for shortage in result.get("shortages", []):
                    name = shortage.get(f"material_name_{language}") or shortage.get("material_name", "")
                    unit = shortage.get("unit", "")
                    if language == "ar":
                        details_text = (
                            f"{name}: المطلوب {shortage['required']:g} {unit}، "
                            f"المتاح {shortage['available']:g} {unit}، "
                            f"الناقص {shortage['missing']:g} {unit}"
                        )
                    else:
                        details_text = (
                            f"{name}: Required {shortage['required']:g} {unit}, "
                            f"Available {shortage['available']:g} {unit}, "
                            f"Missing {shortage['missing']:g} {unit}"
                        )
                    shortage_lines.append(details_text)
                heading = (
                    f"لا يمكن إنتاج {quantity:g} قطعة"
                    if language == "ar" else f"Cannot produce {quantity:g} units"
                )
                QMessageBox.warning(
                    dialog,
                    "نقص في الخامات" if language == "ar" else "Material Shortage",
                    "\n".join([heading, *shortage_lines]),
                )
            finally:
                if dialog.isVisible():
                    dialog._is_submitting = False
                    confirm.setEnabled(True)

        actions = QHBoxLayout()
        actions.addStretch(1)
        cancel = QPushButton("إلغاء" if language == "ar" else "Cancel")
        confirm = QPushButton("تأكيد الإنتاج" if language == "ar" else "Confirm Production")
        cancel.setObjectName("cancelProductionButton")
        confirm.setObjectName("confirmProductionButton")
        cancel.clicked.connect(dialog.reject)
        confirm.clicked.connect(confirm_production)
        actions.addWidget(cancel)
        actions.addWidget(confirm)
        layout.addLayout(actions)
        self.produced_quantity_dialog = dialog
        self.produced_materials_preview = preview
        self.produced_qty_input.valueChanged.connect(refresh_preview)
        refresh_preview()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self.produced_qty_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

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
            self.history_table.setItem(row, 0, QTableWidgetItem(row_data.datetime))
            self.history_table.setItem(row, 1, QTableWidgetItem(row_data.product_name))
            self.history_table.setItem(row, 2, QTableWidgetItem(f"{row_data.qty_produced:.3f}"))
            self.history_table.setItem(row, 3, QTableWidgetItem(f"{row_data.material_cost:.2f}"))
            self.history_table.setItem(row, 4, QTableWidgetItem(f"{row_data.extra_cost:.2f}"))
            self.history_table.setItem(row, 5, QTableWidgetItem(f"{row_data.total_cost:.2f}"))
            self.history_table.setItem(row, 6, QTableWidgetItem(f"{row_data.selling_price:.2f}"))
            self.history_table.setItem(row, 7, QTableWidgetItem(f"{row_data.profit:.2f}"))
            self.history_table.setItem(row, 8, QTableWidgetItem(f"{row_data.margin_pct:.2f}%"))
            self.history_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, row_data.order_no)
        self._refresh_selected_history_usage()

    def _refresh_selected_history_usage(self) -> None:
        row = self.history_table.currentRow()
        self.usage_table.setRowCount(0)
        if row < 0:
            self.usage_box.setVisible(False)
            return
        order_no_item = self.history_table.item(row, 0)
        order_no = order_no_item.data(Qt.ItemDataRole.UserRole) if order_no_item else None
        if not order_no:
            self.usage_box.setVisible(False)
            return
        source_order = next((o for o in list_production_orders() if o.order_no == order_no), None)
        if not source_order:
            self.usage_box.setVisible(False)
            return
        for consumption in list_production_consumption(source_order.id):
            material_name = choose_name(
                consumption.material_name_ar,
                consumption.material_name_en,
                language=self._language,
            )
            row_idx = self.usage_table.rowCount()
            self.usage_table.insertRow(row_idx)
            self.usage_table.setItem(row_idx, 0, QTableWidgetItem(material_name))
            self.usage_table.setItem(
                row_idx, 1, QTableWidgetItem(f"{consumption.qty_consumed:.3f}")
            )
            historical_cost = consumption.qty_consumed * consumption.cost_at_time
            self.usage_table.setItem(row_idx, 2, QTableWidgetItem(f"{historical_cost:.2f}"))
        self.usage_box.setVisible(self.usage_table.rowCount() > 0)

    def _view_history_details(self) -> None:
        row = self.history_table.currentRow()
        if row < 0:
            QMessageBox.information(
                self,
                "عرض التفاصيل" if self._language == "ar" else "View Details",
                "اختر صفًا من السجل أولاً." if self._language == "ar" else "Select one history row first.",
            )
            return
        values = [self.history_table.item(row, col).text() if self.history_table.item(row, col) else "" for col in range(9)]
        QMessageBox.information(
            self,
            "تفاصيل الورشة" if self._language == "ar" else "Workshop Details",
            (
                f"{'التاريخ' if self._language == 'ar' else 'Date'}: {values[0]}\n"
                f"{'المنتج' if self._language == 'ar' else 'Product'}: {values[1]}\n"
                f"{'الكمية المنتجة' if self._language == 'ar' else 'Qty Produced'}: {values[2]}\n"
                f"{'تكلفة الخامات' if self._language == 'ar' else 'Material Cost'}: {values[3]}\n"
                f"{'تكلفة إضافية' if self._language == 'ar' else 'Extra Cost'}: {values[4]}\n"
                f"{'التكلفة الإجمالية' if self._language == 'ar' else 'Total Cost'}: {values[5]}\n"
                f"{'سعر البيع' if self._language == 'ar' else 'Selling Price'}: {values[6]}\n"
                f"{'الربح' if self._language == 'ar' else 'Profit'}: {values[7]}\n"
                f"{'الهامش %' if self._language == 'ar' else 'Margin %'}: {values[8]}"
            ),
        )

    def _open_duplicate_design_picker(self) -> None:
        boms = list_boms()
        if not boms:
            QMessageBox.information(self, "Duplicate Design", "No previous designs available.")
            return
        products = {product.id: product for product in list_products()}
        choices: list[tuple[str, int]] = []
        for bom in boms:
            product = products.get(bom.product_id)
            product_name = (
                choose_name(product.name_ar, product.name_en, language=self._language)
                if product
                else f"Product {bom.product_id}"
            )
            sku = (product.sku or "").strip() if product else ""
            label = f"{bom.name} | {product_name} | SKU: {sku or '-'}"
            choices.append((label, bom.id))
        selected_label, ok = QInputDialog.getItem(
            self,
            "Duplicate Design",
            "Select a design:",
            [label for label, _ in choices],
            0,
            False,
        )
        if not ok or not selected_label:
            return
        selected_bom_id = next((bom_id for label, bom_id in choices if label == selected_label), None)
        if selected_bom_id is None:
            QMessageBox.warning(self, "Duplicate Design", "Missing design reference.")
            return
        self._duplicate_design_from_bom(selected_bom_id)

    def _duplicate_design_from_bom(self, bom_id: int) -> None:
        source_bom = next((bom for bom in list_boms() if bom.id == bom_id), None)
        if not source_bom:
            QMessageBox.warning(self, "Duplicate Design", "Could not load selected design.")
            return
        source_product = next((p for p in list_products() if p.id == source_bom.product_id), None)
        if not source_product:
            QMessageBox.warning(self, "Duplicate Design", "Could not load the design's linked product.")
            return
        source_lines = list_bom_lines(source_bom.id)

        self._start_new_design()
        self.design_product_name_ar.setText(source_product.name_ar or "")
        self.design_product_name_en.setText(source_product.name_en or "")
        product_index = self.bom_product_combo.findData(source_product.id)
        if product_index >= 0:
            self.bom_product_combo.setCurrentIndex(product_index)
        source_sku = (source_product.sku or "").strip()
        copy_sku = f"{source_sku}-COPY" if source_sku else "DES-COPY"
        used_skus = {(product.sku or "").strip().casefold() for product in list_products()}
        suffix = 2
        candidate = copy_sku
        while candidate.casefold() in used_skus:
            candidate = f"{copy_sku}-{suffix}"
            suffix += 1
        self.design_product_sku.setText(candidate)
        self.design_product_barcode.setText(source_product.barcode or "")
        self.design_product_price.setValue(float(source_product.price or 0.0))
        self.design_labor_cost.setValue(float(getattr(source_bom, "labor_cost", 0.0) or 0.0))
        self.design_packaging_cost.setValue(float(getattr(source_bom, "packaging_cost", 0.0) or 0.0))
        self.design_other_cost.setValue(float(getattr(source_bom, "other_cost", 0.0) or 0.0))
        copy_suffix = "نسخة" if self._language == "ar" else "Copy"
        self.bom_name_input.setText(f"{source_bom.name} - {copy_suffix}")
        self.bom_active_check.setChecked(source_bom.active)
        self.bom_lines_table.setRowCount(0)
        for line in source_lines:
            material_label = next(
                (label for label, mid in self._material_map.items() if mid == line.material_id),
                "خامة غير متاحة" if self._language == "ar" else "Unavailable Material",
            )
            row_idx = self.bom_lines_table.rowCount()
            self.bom_lines_table.insertRow(row_idx)
            self.bom_lines_table.setItem(row_idx, 0, QTableWidgetItem(material_label))
            self.bom_lines_table.setItem(row_idx, 1, QTableWidgetItem("0.000"))
            self.bom_lines_table.setItem(row_idx, 2, QTableWidgetItem(f"{line.qty_required:.3f}"))
            self.bom_lines_table.setItem(row_idx, 3, QTableWidgetItem("0.00"))
            self.bom_lines_table.setItem(row_idx, 4, QTableWidgetItem("0.00"))
            self.bom_lines_table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, line.material_id)
        # Duplication must remain an unsaved form: Save Design inserts a BOM
        # rather than updating either source identity.
        self._selected_bom_id = None
        self._editing_product_id = None
        self._refresh_design_cost_summary()

        self.tabs.setCurrentIndex(0)
        QMessageBox.information(self, "Duplicate Design", "Design copied. Review details then create product.")

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
        if self.header_label is not None:
            self.header_label.setText(t("manufacturing.header", language=language))
        self.tabs.setTabText(0, "إنشاء تصميم" if language == "ar" else "Designs")
        self.tabs.setTabText(1, "الخامات" if language == "ar" else "Materials")
        self.tabs.setTabText(2, "سجل التصنيع" if language == "ar" else "Manufacturing History")
        self.materials_box.setTitle(t("manufacturing.materials_box", language=language))
        self.material_name_ar_label.setText(t("manufacturing.material_name_ar", language=language))
        self.material_name_en_label.setText(t("manufacturing.material_name_en", language=language))
        self.material_code_label.setText(t("manufacturing.material_code", language=language))
        self.material_qty_label.setText(t("manufacturing.material_qty", language=language))
        self.material_unit_label.setText(t("manufacturing.material_unit", language=language))
        self.material_min_qty_label.setText(t("manufacturing.material_min_qty", language=language))
        self.material_cost_label.setText(t("manufacturing.material_cost", language=language))
        self.material_adjust_stock_btn.setText("تعديل الرصيد" if language == "ar" else "Adjust Stock")
        self.material_delete_btn.setText("حذف خامة" if language == "ar" else "Delete Material")
        self.material_clear_btn.setText("خامة جديدة" if language == "ar" else "New Material")
        self._update_material_edit_ui()
        self.materials_table.setHorizontalHeaderLabels(
            [
                "اسم الخامة" if language == "ar" else "Material Name Arabic",
                "اسم الخامة (EN)" if language == "ar" else "Material Name English",
                "الكود" if language == "ar" else "Code",
                "الكمية" if language == "ar" else "Qty On Hand",
                "الوحدة" if language == "ar" else "Unit",
                "التكلفة" if language == "ar" else "Unit Cost",
                "الحد الأدنى" if language == "ar" else "Min Qty",
            ]
        )
        self.tabs.setTabText(0, "إنشاء تصميم" if language == "ar" else "Designs")
        self.new_design_btn.setText("تصميم جديد" if language == "ar" else "New Design")
        self.edit_design_btn.setText(
            "تعديل تصميم موجود" if language == "ar" else "Edit Existing Design"
        )
        self.design_search_input.setPlaceholderText(
            "ابحث باسم التصميم أو المنتج أو الرمز"
            if language == "ar"
            else "Search by design name, product name, or SKU"
        )
        self.bom_box.setTitle("المنتج النهائي" if language == "ar" else "Final Product")
        self._design_field_labels["product"].setText(t("manufacturing.bom_product", language=language))
        self._design_field_labels["product_name_ar"].setText("اسم المنتج بالعربية" if language == "ar" else "Product Name Arabic")
        self._design_field_labels["product_name_en"].setText("اسم المنتج بالإنجليزية" if language == "ar" else "Product Name English")
        self._design_field_labels["sku_code"].setText("الرمز/الكود" if language == "ar" else "SKU/Code")
        self._design_field_labels["barcode"].setText("الباركود" if language == "ar" else "Barcode")
        self._design_field_labels["selling_price"].setText("سعر البيع" if language == "ar" else "Selling Price")
        self._design_field_labels["labor_cost"].setText("تقدير تكلفة العمالة" if language == "ar" else "Labor Estimate")
        self._design_field_labels["packaging_cost"].setText("تقدير تكلفة التغليف" if language == "ar" else "Packaging Estimate")
        self._design_field_labels["other_cost"].setText("تقدير تكلفة أخرى" if language == "ar" else "Other Estimate")
        self.bom_product_label.setText(t("manufacturing.bom_product", language=language))
        self.bom_name_label.setText("اسم التصميم" if language == "ar" else "Design Name")
        self.bom_name_label.setToolTip("أدخل اسمًا واضحًا للتصميم." if language == "ar" else "Enter a clear name for this design.")
        self.bom_active_check.setText(t("manufacturing.bom_active", language=language))
        self.lines_box.setTitle("الخامات المستخدمة" if language == "ar" else "Materials Used")
        self.bom_material_label.setText("الخامة" if language == "ar" else "Material")
        self.bom_available_qty_label.setText("الكمية المتاحة" if language == "ar" else "Available Qty")
        self.bom_qty_label.setText("الكمية المستخدمة" if language == "ar" else "Qty Used")
        self.add_bom_line_btn.setText("إضافة خامة" if language == "ar" else "Add Material")
        self.bom_lines_table.setHorizontalHeaderLabels(["الخامة", "الكمية المتاحة", "الكمية المستخدمة لكل وحدة", "تكلفة الوحدة", "التكلفة لكل وحدة"] if language == "ar" else ["Material", "Available Qty", "Qty Used Per Unit", "Unit Cost", "Cost Per Unit"])
        self.remove_line_btn.setText("حذف خامة" if language == "ar" else "Remove Material")
        self.cost_summary_box.setTitle("ملخص التكلفة" if language == "ar" else "Cost Summary")
        self.summary_material_cost_label.setText("تكلفة الخامات" if language == "ar" else "Material Cost")
        self.summary_labor_cost_label.setText("تكلفة العمالة" if language == "ar" else "Labor Cost")
        self.summary_packaging_cost_label.setText("تكلفة التغليف" if language == "ar" else "Packaging Cost")
        self.summary_other_cost_label.setText("تكلفة أخرى" if language == "ar" else "Other Cost")
        self.summary_total_cost_label.setText("التكلفة الإجمالية لكل وحدة" if language == "ar" else "Total Cost Per Unit")
        self.summary_selling_price_label.setText("سعر البيع" if language == "ar" else "Selling Price")
        self.summary_profit_label.setText("الربح لكل وحدة" if language == "ar" else "Profit Per Unit")
        self.summary_margin_label.setText("هامش %" if language == "ar" else "Margin %")
        self.bom_save_btn.setText("حفظ التصميم" if language == "ar" else "Save Design")
        self.produce_design_btn.setText(
            "إضافة كمية منتجة" if language == "ar" else "Add Produced Quantity"
        )
        self.duplicate_design_btn.setText("تكرار التصميم" if language == "ar" else "Duplicate Design")
        self.bom_delete_btn.setText(t("manufacturing.delete_bom_label", language=language))
        self.bom_clear_btn.setText("Clear")
        self.boms_table.setHorizontalHeaderLabels(
            [
                t("manufacturing.bom_table_product", language=language),
                t("manufacturing.bom_table_name", language=language),
                t("manufacturing.bom_table_active", language=language),
            ]
        )
        self.history_box.setTitle(t("manufacturing.history_box", language=language))
        self.history_help.setText(t("manufacturing.history_help", language=language))
        self.history_from_label.setText(f"{t('common.from', language=language)}:")
        self.history_to_label.setText(f"{t('common.to', language=language)}:")
        self.history_status_label.setText(f"{t('manufacturing.history_status', language=language)}:")
        self.history_product_label.setText(f"{t('manufacturing.history_product', language=language)}:")
        self.history_refresh_btn.setText(t("manufacturing.history_refresh", language=language))
        self.history_view_btn.setText("عرض التفاصيل" if language == "ar" else "View Details")
        self.history_table.setHorizontalHeaderLabels(
            [
                t("manufacturing.history_table_date", language=language),
                t("manufacturing.history_table_product", language=language),
                "الكمية المنتجة" if language == "ar" else "Qty Produced",
                "تكلفة الخامات" if language == "ar" else "Material Cost",
                "تكلفة إضافية" if language == "ar" else "Extra Cost",
                "التكلفة الإجمالية" if language == "ar" else "Total Cost",
                "سعر البيع" if language == "ar" else "Selling Price",
                "الربح" if language == "ar" else "Profit",
                "الهامش %" if language == "ar" else "Margin %",
            ]
        )
        self.usage_box.setTitle(t("manufacturing.usage_box", language=language))
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
        self._refresh_design_products()
        self._refresh_history_products()
        self._refresh_boms()
