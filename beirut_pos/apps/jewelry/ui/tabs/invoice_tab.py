"""Invoice tab for Jewelry app."""

from __future__ import annotations

import math
import logging
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QDate, QElapsedTimer, QEvent, QSettings, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QHeaderView,
    QSizePolicy,
    QSpinBox,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QFrame,
    QCheckBox,
    QInputDialog,
    QDialog,
)

from .base_tab import BaseTabContainer
from ...services.db import (
    JewelryInvoiceItem,
    create_invoice,
    fetch_invoice_details,
    find_product_by_code,
    get_loyalty_balance,
    list_active_statuses,
    list_delivery_companies,
    list_payment_methods,
    list_product_categories,
    list_products,
    create_order_payment,
    recalculate_invoice_payment_totals,
    search_customers,
    save_customer,
    get_conn,
)
from ...services.pdf_exports import GalleryInfo, export_invoice_pdf
from ...services.receipt import build_receipt_text
from ...services.session import get_current_user
from ...services.settings import load_gallery_settings
from ...services.i18n import choose_name, get_ui_language, t
from beirut_pos.services.printer import printer
from ..date_utils import to_iso_date
from ..theme import JEWELRY_CONTROLS, JEWELRY_SPACING, JEWELRY_TABLE, JEWELRY_TYPOGRAPHY
from ..dialogs.quick_customer_dialog import QuickCustomerDialog
from .base_tab import BaseTabContainer

logger = logging.getLogger(__name__)


