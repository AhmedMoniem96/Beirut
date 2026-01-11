"""Invoice tab for Jewelry app."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QElapsedTimer, QEvent, Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
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
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QFrame,
)

from ...services.db import (
    JewelryInvoiceItem,
    create_invoice,
    fetch_invoice_details,
    find_product_by_code,
    get_loyalty_balance,
    list_payment_methods,
    list_products,
    search_customers,
    save_customer,
)
from ...services.pdf_exports import GalleryInfo, export_invoice_pdf
from ...services.session import get_current_user
from ...services.settings import load_gallery_settings
from ...services.i18n import choose_name, get_ui_language, t


class InvoiceTab(QWidget):
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
        self._gallery_settings = load_gallery_settings()
        self._website_orders_enabled = self._gallery_settings.website_orders_enabled
        self._language = get_ui_language()
        QApplication.instance().installEventFilter(self)

        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        header = QLabel()
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        left_layout.addWidget(header)
        self.header_label = header

        self.invoice_info_label = QLabel()
        left_layout.addWidget(self.invoice_info_label)

        form_box = QGroupBox()
        self.form_box = form_box
        self._form_layout = QFormLayout(form_box)
        self._form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        self._form_layout.setHorizontalSpacing(12)
        self._form_layout.setVerticalSpacing(8)
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
        self.website_order_label = QLabel()
        self.website_order_input = QLineEdit()
        self.website_order_input.setEnabled(False)
        self.website_order_panel = QWidget()
        website_layout = QFormLayout(self.website_order_panel)
        website_layout.setContentsMargins(0, 0, 0, 0)
        website_layout.setHorizontalSpacing(12)
        website_layout.setVerticalSpacing(8)
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
        discount_layout.setHorizontalSpacing(12)
        discount_layout.setVerticalSpacing(8)
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
        dropdown_layout.setSpacing(4)
        self.customer_dropdown = QListWidget()
        self.customer_dropdown.setMaximumHeight(160)
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
        customer_search_layout.setSpacing(4)
        customer_search_layout.addWidget(self.customer_search_input)
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
        notes_layout.setHorizontalSpacing(12)
        notes_layout.setVerticalSpacing(8)
        self.notes_label = QLabel()
        notes_layout.addRow(self.notes_label, self.notes_input)
        self.return_reason_input = QLineEdit()
        self.return_reason_input.setEnabled(False)
        self.return_panel = QWidget()
        return_layout = QFormLayout(self.return_panel)
        return_layout.setContentsMargins(0, 0, 0, 0)
        return_layout.setHorizontalSpacing(12)
        return_layout.setVerticalSpacing(8)
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
        self.customer_search_label = QLabel()
        self.customer_name_label = QLabel()
        self.customer_phone_label = QLabel()
        self.customer_email_label = QLabel()
        self.customer_notes_label = QLabel()
        self._form_layout.addRow(self.cashier_label, self.cashier_input)
        self._form_layout.addRow(self.transaction_label, self.txn_type_combo)
        self._form_layout.addRow(self.payment_method_label, self.payment_combo)
        self._form_layout.addRow(self.order_source_label, self.order_source_combo)
        self._form_layout.addRow(self.customer_search_label, customer_search_container)
        self._form_layout.addRow(self.customer_name_label, self.customer_name_input)
        self._form_layout.addRow(self.customer_phone_label, self.customer_phone_input)
        self._form_layout.addRow(self.customer_email_label, self.customer_email_input)
        self._form_layout.addRow(self.customer_notes_label, self.customer_notes_input)
        customer_actions = QHBoxLayout()
        customer_actions.addWidget(self.customer_save_btn)
        self._form_layout.addRow("", customer_actions)
        self.loyalty_balance_label = QLabel()
        self.redeem_points_label = QLabel()
        self.points_earned_label = QLabel()
        self._form_layout.addRow(self.loyalty_balance_label, self.customer_points_label)
        self._form_layout.addRow(self.redeem_points_label, self.loyalty_redeem_input)
        self._form_layout.addRow(self.points_earned_label, self.loyalty_earned_label)
        advanced_controls = QWidget()
        advanced_controls_layout = QHBoxLayout(advanced_controls)
        advanced_controls_layout.setContentsMargins(0, 0, 0, 0)
        advanced_controls_layout.setSpacing(8)
        advanced_controls_layout.addWidget(self.discount_toggle)
        advanced_controls_layout.addWidget(self.notes_toggle)
        advanced_controls_layout.addWidget(self.return_toggle)
        advanced_controls_layout.addWidget(self.website_toggle)
        advanced_controls_layout.addStretch()
        self.advanced_options_label = QLabel()
        self._form_layout.addRow(self.advanced_options_label, advanced_controls)
        self._form_layout.addRow(self.discount_panel)
        self._form_layout.addRow(self.notes_panel)
        self._form_layout.addRow(self.return_panel)
        self._form_layout.addRow(self.website_order_panel)
        left_layout.addWidget(form_box)

        product_box = QGroupBox()
        self.product_box = product_box
        product_layout = QGridLayout(product_box)
        self.barcode_input = QLineEdit()
        self.search_label = QLabel()
        self.barcode_label = QLabel()
        self.barcode_input.setPlaceholderText("")
        self.barcode_input.returnPressed.connect(self._handle_barcode_submit)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("")
        self.search_input.textChanged.connect(self.refresh_products)
        product_layout.addWidget(self.search_label, 0, 0)
        product_layout.addWidget(self.search_input, 0, 1, 1, 2)
        product_layout.addWidget(self.barcode_label, 1, 0)
        product_layout.addWidget(self.barcode_input, 1, 1, 1, 2)

        self.products_table = QTableWidget(0, 6)
        self.products_table.setHorizontalHeaderLabels(["", "", "", "", "", ""])
        self.products_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.products_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.products_table.setAlternatingRowColors(True)
        self.products_table.cellDoubleClicked.connect(self._add_selected_product)
        self.products_table.itemSelectionChanged.connect(self._update_add_state)

        self.qty_input = QSpinBox()
        self.qty_input.setRange(1, 1000)
        self.add_btn = QPushButton()
        self.add_btn.clicked.connect(self._add_selected_product)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._add_selected_product)

        product_layout.addWidget(self.products_table, 2, 0, 1, 3)
        self.qty_label = QLabel()
        product_layout.addWidget(self.qty_label, 3, 0)
        product_layout.addWidget(self.qty_input, 3, 1)
        product_layout.addWidget(self.add_btn, 3, 2)
        left_layout.addWidget(product_box)

        items_box = QGroupBox()
        self.items_box = items_box
        items_layout = QVBoxLayout(items_box)
        self.items_table = QTableWidget(0, 7)
        self.items_table.setHorizontalHeaderLabels(["", "", "", "", "", "-", "+"])
        self.items_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.items_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.items_table.setAlternatingRowColors(True)
        items_layout.addWidget(self.items_table)

        btn_row = QHBoxLayout()
        self.remove_btn = QPushButton()
        self.remove_btn.clicked.connect(self._remove_selected_item)
        btn_row.addWidget(self.remove_btn)
        items_layout.addLayout(btn_row)
        left_layout.addWidget(items_box)
        left_layout.addStretch()

        left_container = QWidget()
        left_container.setLayout(left_layout)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_container)
        splitter.addWidget(left_scroll)

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
        breakdown_layout.setSpacing(4)
        self.subtotal_label = QLabel()
        self.discount_summary_label = QLabel()
        self.loyalty_summary_label = QLabel()
        breakdown_layout.addWidget(self.subtotal_label)
        breakdown_layout.addWidget(self.discount_summary_label)
        breakdown_layout.addWidget(self.loyalty_summary_label)
        totals_layout.addWidget(breakdown_frame)
        self.payment_summary_label = QLabel()
        totals_layout.addWidget(self.payment_summary_label)
        right_layout.addWidget(totals_box)

        calculator_box = QGroupBox()
        self.calculator_box = calculator_box
        calculator_layout = QVBoxLayout(calculator_box)
        self.calculator_display = QLineEdit("0")
        self.calculator_display.setReadOnly(True)
        self.calculator_display.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.calculator_display.setMinimumHeight(32)
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
        right_layout.addWidget(calculator_box)

        actions_layout = QVBoxLayout()
        self.save_btn = QPushButton()
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.clicked.connect(self._save_invoice)
        self.validation_label = QLabel("")
        self.validation_label.setObjectName("validationLabel")
        self.validation_label.setWordWrap(True)
        self.validation_label.setVisible(False)
        self.export_btn = QPushButton()
        self.export_btn.clicked.connect(self._export_invoice_pdf)
        self.print_btn = QPushButton()
        self.print_btn.clicked.connect(self._print_invoice)
        self.clear_btn = QPushButton()
        self.clear_btn.clicked.connect(self._clear_invoice)
        actions_layout.addWidget(self.save_btn)
        actions_layout.addWidget(self.validation_label)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addWidget(self.print_btn)
        actions_layout.addWidget(self.clear_btn)
        right_layout.addLayout(actions_layout)
        right_layout.addStretch()
        right_container = QWidget()
        right_container.setLayout(right_layout)
        splitter.addWidget(right_container)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        self._refresh_payment_methods()
        self.refresh_products()
        self._initialize_cashier()
        self._customer_id: Optional[str] = None
        self._customer_points: float = 0.0
        self._configure_shortcuts()
        self._configure_focus_order()
        self._apply_invoice_styles()
        self._update_advanced_panels()
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

    def refresh_products(self, _text: str | None = None) -> None:
        search = self.search_input.text().strip()
        self._products = list_products(search=search if search else None)
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

    def _update_advanced_panels(self) -> None:
        self.discount_panel.setVisible(self.discount_toggle.isChecked())
        self.notes_panel.setVisible(self.notes_toggle.isChecked())
        self.return_panel.setVisible(self.return_toggle.isChecked())
        self.website_order_panel.setVisible(self.website_toggle.isChecked())
        self._update_return_reason_state()
        self._update_website_order_state()

    def _update_return_reason_state(self) -> None:
        is_return = self.txn_type_combo.currentIndex() == 1
        self.return_reason_input.setEnabled(is_return and self.return_toggle.isChecked())

    def _update_website_order_state(self) -> None:
        if not self.website_toggle.isChecked():
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

    def _calculate_discount_amount(self, subtotal: float) -> float:
        discount_value = float(self.discount_input.value())
        if self._discount_type() == "percent":
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
        term = self.customer_search_input.text().strip()
        if not term:
            return
        normalized = term.replace(" ", "")
        is_phone = normalized.lstrip("+").isdigit()
        self._customer_id = None
        self._customer_points = 0.0
        self.customer_points_label.setText("0")
        if is_phone:
            self.customer_phone_input.setText(term)
            self.customer_name_input.setFocus()
        else:
            self.customer_name_input.setText(term)
            self.customer_phone_input.setFocus()
        self.customer_email_input.clear()
        self._hide_customer_dropdown()

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
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("invoice.profile_saved", language=self._language),
        )

    def _configure_shortcuts(self) -> None:
        search_shortcut = QShortcut(QKeySequence("/"), self)
        search_shortcut.activated.connect(self._focus_product_search)

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
        subtotal = 0.0
        for row in range(self.items_table.rowCount()):
            subtotal += float(self.items_table.item(row, self.ITEM_COL_LINE_TOTAL).text())
        discount = self._calculate_discount_amount(subtotal)
        loyalty_redeem = self._loyalty_redeem_amount(subtotal, discount)
        total = max(subtotal - discount - loyalty_redeem, 0.0)
        self.subtotal_label.setText(
            t("invoice.subtotal", language=self._language, total=f"{subtotal:.2f}")
        )
        self.total_label.setText(t("invoice.net_total", language=self._language, total=f"{total:.2f}"))
        self.loyalty_summary_label.setText(
            t("invoice.loyalty_summary", language=self._language, total=f"{loyalty_redeem:.2f}")
        )
        earned = 0 if self.txn_type_combo.currentIndex() == 1 else int(total)
        self.loyalty_earned_label.setText(f"{earned}")
        self._refresh_summary_labels()
        self._update_validation_state()

    def _calculate_subtotal(self) -> float:
        subtotal = 0.0
        for row in range(self.items_table.rowCount()):
            subtotal += float(self.items_table.item(row, self.ITEM_COL_LINE_TOTAL).text())
        return subtotal

    def _validation_message(self) -> str:
        if self.items_table.rowCount() == 0:
            return t("invoice.validation_items", language=self._language)
        customer_name = self.customer_name_input.text().strip()
        customer_phone = self.customer_phone_input.text().strip()
        if (customer_name or customer_phone) and not (customer_name and customer_phone):
            return t("invoice.validation_customer", language=self._language)
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
        subtotal = self._calculate_subtotal()
        discount_type = self._discount_type()
        discount_value = float(self.discount_input.value())
        discount = self._calculate_discount_amount(subtotal)
        loyalty_redeem = 0.0 if txn_type == "return" else float(self.loyalty_redeem_input.value())
        total = max(subtotal - discount - loyalty_redeem, 0.0)
        loyalty_earned = 0 if txn_type == "return" else int(total)
        payment_method = self.payment_combo.currentText()
        order_source = "website" if self._website_orders_enabled else (self.order_source_combo.currentData() or "in_store")
        website_order_ref = ""
        if order_source == "website":
            website_order_ref = self.website_order_input.text().strip()
        if order_source != "website":
            website_order_ref = ""
        notes = self.notes_input.toPlainText().strip()
        return_reason = self.return_reason_input.text().strip() if txn_type == "return" else ""
        items = self._collect_items()
        invoice_no = create_invoice(
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
            order_source,
            website_order_ref,
            notes,
            return_reason,
            items,
        )
        self._last_invoice_no = invoice_no
        self.invoice_info_label.setText(t("invoice.info_number", language=self._language, invoice_no=invoice_no))
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("invoice.saved_message", language=self._language, invoice_no=invoice_no),
        )
        self.refresh_products()

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
        tmp_path = Path.cwd() / f"{self._last_invoice_no}.pdf"
        invoice, items = fetch_invoice_details(self._last_invoice_no)
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

    def _clear_invoice(self) -> None:
        self.items_table.setRowCount(0)
        self.discount_type_combo.setCurrentIndex(0)
        self.discount_input.setValue(0.0)
        self.loyalty_redeem_input.setValue(0.0)
        self.customer_name_input.clear()
        self.customer_phone_input.clear()
        self.customer_email_input.clear()
        self.customer_notes_input.clear()
        self.customer_points_label.setText("0")
        self.customer_search_input.clear()
        self._hide_customer_dropdown()
        self.loyalty_earned_label.setText("0")
        self._customer_id = None
        self._customer_points = 0.0
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
            QTableWidgetItem(f"{product.name_en} / {product.name_ar}"),
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
        minus_btn.setFixedWidth(32)
        plus_btn.setFixedWidth(32)
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

    def _handle_barcode_submit(self) -> None:
        code = self.barcode_input.text().strip()
        if not code:
            return
        self.barcode_input.clear()
        product = find_product_by_code(code)
        if not product:
            self._dispatch_scan(code)
            self._focus_barcode_input()
            return
        self._add_product_to_invoice(product, float(self.qty_input.value()))

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
        self.customer_email_label.setText(t("invoice.customer_email_label", language=language))
        self.customer_notes_label.setText(t("invoice.customer_notes_label", language=language))
        self.loyalty_balance_label.setText(t("invoice.loyalty_balance_label", language=language))
        self.redeem_points_label.setText(t("invoice.redeem_points_label", language=language))
        self.points_earned_label.setText(t("invoice.points_earned_label", language=language))
        self.advanced_options_label.setText(t("invoice.advanced_options", language=language))
        self.product_box.setTitle(t("invoice.products_box", language=language))
        self.barcode_input.setPlaceholderText(t("invoice.scan_barcode", language=language))
        self.search_input.setPlaceholderText(t("invoice.search_products", language=language))
        self.search_label.setText(t("invoice.search_label", language=language))
        self.barcode_label.setText(t("invoice.barcode_label", language=language))
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
        self.clear_btn.setText(t("invoice.new_invoice", language=language))
        self._refresh_payment_methods()
        self.refresh_products()
        self._recalculate_totals()
        self._update_validation_state()

    def handle_scan(self, code: str) -> str:
        normalized_code = self._normalize_scan_text(code)
        product = find_product_by_code(normalized_code)
        if not product:
            return t("invoice.unknown_barcode", language=self._language, code=normalized_code)
        self._add_product_to_invoice(product, 1.0)
        return t(
            "invoice.added_product",
            language=self._language,
            name=choose_name(product.name_ar, product.name_en, language=self._language),
        )

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
