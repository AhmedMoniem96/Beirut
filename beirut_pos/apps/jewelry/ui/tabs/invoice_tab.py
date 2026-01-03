"""Invoice tab for Jewelry app."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QElapsedTimer, QEvent, Qt, QTimer, QUrl
from PyQt6.QtGui import QBrush, QColor, QDesktopServices, QFont
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
        QApplication.instance().installEventFilter(self)

        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()
        header = QLabel("New Invoice (فاتورة جديدة)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        left_layout.addWidget(header)

        self.invoice_info_label = QLabel("Invoice No: Auto | رقم الفاتورة: تلقائي")
        left_layout.addWidget(self.invoice_info_label)

        form_box = QGroupBox("Invoice Info (بيانات الفاتورة)")
        form_layout = QFormLayout(form_box)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(8)
        form_layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.cashier_input = QLineEdit()
        self.cashier_input.setReadOnly(True)
        self.txn_type_combo = QComboBox()
        self.txn_type_combo.addItems(["Sale (بيع)", "Return (مرتجع)"])
        self.payment_combo = QComboBox()
        self.payment_combo.currentTextChanged.connect(self._refresh_summary_labels)
        self.order_source_combo = QComboBox()
        self.order_source_combo.addItem("In-Store (داخل المعرض)", "in_store")
        self.order_source_combo.addItem("Website (طلب أونلاين)", "website")
        self.order_source_combo.currentIndexChanged.connect(self._handle_order_source_change)
        self.website_order_label = QLabel("Website Order No (رقم طلب الموقع - اختياري)")
        self.website_order_input = QLineEdit()
        self.website_order_input.setPlaceholderText("Website Order No (optional)")
        self.website_order_input.setEnabled(False)
        self.discount_type_combo = QComboBox()
        self.discount_type_combo.addItem("Amount (قيمة)", "amount")
        self.discount_type_combo.addItem("Percent (%)", "percent")
        self.discount_type_combo.currentIndexChanged.connect(self._handle_discount_type_change)
        self.discount_input = QDoubleSpinBox()
        self.discount_input.setRange(0, 999999)
        self.discount_input.setDecimals(2)
        self.discount_input.valueChanged.connect(self._recalculate_totals)
        self.customer_search_input = QLineEdit()
        self.customer_search_input.setPlaceholderText("Search by phone or name...")
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
        self.customer_no_results_label = QLabel("No matches found.")
        self.customer_create_btn = QPushButton("Create new customer")
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
        self.customer_phone_input.setPlaceholderText("Phone (هاتف)")
        self.customer_email_input = QLineEdit()
        self.customer_email_input.setPlaceholderText("Email (بريد إلكتروني)")
        self.customer_notes_input = QLineEdit()
        self.customer_notes_input.setPlaceholderText("Notes (ملاحظات)")
        self.customer_points_label = QLabel("0")
        self.customer_search_input.installEventFilter(self)
        self.customer_dropdown.installEventFilter(self)
        self.customer_name_input.textChanged.connect(self._clear_customer_selection)
        self.customer_phone_input.textChanged.connect(self._clear_customer_selection)
        self.customer_email_input.textChanged.connect(self._clear_customer_selection)
        self.loyalty_redeem_input = QDoubleSpinBox()
        self.loyalty_redeem_input.setDecimals(2)
        self.loyalty_redeem_input.setRange(0, 999999)
        self.loyalty_redeem_input.valueChanged.connect(self._recalculate_totals)
        self.loyalty_earned_label = QLabel("0")
        self.customer_save_btn = QPushButton("Save Profile (حفظ الملف)")
        self.customer_save_btn.clicked.connect(self._save_customer_profile)
        self.notes_input = QTextEdit()
        self.notes_input.setMinimumHeight(80)
        self.notes_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.return_reason_input = QLineEdit()
        self.return_reason_input.setPlaceholderText("Reason (سبب المرتجع)")
        self.return_reason_input.setEnabled(False)
        self.txn_type_combo.currentIndexChanged.connect(self._handle_txn_type_change)

        form_layout.addRow("Cashier (الكاشير):", self.cashier_input)
        form_layout.addRow("Transaction (العملية):", self.txn_type_combo)
        form_layout.addRow("Payment Method (طريقة الدفع):", self.payment_combo)
        form_layout.addRow("Order Source (مصدر الطلب):", self.order_source_combo)
        form_layout.addRow(self.website_order_label, self.website_order_input)
        form_layout.addRow("Discount Type (نوع الخصم):", self.discount_type_combo)
        form_layout.addRow("Discount Value (قيمة الخصم):", self.discount_input)
        form_layout.addRow("Customer Search (بحث العميل):", customer_search_container)
        form_layout.addRow("Customer Name (العميل):", self.customer_name_input)
        form_layout.addRow("Customer Phone (الهاتف):", self.customer_phone_input)
        form_layout.addRow("Customer Email:", self.customer_email_input)
        form_layout.addRow("Customer Notes:", self.customer_notes_input)
        customer_actions = QHBoxLayout()
        customer_actions.addWidget(self.customer_save_btn)
        form_layout.addRow("", customer_actions)
        form_layout.addRow("Loyalty Balance (نقاط):", self.customer_points_label)
        form_layout.addRow("Redeem Points (خصم نقاط):", self.loyalty_redeem_input)
        form_layout.addRow("Points Earned (نقاط مكتسبة):", self.loyalty_earned_label)
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
        self.products_table.itemSelectionChanged.connect(self._update_add_state)

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
        self.items_table = QTableWidget(0, 7)
        self.items_table.setHorizontalHeaderLabels(
            ["Product", "Code", "Qty", "Unit Price", "Line Total", "-", "+"]
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
        left_layout.addStretch()

        left_container = QWidget()
        left_container.setLayout(left_layout)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_container)
        splitter.addWidget(left_scroll)

        totals_box = QGroupBox("Summary (ملخص)")
        totals_layout = QVBoxLayout(totals_box)
        self.subtotal_label = QLabel("Subtotal: 0.00")
        self.discount_summary_label = QLabel("Discount: 0.00")
        self.loyalty_summary_label = QLabel("Loyalty Redeem: 0.00")
        self.total_label = QLabel("Net Total: 0.00")
        self.payment_label = QLabel("Payment: -")
        totals_layout.addWidget(self.subtotal_label)
        totals_layout.addWidget(self.discount_summary_label)
        totals_layout.addWidget(self.loyalty_summary_label)
        totals_layout.addWidget(self.total_label)
        totals_layout.addWidget(self.payment_label)
        right_layout.addWidget(totals_box)

        calculator_box = QGroupBox("Calculator (آلة حاسبة)")
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
        copy_button = QPushButton("Copy Result")
        copy_button.clicked.connect(self._copy_calculator_result)
        keypad_layout.addWidget(copy_button, 4, 3, 1, 1)
        calculator_layout.addLayout(keypad_layout)
        right_layout.addWidget(calculator_box)

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
        self._apply_invoice_styles()

    def _initialize_cashier(self) -> None:
        user = get_current_user()
        if user:
            self.set_cashier_name(user.full_name)

    def _calculator_button_pressed(self, value: str) -> None:
        if value == "C":
            self.calculator_display.setText("0")
            return
        current = self.calculator_display.text()
        if current in {"0", "Error"} and value not in {"+", "-", "×", "÷", "."}:
            self.calculator_display.setText(value)
            return
        if current in {"0", "Error"} and value == ".":
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
            self.calculator_display.setText("Error")
            return
        try:
            result = eval(normalized, {"__builtins__": {}}, {})
        except (SyntaxError, ZeroDivisionError, TypeError, ValueError):
            self.calculator_display.setText("Error")
            return
        self.calculator_display.setText(f"{result:.2f}".rstrip("0").rstrip("."))

    def _copy_calculator_result(self) -> None:
        result = self.calculator_display.text().strip()
        if not result or result == "Error":
            return
        QApplication.clipboard().setText(result)

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
        name_font = QFont(self.products_table.font())
        name_font.setPointSize(name_font.pointSize() + 2)
        name_font.setBold(True)
        price_font = QFont(name_font)
        meta_font = QFont(self.products_table.font())
        meta_font.setPointSize(max(1, meta_font.pointSize() - 1))
        for product in self._products:
            row = self.products_table.rowCount()
            self.products_table.insertRow(row)
            out_of_stock = product.qty_on_hand <= 0
            low_stock = 0 < product.qty_on_hand <= product.min_qty
            name_item = QTableWidgetItem(f"{product.name_en} / {product.name_ar}")
            name_item.setFont(name_font)
            name_item.setData(Qt.ItemDataRole.UserRole, product.id)
            name_item.setData(Qt.ItemDataRole.UserRole + 1, out_of_stock)
            sku_item = QTableWidgetItem(product.sku)
            barcode_item = QTableWidgetItem(product.barcode)
            price_item = QTableWidgetItem(f"{product.price:.2f}")
            price_item.setFont(price_font)
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            stock_text = f"{product.qty_on_hand:.2f}"
            if out_of_stock:
                stock_text = f"{stock_text}  • Out"
            elif low_stock:
                stock_text = f"{stock_text}  ⚠ Low"
            stock_item = QTableWidgetItem(stock_text)
            for meta_item in (sku_item, barcode_item, stock_item):
                meta_item.setFont(meta_font)
                meta_item.setForeground(QColor("#6b7280"))
            if low_stock:
                stock_item.setBackground(QBrush(QColor("#fff7ed")))
                stock_item.setForeground(QColor("#b45309"))
            if out_of_stock:
                tooltip = "Out of stock — cannot add to invoice."
                for item in (name_item, sku_item, barcode_item, price_item, stock_item):
                    item.setToolTip(tooltip)
                    item.setBackground(QBrush(QColor("#f3f4f6")))
                    item.setForeground(QColor("#9ca3af"))
            self.products_table.setItem(row, 0, name_item)
            self.products_table.setItem(row, 1, sku_item)
            self.products_table.setItem(row, 2, barcode_item)
            self.products_table.setItem(row, 3, price_item)
            self.products_table.setItem(row, 4, stock_item)
        self._update_add_state()

    def _handle_txn_type_change(self) -> None:
        is_return = self.txn_type_combo.currentIndex() == 1
        self.return_reason_input.setEnabled(is_return)
        self.loyalty_redeem_input.setEnabled(not is_return)
        if is_return:
            self.loyalty_redeem_input.setValue(0.0)
        self._refresh_summary_labels()

    def _handle_order_source_change(self) -> None:
        if self._website_orders_enabled:
            self.order_source_combo.setCurrentIndex(self.order_source_combo.findData("website"))
            return
        is_website = self.order_source_combo.currentData() == "website"
        self.website_order_input.setEnabled(is_website)
        if not is_website:
            self.website_order_input.clear()

    def _apply_website_order_settings(self) -> None:
        if self._website_orders_enabled:
            website_index = self.order_source_combo.findData("website")
            if website_index >= 0:
                self.order_source_combo.setCurrentIndex(website_index)
            self.order_source_combo.setEnabled(False)
            self.website_order_input.clear()
            self.website_order_input.setEnabled(False)
            self.website_order_input.setVisible(False)
            self.website_order_label.setVisible(False)
        else:
            self.order_source_combo.setEnabled(True)
            self.website_order_input.setVisible(True)
            self.website_order_label.setVisible(True)
            self._handle_order_source_change()

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
        base = f"{customer.name} • {customer.phone} • نقاط {points:.0f}"
        if customer.email:
            return f"{base} • {customer.email}"
        return base

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
            QMessageBox.warning(self, "Missing", "Customer name and phone are required.")
            return
        self._customer_id = save_customer(name, phone, email)
        self._customer_points = get_loyalty_balance(self._customer_id)
        self.customer_points_label.setText(f"{self._customer_points:.2f}")
        self.customer_search_input.blockSignals(True)
        self.customer_search_input.setText(f"{name} ({phone})")
        self.customer_search_input.blockSignals(False)
        QMessageBox.information(self, "Saved", "Customer profile saved.")

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
            QMessageBox.warning(self, "Select", "Please select a product.")
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
        self.subtotal_label.setText(f"Subtotal: {subtotal:.2f}")
        self.total_label.setText(f"Net Total: {total:.2f}")
        self.loyalty_summary_label.setText(f"Loyalty Redeem: {loyalty_redeem:.2f}")
        earned = 0 if self.txn_type_combo.currentIndex() == 1 else int(total)
        self.loyalty_earned_label.setText(f"{earned}")
        self._refresh_summary_labels()

    def _calculate_subtotal(self) -> float:
        subtotal = 0.0
        for row in range(self.items_table.rowCount()):
            subtotal += float(self.items_table.item(row, self.ITEM_COL_LINE_TOTAL).text())
        return subtotal

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
            QMessageBox.warning(self, "Missing Items", "Add at least one item.")
            return
        cashier = self.cashier_input.text().strip() or "N/A"
        txn_type = "return" if self.txn_type_combo.currentIndex() == 1 else "sale"
        customer_name = self.customer_name_input.text().strip()
        customer_phone = self.customer_phone_input.text().strip()
        customer_email = self.customer_email_input.text().strip()
        customer_id = None
        if customer_name or customer_phone:
            if not customer_name or not customer_phone:
                QMessageBox.warning(self, "Missing", "Customer name and phone are required.")
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
        if order_source == "website" and self.website_order_input.isVisible():
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
        self._last_invoice_no = None
        self.invoice_info_label.setText("Invoice No: Auto | رقم الفاتورة: تلقائي")
        self._apply_website_order_settings()
        self._recalculate_totals()

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
            self.add_btn.setToolTip("Out of stock items cannot be added.")
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
            #jewelryInvoiceTab QLabel {
                padding: 2px 0;
            }
            #jewelryInvoiceTab QTableWidget::item {
                padding: 4px;
            }
            """
        )

    def handle_scan(self, code: str) -> str:
        normalized_code = self._normalize_scan_text(code)
        product = find_product_by_code(normalized_code)
        if not product:
            return f"Unknown barcode: {normalized_code}"
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
            if source in {self.customer_search_input, self.customer_dropdown}:
                if self._handle_customer_dropdown_key(event):
                    return True
                return super().eventFilter(source, event)
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
