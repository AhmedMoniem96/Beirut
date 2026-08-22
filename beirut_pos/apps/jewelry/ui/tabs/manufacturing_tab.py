"""Manufacturing tab for Jewelry app."""

from __future__ import annotations

from datetime import datetime, time
from typing import Dict, List, Optional

import re

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QColor
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
    save_product,
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


    def _disable_spinbox_arrows(self) -> None:
        for widget_name in (
            "material_qty",
            "material_min_qty",
            "material_cost",
            "design_product_price",
            "design_qty_produced",
            "design_labor_cost",
            "design_packaging_cost",
            "design_other_cost",
            "design_profit_pct",
            "bom_qty_input",
            "order_qty_input",
            "order_labor_input",
            "order_overhead_input",
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
        self.material_edit_btn = QPushButton()
        self.material_cancel_edit_btn = QPushButton()
        self.material_delete_btn = QPushButton()
        self.material_clear_btn = QPushButton()
        self.material_restock_btn = QPushButton()
        self.material_edit_indicator = QLabel()
        self.material_save_btn.clicked.connect(self._save_material)
        self.material_edit_btn.clicked.connect(self._start_edit_material)
        self.material_cancel_edit_btn.clicked.connect(self._clear_material_form)
        self.material_delete_btn.clicked.connect(self._delete_material)
        self.material_clear_btn.clicked.connect(self._clear_material_form)
        self.material_restock_btn.clicked.connect(self._restock_material)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        actions_row.addWidget(self.material_clear_btn)
        actions_row.addWidget(self.material_edit_btn)
        actions_row.addWidget(self.material_cancel_edit_btn)
        actions_row.addWidget(self.material_save_btn)
        actions_row.addWidget(self.material_restock_btn)
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
        self.design_product_name = QLineEdit()
        self.design_product_sku = QLineEdit()
        self.design_product_price = QDoubleSpinBox(); self.design_product_price.setRange(0, 999999); self.design_product_price.setDecimals(2)
        self.design_qty_produced = QDoubleSpinBox(); self.design_qty_produced.setRange(0, 999999); self.design_qty_produced.setDecimals(3)
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
            ("product_name_ar", self.design_product_name),
            ("design_name", self.bom_name_input),
            ("sku_code", self.design_product_sku),
            ("selling_price", self.design_product_price),
            ("qty_produced", self.design_qty_produced),
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
        self.bom_qty_input = QDoubleSpinBox(); self.bom_qty_input.setRange(0.001, 999999); self.bom_qty_input.setDecimals(3)
        self.add_bom_line_btn = QPushButton("Add Material")
        self.add_bom_line_btn.clicked.connect(self._add_bom_line)
        self.bom_material_label = QLabel()
        self.bom_qty_label = QLabel()
        add_line_layout.addWidget(self.bom_material_label); add_line_layout.addWidget(self.bom_material_combo)
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
        self.summary_extra_cost = QLabel("0.00")
        self.summary_total_cost = QLabel("0.00")
        self.summary_selling_price = QLabel("0.00")
        self.summary_profit = QLabel("0.00")
        self.summary_margin = QLabel("0.00%")
        self.summary_material_cost_label = QLabel()
        self.summary_extra_cost_label = QLabel()
        self.summary_total_cost_label = QLabel()
        self.summary_selling_price_label = QLabel()
        self.summary_profit_label = QLabel()
        self.summary_margin_label = QLabel()
        cost_layout.addRow(self.summary_material_cost_label, self.summary_material_cost)
        cost_layout.addRow(self.summary_extra_cost_label, self.summary_extra_cost)
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
        self.duplicate_design_btn = QPushButton("Duplicate Design")
        self.edit_product_btn = QPushButton("Edit Product")
        self.cancel_edit_btn = QPushButton("Cancel Edit")
        self.cancel_edit_btn.setVisible(False)
        self.editing_product_label = QLabel("")
        self.bom_delete_btn = QPushButton()
        self.bom_clear_btn = QPushButton()
        self.bom_save_btn.clicked.connect(self._save_bom)
        self.duplicate_design_btn.clicked.connect(self._open_duplicate_design_picker)
        self.edit_product_btn.clicked.connect(self._open_edit_product_picker)
        self.cancel_edit_btn.clicked.connect(self._cancel_edit_product)
        self.bom_delete_btn.clicked.connect(self._delete_bom)
        self.bom_clear_btn.clicked.connect(self._clear_bom_form)

        footer = QHBoxLayout(); footer.addStretch(1)
        footer.addWidget(self.editing_product_label)
        footer.addWidget(self.cancel_edit_btn)
        footer.addWidget(self.bom_clear_btn); footer.addWidget(self.duplicate_design_btn); footer.addWidget(self.edit_product_btn); footer.addWidget(self.bom_save_btn)
        tab_layout.addLayout(footer)

        self.tabs.addTab(self.boms_tab, "")

        self._selected_bom_id: Optional[int] = None
        self.design_qty_produced.valueChanged.connect(self._refresh_design_cost_summary)
        self.design_product_name.textEdited.connect(self._suggest_design_name)
        self.design_labor_cost.valueChanged.connect(self._refresh_design_cost_summary)
        self.design_packaging_cost.valueChanged.connect(self._refresh_design_cost_summary)
        self.design_other_cost.valueChanged.connect(self._refresh_design_cost_summary)
        self.design_product_price.valueChanged.connect(self._refresh_design_cost_summary)
        self._refresh_design_cost_summary()

    def _suggest_design_name(self, product_name: str) -> None:
        """Suggest a design name without overwriting a name entered by the user."""
        if product_name.strip() and not self.bom_name_input.text().strip():
            self.bom_name_input.setText(f"{product_name.strip()} - Design")

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
        self.status_legend_label = QLabel("")
        form_container = BaseTabContainer(show_header=False)
        form_content = QWidget()
        form_content_layout = QVBoxLayout(form_content)
        form_content_layout.setSpacing(12)
        form_content_layout.addWidget(form_box)
        form_content_layout.addWidget(self.status_legend_label)
        form_content_layout.addWidget(self.shortage_label)
        form_container.set_page_content_widget(form_content)
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
        self._status_colors = {
            "draft": QColor("#B7791F"),
            "confirmed": QColor("#1D4ED8"),
            "done": QColor("#15803D"),
        }

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

        self._refresh_bom_combo()

    def _refresh_bom_combo(self) -> None:
        if not hasattr(self, "order_bom_combo") or not hasattr(self, "order_product_combo"):
            return
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
            self._paint_status_cell(self.orders_table.item(row, 2), order.status)
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

    def _restock_material(self) -> None:
        if not self._selected_material_id:
            QMessageBox.warning(self, t("common.select", language=self._language), "Select a material first.")
            return
        amount, ok = QInputDialog.getDouble(
            self,
            "Restock Material",
            "Restock Quantity",
            0.0,
            0.001,
            999999.0,
            3,
        )
        if not ok:
            return
        new_qty = float(self.material_qty.value()) + float(amount)
        save_material(
            self._selected_material_id,
            self.material_name_ar.text().strip(),
            self.material_name_en.text().strip(),
            self.material_code.text().strip(),
            new_qty,
            self.material_unit.text().strip(),
            float(self.material_min_qty.value()),
            float(self.material_cost.value()),
        )
        self.material_qty.setValue(new_qty)
        QMessageBox.information(self, t("common.saved_title", language=self._language), "Material restocked.")
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


    def _start_edit_material(self) -> None:
        if not self._selected_material_id:
            QMessageBox.warning(self, t("common.select", language=self._language), "Select a material first.")
            return
        self._editing_material_id = self._selected_material_id
        self._update_material_edit_ui()

    def _update_material_edit_ui(self) -> None:
        in_edit_mode = self._editing_material_id is not None
        self.material_save_btn.setText(("تحديث خامة" if self._language == "ar" else "Update Material") if in_edit_mode else ("حفظ خامة" if self._language == "ar" else "Save Material"))
        self.material_edit_btn.setEnabled(not in_edit_mode)
        self.material_cancel_edit_btn.setVisible(in_edit_mode)
        if in_edit_mode:
            name = self.material_name_en.text().strip() or self.material_name_ar.text().strip() or "-"
            self.material_edit_indicator.setText(f"Editing Material: {name}")
        else:
            self.material_edit_indicator.clear()

    def _load_material(self, row: int) -> None:
        self._selected_material_id = self.materials_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self._editing_material_id = None
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
        qty_produced = float(self.design_qty_produced.value()) if hasattr(self, "design_qty_produced") else 0.0
        materials = {m.id: m for m in list_materials()}
        material_total_cost = 0.0
        for row in range(self.bom_lines_table.rowCount()):
            material_id = self.bom_lines_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            qty_used = float(self.bom_lines_table.item(row, 2).text())
            material = materials.get(material_id)
            if not material:
                continue
            line_total_qty = qty_used * qty_produced
            line_total_cost = line_total_qty * material.cost_per_unit
            material_total_cost += line_total_cost
            self.bom_lines_table.setItem(row, 1, QTableWidgetItem(f"{material.qty_on_hand:.3f}"))
            self.bom_lines_table.setItem(row, 3, QTableWidgetItem(f"{material.cost_per_unit:.2f}"))
            self.bom_lines_table.setItem(row, 4, QTableWidgetItem(f"{line_total_cost:.2f}"))
        extra_cost = float(self.design_labor_cost.value() + self.design_packaging_cost.value() + self.design_other_cost.value())
        total_cost = material_total_cost + extra_cost
        selling_price = float(self.design_product_price.value())
        profit = selling_price - total_cost
        margin = (profit / selling_price * 100.0) if selling_price > 0 else 0.0
        self.summary_material_cost.setText(f"{material_total_cost:.2f}")
        self.summary_extra_cost.setText(f"{extra_cost:.2f}")
        self.summary_total_cost.setText(f"{total_cost:.2f}")
        self.summary_selling_price.setText(f"{selling_price:.2f}")
        self.summary_profit.setText(f"{profit:.2f}")
        self.summary_margin.setText(f"{margin:.2f}%")

    def _save_bom(self) -> None:
        name = self.design_product_name.text().strip()
        sku = self.design_product_sku.text().strip()
        design_name = self.bom_name_input.text().strip()
        qty_produced = float(self.design_qty_produced.value())
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
        if qty_produced <= 0:
            QMessageBox.warning(self, "Validation", "Qty produced must be greater than zero.")
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

        saved_product_id = save_product(
            existing.id if existing else None,
            name_ar=name,
            name_en=existing.name_en if existing else name,
            sku=sku,
            barcode=existing.barcode if existing else "",
            barcode_type=existing.barcode_type if existing else "",
            price=float(self.design_product_price.value()),
            qty_on_hand=existing.qty_on_hand if existing else 0.0,
            min_qty=existing.min_qty if existing else 0.0,
            category=existing.category if existing else "Handmade",
            handmade_flag=existing.handmade_flag if existing else True,
            stone_type=existing.stone_type if existing else "",
            color=existing.color if existing else "",
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
        save_bom(
            self._selected_bom_id,
            product_id,
            design_name,
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
        self._refresh_design_cost_summary()
        self._cancel_edit_product()



    def _open_edit_product_picker(self) -> None:
        products = list_products()
        if not products:
            QMessageBox.information(self, "Edit Product", "No products available.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Product")
        layout = QVBoxLayout(dialog)
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search by product name or SKU/code")
        results = QListWidget()
        buttons = QHBoxLayout()
        open_btn = QPushButton("Load")
        cancel_btn = QPushButton("Cancel")
        buttons.addStretch(1)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(open_btn)
        layout.addWidget(search_input)
        layout.addWidget(results, 1)
        layout.addLayout(buttons)

        def populate(filter_text: str = "") -> None:
            results.clear()
            text = filter_text.strip().lower()
            for product in products:
                name = (product.name_en or "").strip()
                sku = (product.sku or "").strip()
                if text and text not in name.lower() and text not in sku.lower():
                    continue
                item = QListWidgetItem(f"{name} | SKU: {sku or '-'}")
                item.setData(Qt.ItemDataRole.UserRole, product.id)
                results.addItem(item)

        def accept_selected() -> None:
            if results.currentItem() is None:
                return
            dialog.accept()

        search_input.textChanged.connect(populate)
        open_btn.clicked.connect(accept_selected)
        cancel_btn.clicked.connect(dialog.reject)
        results.itemDoubleClicked.connect(lambda _: accept_selected())
        populate()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = results.currentItem()
        if selected is None:
            return
        self._load_product_for_edit(int(selected.data(Qt.ItemDataRole.UserRole)))

    def _load_product_for_edit(self, product_id: int) -> None:
        product = next((p for p in list_products() if p.id == product_id), None)
        if not product:
            QMessageBox.warning(self, "Edit Product", "Could not load selected product.")
            return
        bom = next((b for b in list_boms() if b.product_id == product.id), None)
        self._editing_product_id = product.id
        self.design_product_name.setText(product.name_en or "")
        self.design_product_sku.setText(product.sku or "")
        self.design_product_price.setValue(float(product.price or 0.0))
        product_index = self.bom_product_combo.findData(product.id)
        if product_index >= 0:
            self.bom_product_combo.setCurrentIndex(product_index)
        self.bom_lines_table.setRowCount(0)
        if bom:
            self._selected_bom_id = bom.id
            self.bom_name_input.setText(bom.name)
            self.bom_active_check.setChecked(bom.active)
            for line in list_bom_lines(bom.id):
                material_label = next((label for label, mid in self._material_map.items() if mid == line.material_id), f"{t('manufacturing.material_label', language=self._language)} {line.material_id}")
                row_idx = self.bom_lines_table.rowCount()
                self.bom_lines_table.insertRow(row_idx)
                self.bom_lines_table.setItem(row_idx, 0, QTableWidgetItem(material_label))
                self.bom_lines_table.setItem(row_idx, 1, QTableWidgetItem("0.000"))
                self.bom_lines_table.setItem(row_idx, 2, QTableWidgetItem(f"{line.qty_required:.3f}"))
                self.bom_lines_table.setItem(row_idx, 3, QTableWidgetItem("0.00"))
                self.bom_lines_table.setItem(row_idx, 4, QTableWidgetItem("0.00"))
                self.bom_lines_table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, line.material_id)
        order = next((o for o in reversed(list_production_orders()) if o.product_id == product.id), None)
        if order:
            self.design_qty_produced.setValue(float(order.qty_to_produce or 1.0))
            self.design_labor_cost.setValue(float(order.labor_cost or 0.0))
            self.design_packaging_cost.setValue(float(order.overhead_cost or 0.0))
            self.design_other_cost.setValue(0.0)
        self.editing_product_label.setText(f"Editing Product: {product.name_en}")
        self.cancel_edit_btn.setVisible(True)
        self._refresh_design_cost_summary()

    def _cancel_edit_product(self) -> None:
        self._editing_product_id = None
        self.editing_product_label.setText("")
        self.cancel_edit_btn.setVisible(False)

    def _load_bom(self, row: int) -> None:
        self._selected_bom_id = self.boms_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        bom = next((b for b in list_boms() if b.id == self._selected_bom_id), None)
        if not bom:
            return
        product = next((p for p in list_products() if p.id == bom.product_id), None)
        if product:
            self._editing_product_id = product.id
            self.design_product_name.setText(product.name_ar or product.name_en or "")
            self.design_product_sku.setText(product.sku or "")
            self.design_product_price.setValue(float(product.price or 0.0))
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
            self.bom_lines_table.setItem(row_idx, 1, QTableWidgetItem("0.000"))
            self.bom_lines_table.setItem(row_idx, 2, QTableWidgetItem(f"{line.qty_required:.3f}"))
            self.bom_lines_table.setItem(row_idx, 3, QTableWidgetItem("0.00"))
            self.bom_lines_table.setItem(row_idx, 4, QTableWidgetItem("0.00"))
            self.bom_lines_table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, line.material_id)
        self._refresh_design_cost_summary()

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
        if not source_order or not source_order.bom_id:
            self.usage_box.setVisible(False)
            return
        for line in list_bom_lines(source_order.bom_id):
            material = next((m for m in list_materials() if m.id == line.material_id), None)
            material_name = (
                choose_name(material.name_ar, material.name_en, language=self._language)
                if material
                else f"{t('manufacturing.material_label', language=self._language)} {line.material_id}"
            )
            row_idx = self.usage_table.rowCount()
            self.usage_table.insertRow(row_idx)
            self.usage_table.setItem(row_idx, 0, QTableWidgetItem(material_name))
            self.usage_table.setItem(row_idx, 1, QTableWidgetItem(f"{line.qty_required:.3f}"))
            self.usage_table.setItem(row_idx, 2, QTableWidgetItem(f"{line.unit_cost:.2f}"))
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
        orders = list_production_orders()
        if not orders:
            QMessageBox.information(self, "Duplicate Design", "No previous designs available.")
            return
        choices: list[tuple[str, str]] = []
        for order in orders:
            product_name = next((p.name_en for p in list_products() if p.id == order.product_id), f"Product {order.product_id}")
            label = f"{order.created_at:%Y-%m-%d %H:%M} | {product_name} | {order.order_no}"
            choices.append((label, order.order_no))
        selected_label, ok = QInputDialog.getItem(
            self,
            "Duplicate Design",
            "Select a previous design:",
            [label for label, _ in choices],
            0,
            False,
        )
        if not ok or not selected_label:
            return
        selected_order_no = next((order_no for label, order_no in choices if label == selected_label), None)
        if not selected_order_no:
            QMessageBox.warning(self, "Duplicate Design", "Missing history reference.")
            return
        self._duplicate_design_from_order(selected_order_no)

    def _duplicate_design_from_order(self, order_no: str) -> None:
        source_order = next((o for o in list_production_orders() if o.order_no == order_no), None)
        if not source_order:
            QMessageBox.warning(self, "Duplicate Design", "Could not load selected design history.")
            return
        source_product = next((p for p in list_products() if p.id == source_order.product_id), None)
        if not source_product:
            QMessageBox.warning(self, "Duplicate Design", "Could not load source product.")
            return

        self._cancel_edit_product()
        self.design_product_name.setText(source_product.name_en)
        product_index = self.bom_product_combo.findData(source_product.id)
        if product_index >= 0:
            self.bom_product_combo.setCurrentIndex(product_index)
        self._selected_bom_id = None
        self.design_product_sku.clear()
        self.design_product_price.setValue(float(source_product.price or 0.0))
        self.design_qty_produced.setValue(1.0)
        self.design_labor_cost.setValue(float(source_order.labor_cost or 0.0))
        overhead_cost = float(source_order.overhead_cost or 0.0)
        self.design_packaging_cost.setValue(overhead_cost)
        self.design_other_cost.setValue(0.0)
        self.bom_name_input.setText(f"{source_product.name_en} Design Copy")
        self.bom_active_check.setChecked(True)
        self.bom_lines_table.setRowCount(0)
        if source_order.bom_id:
            for line in list_bom_lines(source_order.bom_id):
                material_label = next(
                    (label for label, mid in self._material_map.items() if mid == line.material_id),
                    f"{t('manufacturing.material_label', language=self._language)} {line.material_id}",
                )
                row_idx = self.bom_lines_table.rowCount()
                self.bom_lines_table.insertRow(row_idx)
                self.bom_lines_table.setItem(row_idx, 0, QTableWidgetItem(material_label))
                self.bom_lines_table.setItem(row_idx, 1, QTableWidgetItem("0.000"))
                self.bom_lines_table.setItem(row_idx, 2, QTableWidgetItem(f"{line.qty_required:.3f}"))
                self.bom_lines_table.setItem(row_idx, 3, QTableWidgetItem("0.00"))
                self.bom_lines_table.setItem(row_idx, 4, QTableWidgetItem("0.00"))
                self.bom_lines_table.item(row_idx, 0).setData(Qt.ItemDataRole.UserRole, line.material_id)
        self._refresh_design_cost_summary()

        self.tabs.setCurrentIndex(0)
        QMessageBox.information(self, "Duplicate Design", "Design copied. Review details then create product.")

    def _paint_status_cell(self, item: QTableWidgetItem, status: str) -> None:
        color = self._status_colors.get(status)
        if color:
            item.setForeground(color)

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
        self.tabs.setTabText(0, "Design")
        self.tabs.setTabText(1, "الخامات" if language == "ar" else "Materials")
        self.tabs.setTabText(2, "السجل" if language == "ar" else "History")
        self.materials_box.setTitle(t("manufacturing.materials_box", language=language))
        self.material_name_ar_label.setText(t("manufacturing.material_name_ar", language=language))
        self.material_name_en_label.setText(t("manufacturing.material_name_en", language=language))
        self.material_code_label.setText(t("manufacturing.material_code", language=language))
        self.material_qty_label.setText(t("manufacturing.material_qty", language=language))
        self.material_unit_label.setText(t("manufacturing.material_unit", language=language))
        self.material_min_qty_label.setText(t("manufacturing.material_min_qty", language=language))
        self.material_cost_label.setText(t("manufacturing.material_cost", language=language))
        self.material_restock_btn.setText("إعادة تعبئة خامة" if language == "ar" else "Restock Material")
        self.material_delete_btn.setText("حذف خامة" if language == "ar" else "Delete Material")
        self.material_clear_btn.setText("إضافة خامة" if language == "ar" else "Add Material")
        self.material_edit_btn.setText("تعديل خامة" if language == "ar" else "Edit Material")
        self.material_cancel_edit_btn.setText("Cancel Edit")
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
        self.tabs.setTabText(0, "إنشاء تصميم" if language == "ar" else "Create Design")
        self.bom_box.setTitle("المنتج النهائي" if language == "ar" else "Final Product")
        self._design_field_labels["product"].setText(t("manufacturing.bom_product", language=language))
        self._design_field_labels["product_name_ar"].setText("اسم المنتج بالعربية" if language == "ar" else "Product Name Arabic")
        self._design_field_labels["sku_code"].setText("الرمز/الكود" if language == "ar" else "SKU/Code")
        self._design_field_labels["selling_price"].setText("سعر البيع" if language == "ar" else "Selling Price")
        self._design_field_labels["qty_produced"].setText("الكمية المنتجة" if language == "ar" else "Qty Produced")
        self._design_field_labels["labor_cost"].setText("تكلفة العمالة" if language == "ar" else "Labor Cost")
        self._design_field_labels["packaging_cost"].setText("تكلفة التغليف" if language == "ar" else "Packaging Cost")
        self._design_field_labels["other_cost"].setText("تكلفة أخرى" if language == "ar" else "Other Cost")
        self.bom_product_label.setText(t("manufacturing.bom_product", language=language))
        self.bom_name_label.setText("اسم التصميم" if language == "ar" else "Design Name")
        self.bom_name_label.setToolTip("أدخل اسمًا واضحًا للتصميم." if language == "ar" else "Enter a clear name for this design.")
        self.bom_active_check.setText(t("manufacturing.bom_active", language=language))
        self.lines_box.setTitle("الخامات المستخدمة" if language == "ar" else "Materials Used")
        self.bom_material_label.setText("الخامة" if language == "ar" else "Material")
        self.bom_qty_label.setText("الكمية المستخدمة" if language == "ar" else "Qty Used")
        self.add_bom_line_btn.setText("إضافة خامة" if language == "ar" else "Add Material")
        self.bom_lines_table.setHorizontalHeaderLabels(["الخامة", "الكمية المتاحة", "الكمية المستخدمة", "تكلفة الوحدة", "التكلفة الإجمالية"] if language == "ar" else ["Material", "Available Qty", "Qty Used", "Unit Cost", "Total Cost"])
        self.remove_line_btn.setText("حذف خامة" if language == "ar" else "Remove Material")
        self.cost_summary_box.setTitle("ملخص التكلفة" if language == "ar" else "Cost Summary")
        self.summary_material_cost_label.setText("تكلفة الخامات" if language == "ar" else "Material Cost")
        self.summary_extra_cost_label.setText("تكلفة إضافية" if language == "ar" else "Extra Cost")
        self.summary_total_cost_label.setText("التكلفة الإجمالية" if language == "ar" else "Total Cost")
        self.summary_selling_price_label.setText("سعر البيع" if language == "ar" else "Selling Price")
        self.summary_profit_label.setText("الربح" if language == "ar" else "Profit")
        self.summary_margin_label.setText("هامش %" if language == "ar" else "Margin %")
        self.bom_save_btn.setText("حفظ التصميم" if language == "ar" else "Save Design")
        self.duplicate_design_btn.setText("تكرار التصميم" if language == "ar" else "Duplicate Design")
        self.edit_product_btn.setText("تعديل المنتج" if language == "ar" else "Edit Product")
        self.cancel_edit_btn.setText("Cancel Edit")
        self.bom_delete_btn.setText(t("manufacturing.delete_bom", language=language))
        self.bom_clear_btn.setText("Clear")
        self.boms_table.setHorizontalHeaderLabels(
            [
                t("manufacturing.bom_table_product", language=language),
                t("manufacturing.bom_table_name", language=language),
                t("manufacturing.bom_table_active", language=language),
            ]
        )
        if hasattr(self, "orders_box"):
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
            self.status_legend_label.setText("الحالات: Draft (مسودة) / Confirmed (تم التأكيد) / Done (مكتمل)")
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
        self.history_help.setText("3 steps: 1) Add materials. 2) Build a workshop design. 3) Create product and review history.")
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