class InvoiceTab(BaseTabContainer):
    ITEM_COL_PRODUCT = 0
    ITEM_COL_CODE = 1
    ITEM_COL_QTY = 2
    ITEM_COL_UNIT_PRICE = 3
    ITEM_COL_LINE_TOTAL = 4
    ITEM_COL_DECREMENT = 5
    ITEM_COL_INCREMENT = 6

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("jewelryInvoiceTab")
        self._last_invoice_no: Optional[str] = None
        self._products = []
        self._scan_buffer = ""
        self._scan_timer = QElapsedTimer()
        self._scan_timer.start()
        self._current_grand_total = 0.0
        self._pay_now_manual = False
        self._pay_now_updating = False
        self._payment_statuses_enabled = False
        self._delivery_statuses_enabled = False
        self._gallery_settings = load_gallery_settings()
        self._website_orders_enabled = self._gallery_settings.website_orders_enabled
        self._language = get_ui_language()
        self._loyalty_points_per_100 = 1.0
        self._loyalty_alert_threshold = 0
        self._load_loyalty_settings()
        QApplication.instance().installEventFilter(self)
        self._category_buttons: dict[Optional[str], QPushButton] = {}
        self._categories: List[str] = []
        self._active_category: Optional[str] = None
        self._instant_invoice_mode = False
        self._recent_scans: list[str] = []

        content = QWidget()
        layout = QHBoxLayout(content)
        self.set_page_content_widget(content)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        self.invoice_info_label = QLabel()

        form_box = QGroupBox()
        self.form_box = form_box
        self._form_layout = QFormLayout(form_box)
        self._form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self._form_layout.setHorizontalSpacing(JEWELRY_SPACING.sm)
        self._form_layout.setVerticalSpacing(JEWELRY_SPACING.xs)
        self._form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.cashier_input = QLineEdit()
        self.cashier_input.setReadOnly(True)
        self.txn_type_combo = QComboBox()
        self.txn_type_combo.addItems(["", ""])
        self.payment_combo = QComboBox()
        self.payment_combo.currentTextChanged.connect(self._refresh_summary_labels)
        self.order_source_combo = QComboBox()
        self.order_source_combo.addItem("", "in_store")
        self.order_source_combo.addItem("", "website")
        self.order_source_combo.currentIndexChanged.connect(self._handle_order_source_change)
        self.delivery_enabled_checkbox = QCheckBox()
        self.delivery_enabled_checkbox.toggled.connect(self._update_delivery_state)
        self.delivery_company_combo = QComboBox()
        self.delivery_company_combo.currentIndexChanged.connect(self._handle_delivery_company_change)
        self.delivery_fee_input = QDoubleSpinBox()
        self.delivery_fee_input.setRange(0, 999999)
        self.delivery_fee_input.setDecimals(2)
        self.delivery_fee_input.valueChanged.connect(self._recalculate_totals)
        self.delivery_address_input = QLineEdit()
        self.delivery_status_combo = QComboBox()
        self.delivery_panel = QWidget()
        delivery_layout = QFormLayout(self.delivery_panel)
        delivery_layout.setContentsMargins(0, 0, 0, 0)
        delivery_layout.setHorizontalSpacing(JEWELRY_SPACING.sm)
        delivery_layout.setVerticalSpacing(JEWELRY_SPACING.xs)
        self.delivery_company_label = QLabel()
        self.delivery_fee_label = QLabel()
        self.delivery_address_label = QLabel()
        self.delivery_status_label = QLabel()
        delivery_layout.addRow(self.delivery_company_label, self.delivery_company_combo)
        delivery_layout.addRow(self.delivery_fee_label, self.delivery_fee_input)
        delivery_layout.addRow(self.delivery_address_label, self.delivery_address_input)
        delivery_layout.addRow(self.delivery_status_label, self.delivery_status_combo)
        self.website_order_label = QLabel()
        self.website_order_input = QLineEdit()
        self.website_order_input.setEnabled(False)
        self.website_order_panel = QWidget()
        website_layout = QFormLayout(self.website_order_panel)
        website_layout.setContentsMargins(0, 0, 0, 0)
        website_layout.setHorizontalSpacing(JEWELRY_SPACING.sm)
        website_layout.setVerticalSpacing(JEWELRY_SPACING.xs)
        website_layout.addRow(self.website_order_label, self.website_order_input)
        self.discount_type_combo = QComboBox()
        self.discount_type_combo.addItem("", "amount")
        self.discount_type_combo.addItem("", "percent")
        self.discount_type_combo.currentIndexChanged.connect(self._handle_discount_type_change)
        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0, 999999)
        self.discount_input.setDecimals(2)
        self.discount_input.valueChanged.connect(self._recalculate_totals)
        self.discount_panel = QWidget()
        discount_layout = QFormLayout(self.discount_panel)
        discount_layout.setContentsMargins(0, 0, 0, 0)
        discount_layout.setHorizontalSpacing(JEWELRY_SPACING.sm)
        discount_layout.setVerticalSpacing(JEWELRY_SPACING.xs)
        self.discount_type_label = QLabel()
        self.discount_value_label = QLabel()
        discount_layout.addRow(self.discount_type_label, self.discount_type_combo)
        discount_layout.addRow(self.discount_value_label, self.discount_input)
        self.customer_search_input = QLineEdit()
        self.customer_search_input.textChanged.connect(self._queue_customer_search)
        self.customer_search_timer = QTimer(self)
        self.customer_search_timer.setSingleShot(True)
        self.customer_search_timer.setInterval(250)
        self.customer_search_timer.timeout.connect(self._perform_customer_search)
        self.customer_dropdown_frame = QFrame()
        self.customer_dropdown_frame.setObjectName("customerDropdown")
        self.customer_dropdown_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.customer_dropdown_frame.setVisible(False)
        dropdown_layout = QVBoxLayout(self.customer_dropdown_frame)
        dropdown_layout.setContentsMargins(6, 6, 6, 6)
        dropdown_layout.setSpacing(JEWELRY_SPACING.xxs)
        self.customer_dropdown = QListWidget()
        self.customer_dropdown.setMaximumHeight(160)
        self.customer_dropdown.setAlternatingRowColors(True)
        self.customer_dropdown.itemClicked.connect(self._select_customer_from_dropdown)
        self.customer_dropdown.itemActivated.connect(self._select_customer_from_dropdown)
        self.customer_no_results_label = QLabel()
        self.customer_create_btn = QPushButton()
        self.customer_create_btn.clicked.connect(self._create_new_customer_from_search)
        dropdown_layout.addWidget(self.customer_dropdown)
        dropdown_layout.addWidget(self.customer_no_results_label)
        dropdown_layout.addWidget(self.customer_create_btn)
        self.customer_no_results_label.setVisible(False)
        self.customer_create_btn.setVisible(False)
        customer_search_container = QWidget()
        customer_search_layout = QVBoxLayout(customer_search_container)
        customer_search_layout.setContentsMargins(0, 0, 0, 0)
        customer_search_layout.setSpacing(JEWELRY_SPACING.xxs)
        customer_search_row = QWidget()
        customer_search_row_layout = QHBoxLayout(customer_search_row)
        customer_search_row_layout.setContentsMargins(0, 0, 0, 0)
        customer_search_row_layout.setSpacing(JEWELRY_SPACING.xs)
        self.customer_add_new_btn = QPushButton("Add New Customer")
        self.customer_add_new_btn.clicked.connect(self._open_quick_customer_dialog)
        customer_search_row_layout.addWidget(self.customer_search_input, 1)
        customer_search_row_layout.addWidget(self.customer_add_new_btn)
        customer_search_layout.addWidget(customer_search_row)
        customer_search_layout.addWidget(self.customer_dropdown_frame)
        self.customer_name_input = QLineEdit()
        self.customer_phone_input = QLineEdit()
        self.customer_email_input = QLineEdit()
        self.customer_notes_input = QLineEdit()
        self.customer_points_label = QLabel("0")
        self.customer_search_input.installEventFilter(self)
        self.customer_dropdown.installEventFilter(self)
        self.customer_name_input.textChanged.connect(self._clear_customer_selection)
        self.customer_phone_input.textChanged.connect(self._clear_customer_selection)
        self.customer_email_input.textChanged.connect(self._clear_customer_selection)
        self.customer_name_input.textChanged.connect(self._update_validation_state)
        self.customer_phone_input.textChanged.connect(self._update_validation_state)
        self.loyalty_redeem_input = QDoubleSpinBox()
        self.loyalty_redeem_input.setDecimals(2)
        self.loyalty_redeem_input.setRange(0, 999999)
        self.loyalty_redeem_input.valueChanged.connect(self._recalculate_totals)
        self.loyalty_earned_label = QLabel("0")
        self.customer_save_btn = QPushButton()
        self.customer_save_btn.clicked.connect(self._save_customer_profile)
        self.notes_input = QTextEdit()
        self.notes_input.setMinimumHeight(80)
        self.notes_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.notes_panel = QWidget()
        notes_layout = QFormLayout(self.notes_panel)
        notes_layout.setContentsMargins(0, 0, 0, 0)
        notes_layout.setHorizontalSpacing(JEWELRY_SPACING.sm)
        notes_layout.setVerticalSpacing(JEWELRY_SPACING.xs)
        self.notes_label = QLabel()
        notes_layout.addRow(self.notes_label, self.notes_input)
        self.return_reason_input = QLineEdit()
        self.return_reason_input.setEnabled(False)
        self.return_panel = QWidget()
        return_layout = QFormLayout(self.return_panel)
        return_layout.setContentsMargins(0, 0, 0, 0)
        return_layout.setHorizontalSpacing(JEWELRY_SPACING.sm)
        return_layout.setVerticalSpacing(JEWELRY_SPACING.xs)
        self.return_reason_label = QLabel()
        return_layout.addRow(self.return_reason_label, self.return_reason_input)
        self.discount_toggle = QPushButton()
        self.notes_toggle = QPushButton()
        self.return_toggle = QPushButton()
        self.website_toggle = QPushButton()
        for toggle in (self.discount_toggle, self.notes_toggle, self.return_toggle, self.website_toggle):
            toggle.setCheckable(True)
            toggle.toggled.connect(self._update_advanced_panels)
        self.txn_type_combo.currentIndexChanged.connect(self._handle_txn_type_change)

        self.cashier_label = QLabel()
        self.transaction_label = QLabel()
        self.payment_method_label = QLabel()
        self.order_source_label = QLabel()
        self.delivery_enabled_label = QLabel()
        self.customer_search_label = QLabel()
        self.customer_name_label = QLabel()
        self.customer_phone_label = QLabel()
        self._form_layout.addRow(self.cashier_label, self.cashier_input)
        self._form_layout.addRow(self.transaction_label, self.txn_type_combo)
        self._form_layout.addRow(self.order_source_label, self.order_source_combo)
        self._form_layout.addRow(self.delivery_enabled_label, self.delivery_enabled_checkbox)
        self._form_layout.addRow("", self.delivery_panel)
        self._form_layout.addRow(self.customer_search_label, customer_search_container)
        self._form_layout.addRow(self.customer_name_label, self.customer_name_input)
        self._form_layout.addRow(self.customer_phone_label, self.customer_phone_input)
        customer_actions = QHBoxLayout()
        customer_actions.addWidget(self.customer_save_btn)
        self._form_layout.addRow("", customer_actions)
        self.loyalty_balance_label = QLabel()
        self.redeem_points_label = QLabel()
        self.points_earned_label = QLabel()
        advanced_controls = QWidget()
        advanced_controls_layout = QHBoxLayout(advanced_controls)
        advanced_controls_layout.setContentsMargins(0, 0, 0, 0)
        advanced_controls_layout.setSpacing(JEWELRY_SPACING.xs)
        advanced_controls_layout.addWidget(self.discount_toggle)
        advanced_controls_layout.addWidget(self.notes_toggle)
        advanced_controls_layout.addWidget(self.return_toggle)
        advanced_controls_layout.addWidget(self.website_toggle)
        advanced_controls_layout.addStretch()
        self.customer_email_label = QLabel()
        self.customer_notes_label = QLabel()
        self.advanced_box = QGroupBox()
        self.advanced_box.setCheckable(True)
        self.advanced_box.setChecked(False)
        self.advanced_box.toggled.connect(self._toggle_advanced_group)
        advanced_box_layout = QVBoxLayout(self.advanced_box)
        advanced_box_layout.setContentsMargins(12, 12, 12, 12)
        advanced_box_layout.setSpacing(JEWELRY_SPACING.xs)
        advanced_box_layout.addWidget(advanced_controls)
        advanced_box_layout.addWidget(self.discount_panel)
        advanced_box_layout.addWidget(self.notes_panel)
        advanced_box_layout.addWidget(self.return_panel)
        advanced_box_layout.addWidget(self.website_order_panel)
        self.advanced_customer_panel = QWidget()
        advanced_customer_layout = QFormLayout(self.advanced_customer_panel)
        advanced_customer_layout.setContentsMargins(0, 0, 0, 0)
        advanced_customer_layout.setHorizontalSpacing(JEWELRY_SPACING.sm)
        advanced_customer_layout.setVerticalSpacing(JEWELRY_SPACING.xs)
        advanced_customer_layout.addRow(self.customer_email_label, self.customer_email_input)
        advanced_customer_layout.addRow(self.customer_notes_label, self.customer_notes_input)
        advanced_customer_layout.addRow(self.loyalty_balance_label, self.customer_points_label)
        advanced_customer_layout.addRow(self.redeem_points_label, self.loyalty_redeem_input)
        advanced_customer_layout.addRow(self.points_earned_label, self.loyalty_earned_label)
        advanced_box_layout.addWidget(self.advanced_customer_panel)
        self._form_layout.addRow(self.advanced_box)
        self.recent_sold_box = QGroupBox()
        self.recent_sold_box.setMinimumHeight(220)
        recent_layout = QVBoxLayout(self.recent_sold_box)
        self.recent_sold_table = QTableWidget(0, 4)
        self.recent_sold_table.setHorizontalHeaderLabels(["", "", "", ""])
        self.recent_sold_table.setAlternatingRowColors(True)
        self.recent_sold_table.setMinimumHeight(180)
        self.recent_sold_table.verticalHeader().setDefaultSectionSize(32)
        recent_header = self.recent_sold_table.horizontalHeader()
        recent_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        recent_header.resizeSection(0, 110)
        recent_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        recent_header.resizeSection(1, 120)
        recent_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        recent_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        recent_layout.addWidget(self.recent_sold_table)
        right_layout.addWidget(self.invoice_info_label)
        right_layout.addWidget(self.recent_sold_box, 2)
        right_layout.addWidget(form_box, 3)

        product_search_panel = QWidget()
        product_search_layout = QGridLayout(product_search_panel)
        product_search_layout.setContentsMargins(0, 0, 0, 0)
        self.barcode_input = QLineEdit()
        self.search_label = QLabel()
        self.barcode_label = QLabel()
        self.instant_invoice_toggle = QCheckBox("فاتورة فورية")
        self.instant_invoice_toggle.toggled.connect(self._set_instant_invoice_mode)
        self.recent_scans_label = QLabel()
        self.barcode_input.setPlaceholderText("")
        self.barcode_input.returnPressed.connect(self._handle_barcode_submit)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("")
        self.search_input.textChanged.connect(self._handle_product_search_change)
        product_search_layout.addWidget(self.instant_invoice_toggle, 0, 0, 1, 3)
        product_search_layout.addWidget(self.search_label, 1, 0)
        product_search_layout.addWidget(self.search_input, 1, 1, 1, 2)
        product_search_layout.addWidget(self.barcode_label, 2, 0)
        product_search_layout.addWidget(self.barcode_input, 2, 1, 1, 2)
        product_search_layout.addWidget(self.recent_scans_label, 3, 0, 1, 3)
        right_layout.addWidget(product_search_panel)
        right_layout.setStretch(1, 2)
        right_layout.setStretch(2, 3)

        self.category_scroll = QScrollArea()
        self.category_scroll.setWidgetResizable(True)
        self.category_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.category_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.category_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.category_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.category_container = QWidget()
        self.category_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.category_layout = QHBoxLayout(self.category_container)
        self.category_layout.setContentsMargins(0, 0, 0, 0)
        self.category_layout.setSpacing(JEWELRY_SPACING.xs)
        self.category_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.category_scroll.setWidget(self.category_container)

        self.products_table = QTableWidget(0, 6)
        self.products_table.setHorizontalHeaderLabels(["", "", "", "", "", ""])
        self.products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.products_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.products_table.setAlternatingRowColors(True)
        self.products_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.products_table.verticalHeader().setDefaultSectionSize(28)
        products_header = self.products_table.horizontalHeader()
        products_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        products_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        products_header.resizeSection(3, 80)
        products_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        products_header.resizeSection(4, 80)
        product_header_height = self.products_table.horizontalHeader().sizeHint().height()
        product_row_height = self.products_table.verticalHeader().defaultSectionSize()
        self.products_table.setMinimumHeight(product_row_height * 8 + product_header_height)
        self.products_table.cellDoubleClicked.connect(self._add_selected_product)
        self.products_table.itemSelectionChanged.connect(self._update_add_state)

        self.qty_input = QSpinBox()
        self.qty_input.setRange(1, 1000)
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self._add_selected_product)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._add_selected_product)

        product_box = QGroupBox()
        self.product_box = product_box
        product_layout = QVBoxLayout(product_box)
        product_layout.addWidget(self.category_scroll)
        product_layout.addWidget(self.products_table)
        qty_row = QHBoxLayout()
        self.qty_label = QLabel()
        qty_row.addWidget(self.qty_label)
        qty_row.addWidget(self.qty_input)
        qty_row.addWidget(self.add_btn)
        qty_row.addStretch()
        product_layout.addLayout(qty_row)

        items_box = QGroupBox()
        self.items_box = items_box
        items_layout = QVBoxLayout(items_box)
        self.items_table = QTableWidget(0, 7)
        self.items_table.setHorizontalHeaderLabels(["", "", "", "", "", "-", "+"])
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.setAlternatingRowColors(True)
        self.items_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.items_table.verticalHeader().setDefaultSectionSize(28)
        items_header = self.items_table.horizontalHeader()
        items_header.setSectionResizeMode(self.ITEM_COL_PRODUCT, QHeaderView.ResizeMode.Stretch)
        for column in (
            self.ITEM_COL_QTY,
            self.ITEM_COL_UNIT_PRICE,
            self.ITEM_COL_LINE_TOTAL,
            self.ITEM_COL_DECREMENT,
            self.ITEM_COL_INCREMENT,
        ):
            items_header.setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            items_header.resizeSection(column, 80 if column <= self.ITEM_COL_LINE_TOTAL else 36)
        items_header_height = self.items_table.horizontalHeader().sizeHint().height()
        items_row_height = self.items_table.verticalHeader().defaultSectionSize()
        self.items_table.setMinimumHeight(items_row_height * 8 + items_header_height)
        items_layout.addWidget(self.items_table)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton()
        self.remove_btn.clicked.connect(self._remove_selected_item)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch()
        items_layout.addLayout(btn_row)

        tables_splitter = QSplitter(Qt.Orientation.Vertical)
        tables_splitter.addWidget(product_box)
        tables_splitter.addWidget(items_box)
        tables_splitter.setStretchFactor(0, 3)
        tables_splitter.setStretchFactor(1, 2)
        right_layout.addWidget(tables_splitter)

        left_container = QWidget()
        left_container.setLayout(left_layout)
        left_container.setMinimumWidth(320)
        splitter.addWidget(left_container)

        totals_box = QGroupBox()
        self.totals_box = totals_box
        totals_layout = QVBoxLayout(totals_box)
        self.total_label = QLabel()
        self.total_label.setObjectName("netTotalLabel")
        totals_layout.addWidget(self.total_label)
        breakdown_title = QLabel()
        breakdown_title.setObjectName("summarySectionTitle")
        totals_layout.addWidget(breakdown_title)
        self.breakdown_title = breakdown_title
        breakdown_frame = QFrame()
        breakdown_layout = QVBoxLayout(breakdown_frame)
        breakdown_layout.setContentsMargins(12, 0, 0, 0)
        breakdown_layout.setSpacing(JEWELRY_SPACING.xxs)
        self.subtotal_label = QLabel()
        self.discount_summary_label = QLabel()
        self.loyalty_summary_label = QLabel()
        breakdown_layout.addWidget(self.subtotal_label)
        breakdown_layout.addWidget(self.discount_summary_label)
        breakdown_layout.addWidget(self.loyalty_summary_label)
        totals_layout.addWidget(breakdown_frame)
        self.payment_summary_label = QLabel()
        totals_layout.addWidget(self.payment_summary_label)
        left_layout.addWidget(totals_box)

        payment_box = QGroupBox()
        payment_layout = QFormLayout(payment_box)
        payment_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        payment_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        payment_layout.setHorizontalSpacing(JEWELRY_SPACING.sm)
        payment_layout.setVerticalSpacing(JEWELRY_SPACING.xs)
        payment_layout.addRow(self.payment_method_label, self.payment_combo)
        self.grand_total_label = QLabel()
        self.grand_total_value = QLabel("0.00")
        self.paid_total_label = QLabel()
        self.paid_total_value = QLabel("0.00")
        self.remaining_total_label = QLabel()
        self.remaining_total_value = QLabel("0.00")
        self.pay_now_label = QLabel()
        self.pay_now_input = QDoubleSpinBox()
        self.pay_now_input.setRange(0, 999999)
        self.pay_now_input.setDecimals(2)
        self.pay_now_input.lineEdit().setReadOnly(True)
        self.pay_now_input.valueChanged.connect(self._handle_pay_now_change)
        self.adjust_pay_now_btn = QPushButton()
        self.adjust_pay_now_btn.clicked.connect(self._toggle_pay_now_manual_mode)
        pay_now_row = QWidget()
        pay_now_row_layout = QHBoxLayout(pay_now_row)
        pay_now_row_layout.setContentsMargins(0, 0, 0, 0)
        pay_now_row_layout.setSpacing(JEWELRY_SPACING.xs)
        pay_now_row_layout.addWidget(self.pay_now_input, 1)
        pay_now_row_layout.addWidget(self.adjust_pay_now_btn)
        self.pay_now_hint_label = QLabel()
        self.payment_due_date_label = QLabel()
        self.payment_due_date_input = QDateEdit()
        self.payment_due_date_input.setCalendarPopup(True)
        self.payment_due_date_input.setDisplayFormat("dd/MM/yyyy")
        self.payment_due_date_input.setDate(QDate.currentDate())
        self.payment_order_status_label = QLabel()
        self.payment_order_status_combo = QComboBox()
        payment_layout.addRow(self.grand_total_label, self.grand_total_value)
        payment_layout.addRow(self.paid_total_label, self.paid_total_value)
        payment_layout.addRow(self.remaining_total_label, self.remaining_total_value)
        payment_layout.addRow(self.pay_now_label, pay_now_row)
        payment_layout.addRow(QLabel(""), self.pay_now_hint_label)
        payment_layout.addRow(self.payment_due_date_label, self.payment_due_date_input)
        payment_layout.addRow(self.payment_order_status_label, self.payment_order_status_combo)
        left_layout.addWidget(payment_box)

        calculator_box = QGroupBox()
        self.calculator_box = calculator_box
        calculator_layout = QVBoxLayout(calculator_box)
        self.calculator_display = QLineEdit("0")
        self.calculator_display.setReadOnly(True)
        self.calculator_display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.calculator_display.setMinimumHeight(JEWELRY_CONTROLS.button_min_height)
        self.calculator_display.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        calculator_layout.addWidget(self.calculator_display)
        keypad_layout = QGridLayout()
        buttons = [
            ("7", 0, 0),
            ("8", 0, 1),
            ("9", 0, 2),
            ("÷", 0, 3),
            ("4", 1, 0),
            ("5", 1, 1),
            ("6", 1, 2),
            ("×", 1, 3),
            ("1", 2, 0),
            ("2", 2, 1),
            ("3", 2, 2),
            ("-", 2, 3),
            ("0", 3, 0),
            (".", 3, 1),
            ("C", 3, 2),
            ("+", 3, 3),
        ]
        for label, row, col in buttons:
            button = QPushButton(label)
            button.clicked.connect(lambda _checked, value=label: self._calculator_button_pressed(value))
            keypad_layout.addWidget(button, row, col)
        equal_button = QPushButton("=")
        equal_button.clicked.connect(self._evaluate_calculator)
        keypad_layout.addWidget(equal_button, 4, 0, 1, 2)
        backspace_button = QPushButton("⌫")
        backspace_button.clicked.connect(self._calculator_backspace)
        keypad_layout.addWidget(backspace_button, 4, 2, 1, 1)
        copy_button = QPushButton()
        copy_button.clicked.connect(self._copy_calculator_result)
        self.copy_button = copy_button
        keypad_layout.addWidget(copy_button, 4, 3, 1, 1)
        calculator_layout.addLayout(keypad_layout)
        actions_layout = QVBoxLayout()
        self.save_btn = QPushButton()
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save_invoice)
        self.validation_label = QLabel("")
        self.validation_label.setProperty("data-role", "helper")
        self.validation_label.setObjectName("validationLabel")
        self.validation_label.setWordWrap(True)
        self.validation_label.setVisible(False)
        self.validation_label.setMinimumHeight(JEWELRY_CONTROLS.field_min_height)
        self.export_btn = QPushButton()
        self.export_btn.clicked.connect(self._export_invoice_pdf)
        self.print_btn = QPushButton()
        self.print_btn.clicked.connect(self._print_invoice)
        self.auto_print_after_save_checkbox = QCheckBox("طباعة تلقائية بعد الحفظ")
        self.print_mode_combo = QComboBox()
        self.print_mode_combo.addItem("Direct printer", "direct")
        self.print_mode_combo.addItem("PDF", "pdf")
        self.print_preview_checkbox = QCheckBox("Quick preview before print")
        self.printer_status_label = QLabel()
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self._clear_invoice)
        print_actions_row = QHBoxLayout()
        print_actions_row.setContentsMargins(0, 0, 0, 0)
        print_actions_row.setSpacing(JEWELRY_SPACING.xs)
        print_actions_row.addWidget(self.export_btn)
        print_actions_row.addWidget(self.print_btn)

        actions_layout.addWidget(self.save_btn)
        actions_layout.addWidget(self.validation_label)
        actions_layout.addLayout(print_actions_row)
        actions_layout.addWidget(self.auto_print_after_save_checkbox)
        actions_layout.addWidget(self.print_mode_combo)
        actions_layout.addWidget(self.print_preview_checkbox)
        actions_layout.addWidget(self.printer_status_label)
        actions_layout.addWidget(self.clear_btn)
        left_layout.addLayout(actions_layout)
        left_layout.addWidget(calculator_box)
        left_layout.addStretch()
        right_container = QWidget()
        right_container.setLayout(right_layout)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 900])

        self._refresh_payment_methods()
        self._refresh_payment_statuses()
        self._refresh_delivery_companies()
        self._refresh_delivery_statuses()
        self.load_categories()
        self.on_category_selected(None)
        self._initialize_cashier()
        self._customer_id: Optional[str] = None
        self._customer_points: float = 0.0
        self._configure_shortcuts()
        self._configure_focus_order()
        self._apply_invoice_styles()
        self._update_advanced_panels()
        self._update_delivery_state(self.delivery_enabled_checkbox.isChecked())
        self._load_print_preferences()
        self._refresh_printer_status_badge()
        self._refresh_recently_sold()
        self.apply_language(self._language)

    def _initialize_cashier(self) -> None:
        user = get_current_user()
        if user:
            self.set_cashier_name(user.full_name)

    def _calculator_button_pressed(self, value: str) -> None:
        if value == "C":
            self.calculator_display.setText("0")
            return
        current = self.calculator_display.text()
        if current in {"0", t("invoice.calc_error", language=self._language)} and value not in {
            "+",
            "-",
            "×",
            "÷",
            ".",
        }:
            self.calculator_display.setText(value)
            return
        if current in {"0", t("invoice.calc_error", language=self._language)} and value == ".":
            self.calculator_display.setText("0.")
            return
        self.calculator_display.setText(f"{current}{value}")

    def _calculator_backspace(self) -> None:
        current = self.calculator_display.text()
        if len(current) <= 1:
            self.calculator_display.setText("0")
        else:
            self.calculator_display.setText(current[:-1])

    def _evaluate_calculator(self) -> None:
        expression = self.calculator_display.text().strip()
        if not expression:
            return
        normalized = expression.replace("×", "*").replace("÷", "/")
        if not all(char in "0123456789.+-*/() " for char in normalized):
            self.calculator_display.setText(t("invoice.calc_error", language=self._language))
            return
        try:
            result = eval(normalized, {"__builtins__": {}}, {})
        except (SyntaxError, ZeroDivisionError, TypeError, ValueError):
            self.calculator_display.setText(t("invoice.calc_error", language=self._language))
            return
        self.calculator_display.setText(f"{result:.2f}".rstrip("0").rstrip("."))

    def _copy_calculator_result(self) -> None:
        result = self.calculator_display.text().strip()
        if not result or result == t("invoice.calc_error", language=self._language):
            return
        QApplication.clipboard().setText(result)

    def set_cashier_name(self, name: str) -> None:
        self.cashier_input.setText(name)

    def _refresh_payment_methods(self) -> None:
        self.payment_combo.clear()
        for _id, name_ar, name_en in list_payment_methods():
            self.payment_combo.addItem(choose_name(name_ar, name_en, language=self._language), _id)
        self._refresh_summary_labels()

    def _payment_status_required(self) -> bool:
        grand_total = max(self._current_grand_total, 0.0)
        pay_now = min(float(self.pay_now_input.value()), grand_total)
        return grand_total > 0 and pay_now < grand_total

    def _refresh_payment_statuses(self, required: Optional[bool] = None) -> None:
        if required is None:
            required = self._payment_status_required()
        selected_id = self.payment_order_status_combo.currentData()
        self.payment_order_status_combo.blockSignals(True)
        self.payment_order_status_combo.clear()
        self.payment_order_status_combo.addItem("", None)
        if required:
            for status in list_active_statuses("PAYMENT"):
                self.payment_order_status_combo.addItem(
                    choose_name(status.name_ar, status.name_en, language=self._language),
                    status.id,
                )
        self.payment_order_status_combo.blockSignals(False)
        if required and selected_id is not None:
            idx = self.payment_order_status_combo.findData(selected_id)
            if idx >= 0:
                self.payment_order_status_combo.setCurrentIndex(idx)
        self._payment_statuses_enabled = required

    def _refresh_delivery_companies(self) -> None:
        self.delivery_company_combo.clear()
        self.delivery_company_combo.addItem("", None)
        for company in list_delivery_companies(include_inactive=False):
            self.delivery_company_combo.addItem(company.name, company.id)
            index = self.delivery_company_combo.count() - 1
            self.delivery_company_combo.setItemData(
                index,
                float(getattr(company, "default_fee", 0.0)),
                Qt.ItemDataRole.UserRole + 1,
            )

    def _refresh_delivery_statuses(self, required: Optional[bool] = None) -> None:
        if required is None:
            required = self.delivery_enabled_checkbox.isChecked()
        selected_id = self.delivery_status_combo.currentData()
        self.delivery_status_combo.blockSignals(True)
        self.delivery_status_combo.clear()
        self.delivery_status_combo.addItem("", None)
        if required:
            for status in list_active_statuses("DELIVERY"):
                self.delivery_status_combo.addItem(
                    choose_name(status.name_ar, status.name_en, language=self._language),
                    status.id,
                )
        self.delivery_status_combo.blockSignals(False)
        if required and selected_id is not None:
            idx = self.delivery_status_combo.findData(selected_id)
            if idx >= 0:
                self.delivery_status_combo.setCurrentIndex(idx)
        self._delivery_statuses_enabled = required

    def _handle_delivery_company_change(self) -> None:
        if not self.delivery_enabled_checkbox.isChecked():
            return
        fee_value = self.delivery_company_combo.currentData(Qt.ItemDataRole.UserRole + 1)
        if fee_value is None:
            return
        self.delivery_fee_input.blockSignals(True)
        self.delivery_fee_input.setValue(float(fee_value))
        self.delivery_fee_input.blockSignals(False)
        self._recalculate_totals()

    def _update_delivery_state(self, enabled: bool) -> None:
        self.delivery_panel.setVisible(enabled)
        self.delivery_panel.setEnabled(enabled)
        self.delivery_company_combo.setEnabled(enabled)
        self.delivery_fee_input.setEnabled(enabled)
        self.delivery_address_input.setEnabled(enabled)
        self.delivery_status_combo.setEnabled(enabled)
        if enabled != self._delivery_statuses_enabled:
            self._refresh_delivery_statuses(required=enabled)
        if not enabled:
            self.delivery_fee_input.blockSignals(True)
            self.delivery_fee_input.setValue(0.0)
            self.delivery_fee_input.blockSignals(False)
        else:
            self._handle_delivery_company_change()
        self._recalculate_totals()

    def _handle_pay_now_change(self) -> None:
        if not self._pay_now_updating and self._pay_now_manual:
            self._pay_now_manual = True
        self._update_payment_totals()

    def _toggle_pay_now_manual_mode(self) -> None:
        if not self.advanced_box.isChecked() and not self._pay_now_manual:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("invoice.advanced_options", language=self._language),
            )
            return
        self._pay_now_manual = not self._pay_now_manual
        self.pay_now_input.lineEdit().setReadOnly(not self._pay_now_manual)
        if not self._pay_now_manual:
            self._set_pay_now_value(self._current_grand_total)
        self._refresh_pay_now_manual_ui()
        self._update_payment_totals()

    def _refresh_pay_now_manual_ui(self) -> None:
        if self._pay_now_manual:
            self.adjust_pay_now_btn.setText(t("invoice.pay_now_manual_disable", language=self._language))
            self.adjust_pay_now_btn.setToolTip(t("invoice.pay_now_manual_disable_tooltip", language=self._language))
            self.pay_now_hint_label.setText(t("invoice.pay_now_hint_partial", language=self._language))
            return
        self.adjust_pay_now_btn.setText(t("invoice.pay_now_manual_enable", language=self._language))
        self.adjust_pay_now_btn.setToolTip(t("invoice.pay_now_manual_enable_tooltip", language=self._language))
        self.pay_now_hint_label.setText(t("invoice.pay_now_hint_default", language=self._language))


    def refresh_products(self, _text: str | None = None) -> None:
        self.load_products(self._active_category, self.search_input.text())

    def load_categories(self) -> None:
        self._categories = list_product_categories()
        self.render_category_buttons()

    def load_products(self, category_id: Optional[str] = None, search_text: str = "") -> None:
        search = search_text.strip()
        self._products = list_products(search=search if search else None, category=category_id)
        self.products_table.setRowCount(0)
        name_font = QFont(self.products_table.font())
        name_font.setPointSize(name_font.pointSize() + 2)
        name_font.setBold(True)
        price_font = QFont(name_font)
        meta_font = QFont(self.products_table.font())
        meta_font.setPointSize(max(1, meta_font.pointSize() - 1))
        for product in self._products:
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            self.products_table.setItem(
                row,
                0,
                QTableWidgetItem(choose_name(product.name_ar, product.name_en, language=self._language)),
            )
            self.products_table.setItem(row, 1, QTableWidgetItem(product.sku))
            self.products_table.setItem(row, 2, QTableWidgetItem(product.barcode))
            self.products_table.setItem(row, 3, QTableWidgetItem(f"{product.price:.2f}"))
            self.products_table.setItem(row, 4, QTableWidgetItem(f"{product.qty_on_hand:.2f}"))
            self.products_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, product.id)
            add_button = QPushButton(t("invoice.add_item", language=self._language))
            add_button.clicked.connect(
                lambda _checked=False, item=product: self._add_product_to_invoice(
                    item, float(self.qty_input.value())
                )
            )
            self.products_table.setCellWidget(row, 5, add_button)

    def render_category_buttons(self) -> None:
        while self.category_layout.count():
            item = self.category_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._category_buttons.clear()
        categories = [None, *self._categories]
        labels = {None: "All Products"}
        for category in categories:
            label = labels.get(category, str(category))
            button = QPushButton(label)
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            button.setStyleSheet(
                "QPushButton { padding: 6px 12px; border-radius: 12px; border: 1px solid #c8c8c8; }"
                "QPushButton:checked { background-color: #2d7dd2; color: white; border-color: #2d7dd2; }"
            )
            button.clicked.connect(
                lambda _checked=False, category_id=category: self.on_category_selected(category_id)
            )
            self.category_layout.addWidget(button)
            self._category_buttons[category] = button
        self.category_layout.addStretch()

    def on_category_selected(self, category_id: Optional[str]) -> None:
        self._active_category = category_id
        for category, button in self._category_buttons.items():
            button.blockSignals(True)
            button.setChecked(category == category_id)
            button.blockSignals(False)
        self.load_products(category_id, self.search_input.text())

    def _handle_product_search_change(self, text: str) -> None:
        self.load_products(self._active_category, text)

    def _handle_txn_type_change(self) -> None:
        is_return = self.txn_type_combo.currentIndex() == 1
        self._update_return_reason_state()
        self.loyalty_redeem_input.setEnabled(not is_return)
        if is_return:
            self.loyalty_redeem_input.setValue(0.0)
        self._refresh_summary_labels()
        self._update_validation_state()

    def _handle_order_source_change(self) -> None:
        if self._website_orders_enabled:
            self.order_source_combo.setCurrentIndex(self.order_source_combo.findData("website"))
        self._update_website_order_state()

    def _apply_website_order_settings(self) -> None:
        if self._website_orders_enabled:
            website_index = self.order_source_combo.findData("website")
            if website_index >= 0:
                self.order_source_combo.setCurrentIndex(website_index)
            self.order_source_combo.setEnabled(False)
        else:
            self.order_source_combo.setEnabled(True)
        self._update_website_order_state()

    def _toggle_advanced_group(self, checked: bool) -> None:
        self._update_advanced_panels()

    def _update_advanced_panels(self) -> None:
        advanced_visible = self.advanced_box.isChecked()
        self.discount_toggle.setEnabled(advanced_visible)
        self.notes_toggle.setEnabled(advanced_visible)
        self.return_toggle.setEnabled(advanced_visible)
        self.website_toggle.setEnabled(advanced_visible)
        self.discount_panel.setVisible(advanced_visible and self.discount_toggle.isChecked())
        self.notes_panel.setVisible(advanced_visible and self.notes_toggle.isChecked())
        self.return_panel.setVisible(advanced_visible and self.return_toggle.isChecked())
        self.website_order_panel.setVisible(advanced_visible and self.website_toggle.isChecked())
        self.advanced_customer_panel.setVisible(advanced_visible)
        self._update_return_reason_state()
        self._update_website_order_state()

    def _update_return_reason_state(self) -> None:
        is_return = self.txn_type_combo.currentIndex() == 1
        self.return_reason_input.setEnabled(
            is_return and self.return_toggle.isChecked() and self.advanced_box.isChecked()
        )

    def _update_website_order_state(self) -> None:
        if not self.advanced_box.isChecked() or not self.website_toggle.isChecked():
            self.website_order_input.setEnabled(False)
            return
        if self._website_orders_enabled:
            self.website_order_input.setEnabled(True)
            return
        is_website = self.order_source_combo.currentData() == "website"
        self.website_order_input.setEnabled(is_website)

    def apply_rtl_layout(self, rtl_enabled: bool) -> None:
        direction = Qt.LayoutDirection.RightToLeft if rtl_enabled else Qt.LayoutDirection.LeftToRight
        alignment = (
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            if rtl_enabled
            else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self._form_layout.setLabelAlignment(alignment)
        self.customer_search_input.setAlignment(alignment)
        self.customer_dropdown_frame.setLayoutDirection(direction)
        self.customer_dropdown.setLayoutDirection(direction)
        self.customer_no_results_label.setAlignment(alignment)
        self._customer_item_alignment = alignment

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

    def _calculate_discount_amount(
        self,
        subtotal: float,
        discount_value: Optional[float] = None,
        discount_type: Optional[str] = None,
    ) -> float:
        discount_value = float(self.discount_input.value()) if discount_value is None else float(discount_value)
        discount_type = self._discount_type() if discount_type is None else discount_type
        if discount_type == "percent":
            return max(subtotal * (discount_value / 100.0), 0.0)
        return max(discount_value, 0.0)

    def _queue_customer_search(self, _text: str) -> None:
        if self.customer_search_timer.isActive():
            self.customer_search_timer.stop()
        term = self.customer_search_input.text().strip()
        if len(term) < 2:
            self._hide_customer_dropdown()
            self.customer_dropdown.clear()
            self.customer_no_results_label.setVisible(False)
            self.customer_create_btn.setVisible(False)
            return
        self.customer_search_timer.start()

    def _perform_customer_search(self) -> None:
        term = self.customer_search_input.text().strip()
        if len(term) < 2:
            self._hide_customer_dropdown()
            return
        results = search_customers(term, limit=8)
        self.customer_dropdown.clear()
        if results:
            for customer in results:
                points = get_loyalty_balance(customer.phone)
                item = QListWidgetItem(self._format_customer_option(customer, points))
                item.setTextAlignment(self._customer_item_alignment)
                item.setData(Qt.ItemDataRole.UserRole, customer)
                item.setData(Qt.ItemDataRole.UserRole + 1, points)
                self.customer_dropdown.addItem(item)
            self.customer_dropdown.setCurrentRow(0)
            self.customer_no_results_label.setVisible(False)
            self.customer_create_btn.setVisible(False)
        else:
            self.customer_no_results_label.setVisible(True)
            self.customer_create_btn.setVisible(True)
        self._show_customer_dropdown()

    def _format_customer_option(self, customer, points: float) -> str:
        points_label = t("invoice.points_label", language=self._language)
        base = (
            f"{self._isolate(customer.name)} • "
            f"{self._isolate(customer.phone)} • "
            f"{self._isolate(points_label)} {points:.0f}"
        )
        if customer.email:
            return f"{base} • {self._isolate(customer.email)}"
        return base

    @staticmethod
    def _isolate(text: str) -> str:
        if not text:
            return ""
        return f"\u2068{text}\u2069"

    def _select_customer_from_dropdown(self, item: QListWidgetItem) -> None:
        customer = item.data(Qt.ItemDataRole.UserRole)
        points = item.data(Qt.ItemDataRole.UserRole + 1)
        if customer is None:
            return
        self._apply_customer_selection(customer, float(points or 0.0))
        self._hide_customer_dropdown()

    def _apply_customer_selection(self, customer, points: float) -> None:
        self._customer_id = customer.phone
        self._customer_points = points
        self.customer_points_label.setText(f"{self._customer_points:.2f}")
        self.customer_search_input.blockSignals(True)
        self.customer_search_input.setText(f"{customer.name} ({customer.phone})")
        self.customer_search_input.blockSignals(False)
        for field, value in (
            (self.customer_name_input, customer.name),
            (self.customer_phone_input, customer.phone),
            (self.customer_email_input, customer.email),
        ):
            field.blockSignals(True)
            field.setText(value)
            field.blockSignals(False)
        self._recalculate_totals()

    def _create_new_customer_from_search(self) -> None:
        self._open_quick_customer_dialog()

    def _open_quick_customer_dialog(self) -> None:
        term = self.customer_search_input.text().strip()
        normalized = term.replace(" ", "")
        is_phone = bool(term) and normalized.lstrip("+").isdigit()
        dialog = QuickCustomerDialog(
            self,
            name="" if is_phone else term,
            phone=term if is_phone else "",
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.values()
        name = payload["name"]
        phone = payload["phone"]
        email = payload["email"]
        notes = payload["notes"]
        if not name or not phone:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("invoice.customer_required", language=self._language),
            )
            return
        self._customer_id = save_customer(name, phone, email)
        self._customer_points = get_loyalty_balance(self._customer_id)
        self.customer_points_label.setText(f"{self._customer_points:.2f}")
        self.customer_search_input.blockSignals(True)
        self.customer_search_input.setText(f"{name} ({phone})")
        self.customer_search_input.blockSignals(False)
        for field, value in (
            (self.customer_name_input, name),
            (self.customer_phone_input, phone),
            (self.customer_email_input, email),
            (self.customer_notes_input, notes),
        ):
            field.blockSignals(True)
            field.setText(value)
            field.blockSignals(False)
        self._hide_customer_dropdown()
        self._recalculate_totals()

    def _clear_customer_selection(self, _text: str) -> None:
        if self._customer_id is None:
            return
        self._customer_id = None
        self._customer_points = 0.0
        self.customer_points_label.setText("0")
        self._recalculate_totals()

    def _show_customer_dropdown(self) -> None:
        if self.customer_dropdown.count() == 0 and not self.customer_create_btn.isVisible():
            return
        self.customer_dropdown_frame.setVisible(True)

    def _hide_customer_dropdown(self) -> None:
        self.customer_dropdown_frame.setVisible(False)

    def _handle_customer_dropdown_key(self, event) -> bool:
        if event.key() == Qt.Key.Key_Escape:
            self._hide_customer_dropdown()
            return True
        if not self.customer_dropdown_frame.isVisible():
            return False
        if event.key() == Qt.Key.Key_Down:
            row = self.customer_dropdown.currentRow()
            next_row = 0 if row < 0 else min(row + 1, self.customer_dropdown.count() - 1)
            self.customer_dropdown.setCurrentRow(next_row)
            return True
        if event.key() == Qt.Key.Key_Up:
            row = self.customer_dropdown.currentRow()
            next_row = 0 if row <= 0 else row - 1
            self.customer_dropdown.setCurrentRow(next_row)
            return True
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.customer_dropdown.currentItem()
            if item:
                self._select_customer_from_dropdown(item)
                return True
        return False

    def _save_customer_profile(self) -> None:
        name = self.customer_name_input.text().strip()
        phone = self.customer_phone_input.text().strip()
        email = self.customer_email_input.text().strip()
        if not name or not phone:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("invoice.customer_required", language=self._language),
            )
            return
        self._customer_id = save_customer(name, phone, email)
        self._customer_points = get_loyalty_balance(self._customer_id)
        self.customer_points_label.setText(f"{self._customer_points:.2f}")
        self.customer_search_input.blockSignals(True)
        self.customer_search_input.setText(f"{name} ({phone})")
        self.customer_search_input.blockSignals(False)
        self._recalculate_totals()
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("invoice.profile_saved", language=self._language),
        )

    def _configure_shortcuts(self) -> None:
        search_shortcut = QShortcut(QKeySequence("/"), self)
        search_shortcut.activated.connect(self._focus_product_search)

        new_invoice_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_invoice_shortcut.activated.connect(self._clear_invoice)

        new_customer_shortcut = QShortcut(QKeySequence("F2"), self)
        new_customer_shortcut.activated.connect(self._start_new_customer_entry)

        discount_shortcut = QShortcut(QKeySequence("F4"), self)
        discount_shortcut.activated.connect(self._focus_discount)

        save_shortcut = QShortcut(QKeySequence("F8"), self)
        save_shortcut.activated.connect(self._save_invoice)

    def _configure_focus_order(self) -> None:
        self.barcode_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.search_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.customer_search_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setTabOrder(self.barcode_input, self.search_input)
        self.setTabOrder(self.search_input, self.products_table)
        self.setTabOrder(self.products_table, self.qty_input)
        self.setTabOrder(self.qty_input, self.add_btn)
        self.setTabOrder(self.add_btn, self.customer_search_input)
        self.setTabOrder(self.customer_search_input, self.customer_name_input)
        self.setTabOrder(self.customer_name_input, self.customer_phone_input)
        self.setTabOrder(self.customer_phone_input, self.discount_input)
        self.setTabOrder(self.discount_input, self.save_btn)
        self.setTabOrder(self.save_btn, self.export_btn)
        self.setTabOrder(self.export_btn, self.print_btn)
        self.setTabOrder(self.print_btn, self.clear_btn)
        self.barcode_input.setFocus()

    def _focus_product_search(self) -> None:
        self.search_input.setFocus()
        self.search_input.selectAll()

    def _submit_barcode_input(self) -> None:
        code = self.barcode_input.text().strip()
        if not code:
            return
        self.barcode_input.clear()
        self._dispatch_scan(code)
        self.barcode_input.setFocus()

    def _focus_discount(self) -> None:
        self.discount_input.setFocus()
        self.discount_input.selectAll()

    def _start_new_customer_entry(self) -> None:
        term = self.customer_search_input.text().strip()
        if term:
            self._create_new_customer_from_search()
            return
        self._customer_id = None
        self._customer_points = 0.0
        self.customer_points_label.setText("0")
        self.customer_name_input.clear()
        self.customer_phone_input.clear()
        self.customer_email_input.clear()
        self.customer_notes_input.clear()
        self.customer_search_input.clear()
        self.customer_name_input.setFocus()

    def _loyalty_redeem_amount(self, subtotal: float, discount: float) -> float:
        max_redeem = max(subtotal - discount, 0.0)
        max_redeem = min(max_redeem, float(self._customer_points))
        if self.loyalty_redeem_input.value() > max_redeem:
            self.loyalty_redeem_input.blockSignals(True)
            self.loyalty_redeem_input.setValue(max_redeem)
            self.loyalty_redeem_input.blockSignals(False)
        return float(self.loyalty_redeem_input.value())

    def _load_loyalty_settings(self) -> None:
        settings = QSettings()
        self._loyalty_points_per_100 = settings.value("loyalty_points_per_100", 1.0, float)
        self._loyalty_alert_threshold = settings.value("loyalty_alert_threshold", 0, int)

    def _calculate_loyalty_points(self, net_total: float) -> int:
        self._load_loyalty_settings()
        # Floor the computed points so we never round up fractional earnings.
        earned = math.floor(net_total / 100 * self._loyalty_points_per_100)
        return max(0, int(earned))

    def _add_selected_product(self) -> None:
        row = self.products_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self,
                t("common.select", language=self._language),
                t("invoice.select_product", language=self._language),
            )
            return
        if self._is_out_of_stock_row(row):
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
        txn_type = "return" if self.txn_type_combo.currentIndex() == 1 else "sale"
        computed = self._compute_invoice_totals(txn_type)
        subtotal = float(computed["subtotal"])
        loyalty_redeem = float(computed["loyalty_redeem"])
        net_total = float(computed["net_total"])
        grand_total = float(computed["total"])
        self.subtotal_label.setText(
            t("invoice.subtotal", language=self._language, total=f"{subtotal:.2f}")
        )
        self.total_label.setText(t("invoice.net_total", language=self._language, total=f"{net_total:.2f}"))
        self.loyalty_summary_label.setText(
            t("invoice.loyalty_summary", language=self._language, total=f"{loyalty_redeem:.2f}")
        )
        customer_name = self.customer_name_input.text().strip()
        customer_phone = self.customer_phone_input.text().strip()
        has_customer = bool(self._customer_id or (customer_name and customer_phone))
        earned = 0 if self.txn_type_combo.currentIndex() == 1 else self._calculate_loyalty_points(net_total)
        display_earned = earned if has_customer else 0
        self.loyalty_earned_label.setText(f"{display_earned}")
        self._current_grand_total = grand_total
        if self.items_table.rowCount() == 0 and self._pay_now_manual:
            self._pay_now_manual = False
            self.pay_now_input.lineEdit().setReadOnly(True)
            self._refresh_pay_now_manual_ui()
        if not self._pay_now_manual:
            self._set_pay_now_value(grand_total)
        self._update_payment_totals()
        self._refresh_summary_labels()
        self._update_validation_state()

    def _delivery_fee_value(self) -> float:
        if not self.delivery_enabled_checkbox.isChecked():
            return 0.0
        return float(self.delivery_fee_input.value())

    def _set_pay_now_value(self, value: float) -> None:
        self._pay_now_updating = True
        self.pay_now_input.blockSignals(True)
        self.pay_now_input.setValue(max(value, 0.0))
        self.pay_now_input.blockSignals(False)
        self._pay_now_updating = False

    def _update_payment_totals(self) -> None:
        grand_total = max(self._current_grand_total, 0.0)
        if grand_total < 0:
            grand_total = 0.0
        self.pay_now_input.setMaximum(grand_total)
        if not self._pay_now_manual:
            self._set_pay_now_value(grand_total)
        pay_now = min(float(self.pay_now_input.value()), grand_total)
        if float(self.pay_now_input.value()) != pay_now:
            self._set_pay_now_value(pay_now)
        remaining = max(grand_total - pay_now, 0.0)
        self.grand_total_value.setText(f"{grand_total:.2f}")
        self.paid_total_value.setText(f"{pay_now:.2f}")
        self.remaining_total_value.setText(f"{remaining:.2f}")
        is_partial = self._pay_now_manual and grand_total > 0 and pay_now < grand_total
        if is_partial != self._payment_statuses_enabled:
            self._refresh_payment_statuses(required=is_partial)
        self.payment_due_date_label.setVisible(is_partial)
        self.payment_order_status_label.setVisible(is_partial)
        self.payment_order_status_combo.setVisible(is_partial)
        self.payment_due_date_input.setVisible(is_partial)
        self.payment_due_date_input.setEnabled(is_partial)
        if not is_partial:
            self.payment_order_status_combo.setCurrentIndex(0)
            self.payment_due_date_input.setDate(QDate.currentDate())
        self._update_validation_state()

    def _calculate_subtotal(self) -> float:
        subtotal = 0.0
        for row in range(self.items_table.rowCount()):
            subtotal += float(self.items_table.item(row, self.ITEM_COL_LINE_TOTAL).text())
        return subtotal

    def _compute_invoice_totals(self, txn_type: str) -> dict[str, float | str]:
        subtotal = self._calculate_subtotal()
        discount_type = self._discount_type()
        adjustments_allowed = self.advanced_box.isChecked()
        discount_value = float(self.discount_input.value()) if adjustments_allowed else 0.0
        discount = self._calculate_discount_amount(subtotal, discount_value, discount_type) if adjustments_allowed else 0.0
        loyalty_redeem = (
            0.0
            if txn_type == "return" or not adjustments_allowed
            else self._loyalty_redeem_amount(subtotal, discount)
        )
        delivery_enabled = self.delivery_enabled_checkbox.isChecked()
        delivery_fee = self._delivery_fee_value() if (delivery_enabled and adjustments_allowed) else 0.0
        net_total = max(subtotal - discount - loyalty_redeem, 0.0)
        total = max(net_total + delivery_fee, 0.0)
        loyalty_earned = 0 if txn_type == "return" else self._calculate_loyalty_points(net_total)
        return {
            "subtotal": subtotal,
            "discount_type": discount_type,
            "discount_value": discount_value,
            "discount": discount,
            "loyalty_redeem": loyalty_redeem,
            "delivery_fee": delivery_fee,
            "net_total": net_total,
            "total": total,
            "loyalty_earned": loyalty_earned,
        }

    def _validation_message(self) -> str:
        if self.items_table.rowCount() == 0:
            return t("invoice.validation_items", language=self._language)
        customer_name = self.customer_name_input.text().strip()
        customer_phone = self.customer_phone_input.text().strip()
        if (customer_name or customer_phone) and not (customer_name and customer_phone):
            return t("invoice.validation_customer", language=self._language)
        has_customer = bool(self._customer_id or (customer_name and customer_phone))
        pay_now = float(self.pay_now_input.value())
        grand_total = max(self._current_grand_total, 0.0)
        is_partial = self._pay_now_manual and grand_total > 0 and pay_now < grand_total
        if is_partial and not has_customer:
            return t("invoice.validation_credit_customer", language=self._language)
        if is_partial and self.payment_order_status_combo.count() > 1:
            if self.payment_order_status_combo.currentIndex() <= 0:
                return t("invoice.validation_payment_status", language=self._language)
        if self.delivery_enabled_checkbox.isChecked():
            if self.delivery_company_combo.currentData() is None:
                return t("invoice.validation_delivery_company", language=self._language)
            if not self.delivery_address_input.text().strip():
                return t("invoice.validation_delivery_address", language=self._language)
            if self.delivery_status_combo.count() > 1 and self.delivery_status_combo.currentData() is None:
                return t("invoice.validation_delivery_status", language=self._language)
        return ""

    def _update_validation_state(self) -> None:
        message = self._validation_message()
        has_error = bool(message)
        self.save_btn.setEnabled(not has_error)
        self.validation_label.setVisible(has_error)
        self.validation_label.setText(message)

    def _collect_items(self) -> List[JewelryInvoiceItem]:
        items = []
        for row in range(self.items_table.rowCount()):
            product_id = self.items_table.item(row, self.ITEM_COL_PRODUCT).data(Qt.ItemDataRole.UserRole)
            name = self.items_table.item(row, self.ITEM_COL_PRODUCT).text()
            code = self.items_table.item(row, self.ITEM_COL_CODE).text()
            qty = float(self.items_table.item(row, self.ITEM_COL_QTY).text())
            unit_price = float(self.items_table.item(row, self.ITEM_COL_UNIT_PRICE).text())
            line_total = float(self.items_table.item(row, self.ITEM_COL_LINE_TOTAL).text())
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
            QMessageBox.warning(
                self,
                t("invoice.missing_items_title", language=self._language),
                t("invoice.missing_items_message", language=self._language),
            )
            return
        cashier = self.cashier_input.text().strip() or "N/A"
        txn_type = "return" if self.txn_type_combo.currentIndex() == 1 else "sale"
        customer_name = self.customer_name_input.text().strip()
        customer_phone = self.customer_phone_input.text().strip()
        customer_email = self.customer_email_input.text().strip()
        customer_id = None
        if customer_name or customer_phone:
            if not customer_name or not customer_phone:
                QMessageBox.warning(
                    self,
                    t("common.select", language=self._language),
                    t("invoice.customer_required", language=self._language),
                )
                return
            customer_id = save_customer(customer_name, customer_phone, customer_email)
            self._customer_id = customer_id
            self._customer_points = get_loyalty_balance(customer_id)
            self.customer_points_label.setText(f"{self._customer_points:.2f}")
        computed = self._compute_invoice_totals(txn_type)
        subtotal = float(computed["subtotal"])
        discount_type = str(computed["discount_type"])
        discount_value = float(computed["discount_value"])
        discount = float(computed["discount"])
        loyalty_redeem = float(computed["loyalty_redeem"])
        net_total = float(computed["net_total"])
        delivery_enabled = self.delivery_enabled_checkbox.isChecked()
        delivery_fee = float(computed["delivery_fee"])
        total = float(computed["total"])
        loyalty_earned = int(computed["loyalty_earned"])
        payment_method = self.payment_combo.currentText()
        pay_now = min(float(self.pay_now_input.value()), total)
        if not self.advanced_box.isChecked():
            pay_now = total
        is_partial = self._pay_now_manual and total > 0 and pay_now < total and self.advanced_box.isChecked()
        if abs(self._current_grand_total - total) > 0.01:
            QMessageBox.warning(
                self,
                t("invoice.save_failed_title", language=self._language),
                "Invoice totals changed. Please review totals and try saving again.",
            )
            self._recalculate_totals()
            return
        payment_due_date = (
            to_iso_date(self.payment_due_date_input.date().toString("dd/MM/yyyy"))
            if is_partial
            else ""
        )
        payment_order_status_id = None
        if is_partial and self.payment_order_status_combo.currentIndex() > 0:
            payment_order_status_id = self.payment_order_status_combo.currentData()
        delivery_company_id = (
            self.delivery_company_combo.currentData() if delivery_enabled else None
        )
        delivery_address = self.delivery_address_input.text().strip() if delivery_enabled else ""
        delivery_status_id = (
            self.delivery_status_combo.currentData() if delivery_enabled else None
        )
        if not self.advanced_box.isChecked():
            self._pay_now_manual = False
            self.pay_now_input.lineEdit().setReadOnly(True)
            self._refresh_pay_now_manual_ui()
        order_source = self.order_source_combo.currentData() or "in_store"
        website_order_ref = (
            self.website_order_input.text().strip() if order_source == "website" else ""
        )
        notes = self.notes_input.toPlainText().strip()
        return_reason = self.return_reason_input.text().strip() if txn_type == "return" else ""
        items = self._collect_items()
        try:
            invoice_no, invoice_id = create_invoice(
                cashier,
                txn_type,
                customer_id,
                customer_name,
                customer_phone,
                subtotal,
                discount,
                discount_type,
                discount_value,
                loyalty_earned,
                loyalty_redeem,
                total,
                payment_method,
                payment_due_date,
                payment_order_status_id,
                order_source,
                website_order_ref,
                delivery_enabled,
                delivery_company_id,
                delivery_fee,
                delivery_address,
                delivery_status_id,
                notes,
                return_reason,
                items,
            )
            if pay_now > 0:
                create_order_payment(invoice_id, payment_method, pay_now, cashier_name=cashier)
            recalculate_invoice_payment_totals(invoice_id)
            self._last_invoice_no = invoice_no
            self.invoice_info_label.setText(
                t("invoice.info_number", language=self._language, invoice_no=invoice_no)
            )
            if self.auto_print_after_save_checkbox.isChecked():
                self._print_invoice()
        except Exception as exc:  # noqa: BLE001 - show the error and keep the app open.
            logger.exception("Failed to save invoice.")
            QMessageBox.critical(
                self,
                t("invoice.save_failed_title", language=self._language),
                t("invoice.save_failed_message", language=self._language, error=str(exc)),
            )
            return
        if customer_id:
            self._load_loyalty_settings()
            self._customer_points = get_loyalty_balance(customer_id)
            if self._loyalty_alert_threshold > 0 and self._customer_points >= self._loyalty_alert_threshold:
                QMessageBox.information(
                    self,
                    t("loyalty.alert_title", language=self._language),
                    t(
                        "loyalty.alert_message",
                        language=self._language,
                        balance=f"{self._customer_points:.2f}",
                        threshold=self._loyalty_alert_threshold,
                    ),
                )
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("invoice.saved_message", language=self._language, invoice_no=invoice_no),
        )
        self._refresh_recently_sold()
        self.reset_invoice_state()
        self.refresh_products()

    def _refresh_recently_sold(self) -> None:
        self.recent_sold_table.setRowCount(0)
        conn = get_conn()
        try:
            rows = conn.execute("SELECT invoice_no, datetime, total FROM jw_invoices ORDER BY id DESC LIMIT 10").fetchall()
        finally:
            conn.close()
        for invoice_no, dt, total in rows:
            row = self.recent_sold_table.rowCount()
            self.recent_sold_table.insertRow(row)
            self.recent_sold_table.setItem(row, 0, QTableWidgetItem(str(invoice_no)))
            self.recent_sold_table.setItem(row, 1, QTableWidgetItem(str(dt)))
            self.recent_sold_table.setItem(row, 2, QTableWidgetItem(f"{float(total):.2f}"))
            actions = QWidget()
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            print_label = "طباعة" if self._language == "ar" else "Print"
            details_label = "فتح التفاصيل" if self._language == "ar" else "Open Details"
            print_btn = QPushButton(print_label)
            details_btn = QPushButton(details_label)
            for button in (print_btn, details_btn):
                button.setMinimumHeight(24)
                button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
                button.setStyleSheet("padding: 2px 6px; font-size: 11px;")
            print_btn.clicked.connect(lambda _c=False, inv=invoice_no: self._print_recent_invoice(inv))
            details_btn.clicked.connect(lambda _c=False, inv=invoice_no: self._open_recent_invoice_details(inv))
            actions_layout.addWidget(print_btn)
            actions_layout.addWidget(details_btn)
            self.recent_sold_table.setCellWidget(row, 3, actions)

    def _print_recent_invoice(self, invoice_no: str) -> None:
        self._last_invoice_no = invoice_no
        self._print_invoice()

    def _open_recent_invoice_details(self, invoice_no: str) -> None:
        invoice, _items = fetch_invoice_details(invoice_no)
        QMessageBox.information(self, "Invoice Details", f"{invoice.invoice_no}\n{invoice.datetime}\n{invoice.total:.2f}")

    def _export_invoice_pdf(self) -> None:
        if not self._last_invoice_no:
            QMessageBox.warning(
                self,
                t("common.export", language=self._language),
                t("invoice.export_first", language=self._language),
            )
            return
        invoice, items = fetch_invoice_details(self._last_invoice_no)
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("invoice.export_pdf", language=self._language),
            f"{invoice.invoice_no}.pdf",
            f"{t('common.file_filter_pdf', language=self._language)} (*.pdf)",
        )
        if not path:
            return
        gallery_settings = load_gallery_settings()
        gallery = GalleryInfo(
            name_en=gallery_settings.name_en,
            name_ar=gallery_settings.name_ar,
            address=gallery_settings.address,
            phone=gallery_settings.phone,
            website_name=gallery_settings.website_name,
            website_url=gallery_settings.website_url,
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
            invoice.customer_name,
            invoice.customer_phone,
            [(i.product_name, i.product_code, i.qty, i.unit_price, i.line_total) for i in items],
            invoice.subtotal,
            invoice.discount,
            invoice.discount_type,
            invoice.discount_value,
            invoice.loyalty_earned,
            invoice.loyalty_redeemed,
            invoice.total,
            invoice.payment_method,
            invoice.order_source,
            invoice.website_order_ref,
            invoice.notes,
            invoice.return_reason,
        )
        QMessageBox.information(
            self,
            t("common.export", language=self._language),
            t("invoice.exported", language=self._language),
        )

    def _print_invoice(self) -> None:
        if not self._last_invoice_no:
            QMessageBox.warning(
                self,
                t("common.print", language=self._language),
                t("invoice.export_first", language=self._language),
            )
            return
        invoice, items = fetch_invoice_details(self._last_invoice_no)
        try:
            if self.print_mode_combo.currentData() == "direct":
                self._load_loyalty_settings()
                loyalty_balance = get_loyalty_balance(invoice.customer_id) if invoice.customer_id else None
                receipt_text = build_receipt_text(
                    invoice,
                    items,
                    loyalty_balance=loyalty_balance,
                    loyalty_threshold=self._loyalty_alert_threshold,
                )
                if self.print_preview_checkbox.isChecked():
                    QMessageBox.information(self, "Preview", "\n".join(receipt_text.splitlines()[:12]))
                receipt_settings = load_gallery_settings()
                printer.print_text_receipt(
                    receipt_text.splitlines(),
                    printer_name=receipt_settings.receipt_printer_name,
                    print_mode=receipt_settings.receipt_print_mode,
                )
            else:
                tmp_path = Path.cwd() / f"{self._last_invoice_no}.pdf"
                gallery_settings = load_gallery_settings()
                gallery = GalleryInfo(
                    name_en=gallery_settings.name_en,
                    name_ar=gallery_settings.name_ar,
                    address=gallery_settings.address,
                    phone=gallery_settings.phone,
                    website_name=gallery_settings.website_name,
                    website_url=gallery_settings.website_url,
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
                    invoice.customer_name,
                    invoice.customer_phone,
                    [(i.product_name, i.product_code, i.qty, i.unit_price, i.line_total) for i in items],
                    invoice.subtotal,
                    invoice.discount,
                    invoice.discount_type,
                    invoice.discount_value,
                    invoice.loyalty_earned,
                    invoice.loyalty_redeemed,
                    invoice.total,
                    invoice.payment_method,
                    invoice.order_source,
                    invoice.website_order_ref,
                    invoice.notes,
                    invoice.return_reason,
                )
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(tmp_path)))
            QMessageBox.information(self, t("common.print", language=self._language), "تمت الطباعة بنجاح.")
        except Exception as exc:
            QMessageBox.critical(self, t("common.print", language=self._language), f"فشلت الطباعة: {exc}")
        self._refresh_printer_status_badge()

    def _load_print_preferences(self) -> None:
        settings = QSettings()
        self.auto_print_after_save_checkbox.setChecked(
            settings.value("invoice_auto_print_after_save", False, bool)
        )
        mode = settings.value("invoice_print_mode", "direct", str)
        self.print_mode_combo.setCurrentIndex(0 if mode == "direct" else 1)
        self.print_preview_checkbox.setChecked(settings.value("invoice_quick_preview", False, bool))
        self.auto_print_after_save_checkbox.toggled.connect(
            lambda v: settings.setValue("invoice_auto_print_after_save", v)
        )
        self.print_mode_combo.currentIndexChanged.connect(
            lambda: settings.setValue("invoice_print_mode", self.print_mode_combo.currentData())
        )
        self.print_preview_checkbox.toggled.connect(
            lambda v: settings.setValue("invoice_quick_preview", v)
        )

    def _refresh_printer_status_badge(self) -> None:
        status = printer.printer_status_text()
        is_ready = status == "ready"
        icon = "🟢" if is_ready else "🔴"
        label = "Printer Ready" if is_ready else "Printer Offline"
        self.printer_status_label.setText(f"{icon} {label}")

    def reset_invoice_state(self, keep_customer: bool = False) -> None:
        self._reset_invoice(keep_customer=keep_customer)
        self._focus_default_input()

    def _reset_after_save(self, keep_customer: bool = False) -> None:
        self.reset_invoice_state(keep_customer=keep_customer)

    def _clear_invoice(self) -> None:
        self.reset_invoice_state(keep_customer=False)

    def _reset_invoice(self, keep_customer: bool = False) -> None:
        self.items_table.setRowCount(0)
        self.txn_type_combo.setCurrentIndex(0)
        self.payment_combo.setCurrentIndex(0)
        self.discount_type_combo.setCurrentIndex(0)
        self.discount_input.setValue(0.0)
        self.loyalty_redeem_input.setValue(0.0)
        self.pay_now_input.setValue(0.0)
        self.payment_due_date_input.setDate(QDate.currentDate())
        self.payment_order_status_combo.setCurrentIndex(0)
        self.delivery_enabled_checkbox.setChecked(False)
        self.delivery_company_combo.setCurrentIndex(0)
        self.delivery_fee_input.setValue(0.0)
        self.delivery_address_input.clear()
        self.delivery_status_combo.setCurrentIndex(0)
        self._pay_now_manual = False
        self.pay_now_input.lineEdit().setReadOnly(True)
        self._refresh_pay_now_manual_ui()
        if not keep_customer:
            self.customer_name_input.clear()
            self.customer_phone_input.clear()
            self.customer_email_input.clear()
            self.customer_notes_input.clear()
            self.customer_points_label.setText("0")
            self.customer_search_input.clear()
            self._customer_id = None
            self._customer_points = 0.0
        self._hide_customer_dropdown()
        self.loyalty_earned_label.setText("0")
        self.notes_input.clear()
        self.return_reason_input.clear()
        self.order_source_combo.setCurrentIndex(0)
        self.website_order_input.clear()
        for toggle in (self.discount_toggle, self.notes_toggle, self.return_toggle, self.website_toggle):
            toggle.setChecked(False)
        self._update_advanced_panels()
        self._last_invoice_no = None
        self.invoice_info_label.setText(t("invoice.info_auto", language=self._language))
        self._apply_website_order_settings()
        self._recalculate_totals()
        self._update_validation_state()

    def _add_product_to_invoice(self, product, qty: float) -> None:
        for row in range(self.items_table.rowCount()):
            if self.items_table.item(row, self.ITEM_COL_PRODUCT).data(Qt.ItemDataRole.UserRole) == product.id:
                existing_qty = float(self.items_table.item(row, self.ITEM_COL_QTY).text())
                new_qty = existing_qty + qty
                self.items_table.setItem(row, self.ITEM_COL_QTY, QTableWidgetItem(f"{new_qty:.2f}"))
                line_total = new_qty * product.price
                self.items_table.setItem(
                    row,
                    self.ITEM_COL_LINE_TOTAL,
                    QTableWidgetItem(f"{line_total:.2f}"),
                )
                self._attach_qty_buttons(row, product.id)
                self._recalculate_totals()
                self._focus_barcode_input()
                return
        line_total = qty * product.price
        item_row = self.items_table.rowCount()
        self.items_table.insertRow(item_row)
        self.items_table.setItem(
            item_row,
            self.ITEM_COL_PRODUCT,
            QTableWidgetItem(choose_name(product.name_ar, product.name_en, language=self._language)),
        )
        self.items_table.setItem(item_row, self.ITEM_COL_CODE, QTableWidgetItem(product.sku))
        self.items_table.setItem(item_row, self.ITEM_COL_QTY, QTableWidgetItem(f"{qty:.2f}"))
        self.items_table.setItem(
            item_row,
            self.ITEM_COL_UNIT_PRICE,
            QTableWidgetItem(f"{product.price:.2f}"),
        )
        self.items_table.setItem(
            item_row,
            self.ITEM_COL_LINE_TOTAL,
            QTableWidgetItem(f"{line_total:.2f}"),
        )
        self.items_table.item(item_row, self.ITEM_COL_PRODUCT).setData(Qt.ItemDataRole.UserRole, product.id)
        self._attach_qty_buttons(item_row, product.id)
        self._recalculate_totals()
        self._focus_barcode_input()

    def _attach_qty_buttons(self, row: int, product_id: int) -> None:
        minus_btn = QPushButton("−")
        minus_btn.setProperty("product_id", product_id)
        minus_btn.clicked.connect(lambda _checked=False, delta=-1.0: self._adjust_item_qty(product_id, delta))
        plus_btn = QPushButton("+")
        plus_btn.setProperty("product_id", product_id)
        plus_btn.clicked.connect(lambda _checked=False, delta=1.0: self._adjust_item_qty(product_id, delta))
        minus_btn.setFixedWidth(JEWELRY_CONTROLS.icon_button_size)
        plus_btn.setFixedWidth(JEWELRY_CONTROLS.icon_button_size)
        self.items_table.setCellWidget(row, self.ITEM_COL_DECREMENT, minus_btn)
        self.items_table.setCellWidget(row, self.ITEM_COL_INCREMENT, plus_btn)

    def _adjust_item_qty(self, product_id: int, delta: float) -> None:
        row = self._find_item_row(product_id)
        if row < 0:
            return
        try:
            current_qty = float(self.items_table.item(row, self.ITEM_COL_QTY).text())
        except Exception:
            current_qty = 0.0
        new_qty = current_qty + delta
        if new_qty <= 0:
            self.items_table.removeRow(row)
            self._recalculate_totals()
            return
        unit_price = float(self.items_table.item(row, self.ITEM_COL_UNIT_PRICE).text())
        self.items_table.setItem(row, self.ITEM_COL_QTY, QTableWidgetItem(f"{new_qty:.2f}"))
        self.items_table.setItem(
            row,
            self.ITEM_COL_LINE_TOTAL,
            QTableWidgetItem(f"{new_qty * unit_price:.2f}"),
        )
        self._recalculate_totals()
        self._focus_barcode_input()

    def _focus_barcode_input(self) -> None:
        if not self.barcode_input.isVisible():
            return
        self.barcode_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self.barcode_input.selectAll()

    def _focus_default_input(self) -> None:
        self._focus_barcode_input()
        if not self.barcode_input.isVisible():
            self._focus_product_search()

    def _handle_barcode_submit(self) -> None:
        code = self.barcode_input.text().strip()
        if not code:
            return
        self.barcode_input.clear()
        self._dispatch_scan(code)
        if self._instant_invoice_mode:
            self._focus_barcode_input()

    def _find_item_row(self, product_id: int) -> int:
        for row in range(self.items_table.rowCount()):
            item = self.items_table.item(row, self.ITEM_COL_PRODUCT)
            if item and item.data(Qt.ItemDataRole.UserRole) == product_id:
                return row
        return -1

    def _is_out_of_stock_row(self, row: int) -> bool:
        item = self.products_table.item(row, 0)
        if not item:
            return False
        return bool(item.data(Qt.ItemDataRole.UserRole + 1))

    def _update_add_state(self) -> None:
        row = self.products_table.currentRow()
        if row < 0:
            self.add_btn.setEnabled(False)
            self.add_btn.setToolTip("")
            return
        if self._is_out_of_stock_row(row):
            self.add_btn.setEnabled(False)
            self.add_btn.setToolTip(t("invoice.out_of_stock", language=self._language))
        else:
            self.add_btn.setEnabled(True)
            self.add_btn.setToolTip("")

    def _apply_invoice_styles(self) -> None:
        self.setStyleSheet(
            """
            #jewelryInvoiceTab QGroupBox {
                font-weight: 600;
                border: 1px solid #d6ccc2;
                border-radius: 10px;
                margin-top: 12px;
                padding: 10px;
                background: #fdfbf8;
            }
            #jewelryInvoiceTab QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            #jewelryInvoiceTab QFrame#customerDropdown {
                background: #ffffff;
                border: 1px solid #e0d7cf;
                border-radius: 6px;
            }
            #jewelryInvoiceTab QTableWidget {
                background: #ffffff;
                border: 1px solid #e0d7cf;
                border-radius: 8px;
                gridline-color: #efe7df;
            }
            #jewelryInvoiceTab QListWidget {
                border: none;
            }
            #jewelryInvoiceTab QHeaderView::section {
                background: #f3eee9;
                padding: 6px;
                border: none;
                font-weight: 600;
            }
            #jewelryInvoiceTab QPushButton#primaryButton {
                background: #c89a5b;
                color: white;
                padding: 8px 12px;
                border-radius: 8px;
                font-weight: 600;
            }
            #jewelryInvoiceTab QPushButton {
                padding: 6px 12px;
                border-radius: 6px;
                min-height: 30px;
            }
            #jewelryInvoiceTab QLabel#netTotalLabel {
                font-size: 22px;
                font-weight: 700;
                color: #4b3a2a;
            }
            #jewelryInvoiceTab QLabel#summarySectionTitle {
                font-size: 12px;
                font-weight: 600;
                color: #7a6a58;
            }
            #jewelryInvoiceTab QLabel#validationLabel {
                color: #b42318;
                font-weight: 600;
                padding: 4px 0;
            }
            #jewelryInvoiceTab QLabel {
                padding: 2px 0;
            }
            #jewelryInvoiceTab QTableWidget::item {
                padding: 4px;
            }
            """
        )

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("invoice.header", language=language))
        if self._last_invoice_no:
            self.invoice_info_label.setText(
                t("invoice.info_number", language=language, invoice_no=self._last_invoice_no)
            )
        else:
            self.invoice_info_label.setText(t("invoice.info_auto", language=language))
        self.form_box.setTitle(t("invoice.form_box", language=language))
        self.txn_type_combo.setItemText(0, t("invoice.txn_sale", language=language))
        self.txn_type_combo.setItemText(1, t("invoice.txn_return", language=language))
        self.order_source_combo.setItemText(0, t("invoice.order_source_in_store", language=language))
        self.order_source_combo.setItemText(1, t("invoice.order_source_website", language=language))
        self.website_order_label.setText(t("invoice.website_order_label", language=language))
        self.website_order_input.setPlaceholderText(
            t("invoice.website_order_placeholder", language=language)
        )
        self.delivery_enabled_label.setText(t("invoice.delivery_enabled_label", language=language))
        self.delivery_company_label.setText(t("invoice.delivery_company_label", language=language))
        self.delivery_fee_label.setText(t("invoice.delivery_fee_label", language=language))
        self.delivery_address_label.setText(t("invoice.delivery_address_label", language=language))
        self.delivery_address_input.setPlaceholderText(
            t("invoice.delivery_address_placeholder", language=language)
        )
        self.delivery_status_label.setText(t("invoice.delivery_status_label", language=language))
        self.discount_type_combo.setItemText(0, t("invoice.discount_type_amount", language=language))
        self.discount_type_combo.setItemText(1, t("invoice.discount_type_percent", language=language))
        self.discount_type_label.setText(t("invoice.discount_type_label", language=language))
        self.discount_value_label.setText(t("invoice.discount_value_label", language=language))
        self.customer_search_input.setPlaceholderText(
            t("invoice.customer_search_placeholder", language=language)
        )
        self.customer_no_results_label.setText(t("invoice.customer_no_results", language=language))
        self.customer_create_btn.setText(t("invoice.customer_create", language=language))
        self.customer_phone_input.setPlaceholderText(
            t("invoice.customer_phone_placeholder", language=language)
        )
        self.customer_email_input.setPlaceholderText(
            t("invoice.customer_email_placeholder", language=language)
        )
        self.customer_notes_input.setPlaceholderText(
            t("invoice.customer_notes_placeholder", language=language)
        )
        self.customer_save_btn.setText(t("invoice.customer_save", language=language))
        self.notes_label.setText(t("invoice.notes_label", language=language))
        self.return_reason_input.setPlaceholderText(
            t("invoice.return_reason_placeholder", language=language)
        )
        self.return_reason_label.setText(t("invoice.return_reason_label", language=language))
        self.discount_toggle.setText(t("invoice.toggle_discount", language=language))
        self.notes_toggle.setText(t("invoice.toggle_notes", language=language))
        self.return_toggle.setText(t("invoice.toggle_return", language=language))
        self.website_toggle.setText(t("invoice.toggle_website", language=language))
        self.cashier_label.setText(t("invoice.cashier_label", language=language))
        self.transaction_label.setText(t("invoice.transaction_label", language=language))
        self.payment_method_label.setText(t("common.payment_method", language=language))
        self.order_source_label.setText(t("invoice.order_source_label", language=language))
        self.customer_search_label.setText(t("invoice.customer_search_label", language=language))
        self.customer_name_label.setText(t("invoice.customer_name_label", language=language))
        self.customer_phone_label.setText(t("invoice.customer_phone_label", language=language))
        self.grand_total_label.setText(t("invoice.grand_total_label", language=language))
        self.paid_total_label.setText(t("invoice.paid_total_label", language=language))
        self.remaining_total_label.setText(t("invoice.remaining_total_label", language=language))
        self.pay_now_label.setText(t("invoice.pay_now_label", language=language))
        self.pay_now_hint_label.setText(
            t("invoice.pay_now_hint_partial", language=language)
            if self._pay_now_manual
            else t("invoice.pay_now_hint_default", language=language)
        )
        self._refresh_pay_now_manual_ui()
        self.payment_due_date_label.setText(t("invoice.payment_due_date_label", language=language))
        self.payment_due_date_input.setToolTip(t("invoice.payment_due_date_placeholder", language=language))
        self.payment_order_status_label.setText(
            t("invoice.payment_order_status_label", language=language)
        )
        self.customer_email_label.setText(t("invoice.customer_email_label", language=language))
        self.customer_notes_label.setText(t("invoice.customer_notes_label", language=language))
        self.loyalty_balance_label.setText(t("invoice.loyalty_balance_label", language=language))
        self.redeem_points_label.setText(t("invoice.redeem_points_label", language=language))
        self.points_earned_label.setText(t("invoice.points_earned_label", language=language))
        self.advanced_box.setTitle(t("invoice.advanced_options", language=language))
        self.recent_sold_box.setTitle(t("invoice.recent_sold_box", language=language))
        self.product_box.setTitle(t("invoice.products_box", language=language))
        self.barcode_input.setPlaceholderText(t("invoice.scan_barcode", language=language))
        self.search_input.setPlaceholderText(t("invoice.search_products", language=language))
        self.search_label.setText(t("invoice.search_label", language=language))
        self.barcode_label.setText(t("invoice.barcode_label", language=language))
        self.instant_invoice_toggle.setText("فاتورة فورية" if language == "ar" else "Instant invoice")
        self._update_recent_scans_label()
        self.qty_label.setText(t("invoice.qty_label", language=language))
        self.add_btn.setText(t("invoice.add_item", language=language))
        self.items_box.setTitle(t("invoice.items_box", language=language))
        self.items_table.setHorizontalHeaderLabels(
            [
                t("invoice.items_header_product", language=language),
                t("invoice.items_header_code", language=language),
                t("invoice.items_header_qty", language=language),
                t("invoice.items_header_unit_price", language=language),
                t("invoice.items_header_line_total", language=language),
                "-",
                "+",
            ]
        )
        self.recent_sold_table.setHorizontalHeaderLabels(
            [
                t("invoice.recent_sold_header_invoice", language=language),
                t("invoice.recent_sold_header_date", language=language),
                t("invoice.recent_sold_header_total", language=language),
                t("invoice.recent_sold_header_actions", language=language),
            ]
        )
        self.products_table.setHorizontalHeaderLabels(
            [
                t("invoice.products_header_name", language=language),
                t("invoice.products_header_sku", language=language),
                t("invoice.products_header_barcode", language=language),
                t("invoice.products_header_price", language=language),
                t("invoice.products_header_stock", language=language),
                "",
            ]
        )
        self.remove_btn.setText(t("invoice.remove_item", language=language))
        self.totals_box.setTitle(t("invoice.summary_box", language=language))
        self.breakdown_title.setText(t("invoice.breakdown", language=language))
        self.calculator_box.setTitle(t("invoice.calculator_box", language=language))
        self.copy_button.setText(t("invoice.copy_result", language=language))
        self.save_btn.setText(t("invoice.save_invoice", language=language))
        self.export_btn.setText(t("invoice.export_pdf", language=language))
        self.print_btn.setText(t("invoice.print", language=language))
        self.auto_print_after_save_checkbox.setText("طباعة تلقائية بعد الحفظ" if language == "ar" else "Auto print after save")
        self.print_preview_checkbox.setText("معاينة سريعة قبل الطباعة" if language == "ar" else "Quick preview before print")
        self.print_mode_combo.setItemText(0, "طابعة مباشرة" if language == "ar" else "Direct printer")
        self.print_mode_combo.setItemText(1, "PDF")
        self._refresh_printer_status_badge()
        self.clear_btn.setText(t("invoice.new", language=language))
        self._refresh_payment_methods()
        self._refresh_payment_statuses()
        self._refresh_delivery_companies()
        self._refresh_delivery_statuses()
        self.refresh_products()
        self._recalculate_totals()
        self._update_validation_state()

    def handle_scan(self, code: str) -> str:
        normalized_code = self._normalize_scan_text(code)
        product = find_product_by_code(normalized_code)
        if not product:
            self._show_scan_fallback_popup(normalized_code)
            return t("invoice.unknown_barcode", language=self._language, code=normalized_code)
        self._add_product_to_invoice(product, 1.0)
        product_name = choose_name(product.name_ar, product.name_en, language=self._language)
        self._register_recent_scan(product_name)
        return t(
            "invoice.added_product",
            language=self._language,
            name=product_name,
        )

    def _set_instant_invoice_mode(self, enabled: bool) -> None:
        self._instant_invoice_mode = enabled
        if enabled:
            self._focus_barcode_input()

    def _register_recent_scan(self, product_name: str) -> None:
        self._recent_scans.insert(0, product_name)
        self._recent_scans = self._recent_scans[:5]
        self._update_recent_scans_label()

    def _update_recent_scans_label(self) -> None:
        if not self._recent_scans:
            self.recent_scans_label.setText("آخر المنتجات الممسوحة: -")
            return
        self.recent_scans_label.setText("آخر المنتجات الممسوحة: " + " • ".join(self._recent_scans))

    def _show_scan_fallback_popup(self, code: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("باركود غير معروف")
        box.setText(f"لم يتم العثور على الباركود: {code}")
        create_btn = box.addButton("إنشاء عنصر سريع", QMessageBox.ButtonRole.AcceptRole)
        retry_btn = box.addButton("إعادة المحاولة", QMessageBox.ButtonRole.ActionRole)
        box.exec()
        if box.clickedButton() is create_btn:
            self._focus_product_search()
        elif box.clickedButton() is retry_btn:
            self._focus_barcode_input()

    def _refresh_summary_labels(self) -> None:
        subtotal = self._calculate_subtotal()
        discount_amount = self._calculate_discount_amount(subtotal)
        if self._discount_type() == "percent":
            discount_value = float(self.discount_input.value())
            discount_text = f"{discount_value:.2f}% ({discount_amount:.2f})"
        else:
            discount_text = f"{discount_amount:.2f}"
        self.discount_summary_label.setText(
            t("invoice.discount_summary", language=self._language, total=discount_text)
        )
        payment_method = self.payment_combo.currentText() or "-"
        self.payment_summary_label.setText(
            t("invoice.payment_summary", language=self._language, method=payment_method)
        )

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
            if source is self.barcode_input:
                return super().eventFilter(source, event)
            if source in {self.customer_search_input, self.customer_dropdown}:
                if self._handle_customer_dropdown_key(event):
                    return True
                return super().eventFilter(source, event)
            key = event.key()
            if source is self.products_table and key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._add_selected_product()
                return True
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
