"""Reports tab for Jewelry app."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QDate, QRectF, Qt
from PyQt6.QtGui import QColor, QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QFileDialog,
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from beirut_pos.utils.excel import write_protected_workbook

from ...services.db import fetch_shift_session_for_date, list_products, save_shift_session
from ...services.pdf_exports import GalleryInfo, export_daily_report_pdf
from ...services.reports import customer_aggregates, inventory_value_estimate, lowest_products, payment_breakdown, production_history, returns_aggregate, sales_aggregate, stock_alerts, top_products, top_products_by_revenue
from ...services.session import get_current_user
from ...services.settings import load_gallery_settings
from ...services.i18n import choose_name, get_ui_language, t
from .base_tab import BaseTabContainer


@dataclass
class ReportData:
    report_date: str
    report_number: str
    cashier: str
    shift_open: str
    shift_close: str
    opening_cash: float
    closing_cash_actual: float
    expected_cash: float
    notes: str
    sales_summary: Tuple[int, float, float, float]
    payment_breakdown: List[Tuple[str, float]]
    returns_summary: Tuple[int, float]
    return_reasons: List[Tuple[str, int, float]]
    top_products: List[Tuple[str, str, float]]
    low_products: List[Tuple[str, str, float]]
    out_of_stock: List[Tuple[str, str, str, float, float]]
    near_out: List[Tuple[str, str, str, float, float]]


class MostSellingChart(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: List[Tuple[str, float]] = []
        self._bar_color = QColor("#5B8FF9")
        self._text_color = QColor("#2C2C2C")
        self._empty_color = QColor("#7A7A7A")

    def set_data(self, data: List[Tuple[str, float]]) -> None:
        self._data = data
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(16, 16, -16, -16)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        if not self._data:
            painter.setPen(self._empty_color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "—")
            return

        font_metrics = QFontMetrics(self.font())
        label_width = max(
            (font_metrics.horizontalAdvance(label) for label, _ in self._data),
            default=0,
        )
        value_area = 48
        bar_rect = rect.adjusted(label_width + 12, 0, -value_area, 0)
        if bar_rect.width() <= 0:
            return

        max_value = max((value for _, value in self._data), default=0)
        if max_value <= 0:
            max_value = 1

        spacing = 8
        bar_height = max(
            12.0,
            (bar_rect.height() - spacing * (len(self._data) - 1)) / max(len(self._data), 1),
        )

        painter.setPen(self._text_color)
        for index, (label, value) in enumerate(self._data):
            y_offset = bar_rect.top() + index * (bar_height + spacing)
            width = (value / max_value) * bar_rect.width()
            bar = QRectF(bar_rect.left(), y_offset, width, bar_height)
            label_rect = QRectF(rect.left(), y_offset, label_width, bar_height)
            value_rect = QRectF(bar_rect.right() + 6, y_offset, value_area - 6, bar_height)

            painter.setPen(self._text_color)
            painter.drawText(
                label_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                label,
            )

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self._bar_color)
            painter.drawRoundedRect(bar, 4, 4)

            painter.setPen(self._text_color)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawText(
                value_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"{value:.2f}",
            )


class ReportsTab(BaseTabContainer):
    def __init__(self) -> None:
        super().__init__()
        self._last_report: Optional[ReportData] = None
        self._language = get_ui_language()
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDisplayFormat("dd/MM/yyyy")
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.dateChanged.connect(self._load_shift_from_db)
        self.date_filter.dateChanged.connect(lambda *_: self._generate_report())
        self.product_filter_combo = QComboBox()
        self.product_filter_combo.currentIndexChanged.connect(self._generate_report)
        self.customer_filter_input = QLineEdit()
        self.customer_filter_input.textChanged.connect(self._generate_report)
        self.date_from_filter = QDateEdit()
        self.date_from_filter.setCalendarPopup(True)
        self.date_from_filter.setDisplayFormat("dd/MM/yyyy")
        self.date_from_filter.setDate(QDate.currentDate())
        self.date_from_filter.dateChanged.connect(lambda *_: self._generate_report())
        self.date_to_filter = QDateEdit()
        self.date_to_filter.setCalendarPopup(True)
        self.date_to_filter.setDisplayFormat("dd/MM/yyyy")
        self.date_to_filter.setDate(QDate.currentDate())
        self.date_to_filter.dateChanged.connect(lambda *_: self._generate_report())
        self.expense_category_filter = QComboBox()
        self.expense_category_filter.addItem("All", "")
        for category in ["Material Purchase", "Electricity Bill", "Shop Bill", "Worker Wage", "Rent", "Packaging", "Maintenance", "Other"]:
            self.expense_category_filter.addItem(category, category)
        self.expense_vendor_worker_filter = QLineEdit()
        self.expense_payment_filter = QLineEdit()
        self.expense_category_filter.currentIndexChanged.connect(self._generate_report)
        self.expense_vendor_worker_filter.textChanged.connect(self._generate_report)
        self.expense_payment_filter.textChanged.connect(self._generate_report)
        self.date_label = QLabel()
        self.product_filter_label = QLabel()
        self.summary_filter_row = self._build_filters_row(include_product=True)
        self.returns_filter_row = self._build_filters_row(include_product=True)
        self.products_filter_row = self._build_filters_row(include_product=True)
        self.stock_filter_row = self._build_filters_row(include_product=False)

        shift_box = QGroupBox()
        self.shift_box = shift_box
        shift_layout = QFormLayout(shift_box)
        self.cashier_input = QLineEdit()
        self.cashier_input.setReadOnly(True)
        self.open_time_input = QDateTimeEdit()
        self.open_time_input.setCalendarPopup(True)
        self.open_time_input.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.close_time_input = QDateTimeEdit()
        self.close_time_input.setCalendarPopup(True)
        self.close_time_input.setDisplayFormat("dd/MM/yyyy HH:mm")
        self.opening_cash_input = QDoubleSpinBox()
        self.opening_cash_input.setRange(0, 999999)
        self.opening_cash_input.setDecimals(2)
        self.closing_cash_input = QDoubleSpinBox()
        self.closing_cash_input.setRange(0, 999999)
        self.closing_cash_input.setDecimals(2)
        self.opening_cash_input.valueChanged.connect(self._refresh_cash_diff)
        self.closing_cash_input.valueChanged.connect(self._refresh_cash_diff)
        self.expected_cash_label = QLabel()
        self.diff_label = QLabel()
        self.notes_input = QTextEdit()
        self.notes_input.setMinimumHeight(90)
        self.notes_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.cashier_label = QLabel()
        self.open_time_label = QLabel()
        self.close_time_label = QLabel()
        self.opening_cash_label = QLabel()
        self.actual_cash_label = QLabel()
        self.expected_label = QLabel()
        self.over_short_label = QLabel()
        self.notes_label = QLabel()
        shift_layout.addRow(self.cashier_label, self.cashier_input)
        shift_layout.addRow(self.open_time_label, self.open_time_input)
        shift_layout.addRow(self.close_time_label, self.close_time_input)
        shift_layout.addRow(self.opening_cash_label, self.opening_cash_input)
        shift_layout.addRow(self.actual_cash_label, self.closing_cash_input)
        shift_layout.addRow(self.expected_label, self.expected_cash_label)
        shift_layout.addRow(self.over_short_label, self.diff_label)
        shift_layout.addRow(self.notes_label, self.notes_input)

        save_shift_btn = QPushButton()
        save_shift_btn.clicked.connect(self._save_shift_session)
        self.save_shift_btn = save_shift_btn

        self.summary_label = QLabel()
        self.summary_cards: Dict[str, QLabel] = {}

        self.payment_table = QTableWidget(0, 2)
        self.returns_table = QTableWidget(0, 3)
        self.top_table = QTableWidget(0, 4)
        self.low_table = QTableWidget(0, 4)
        self.customer_table = QTableWidget(0, 5)
        self.stock_table = QTableWidget(0, 5)
        self.expense_category_table = QTableWidget(0, 3)
        self.expenses_list_table = QTableWidget(0, 6)
        self.material_purchases_table = QTableWidget(0, 4)
        self.worker_wages_table = QTableWidget(0, 3)
        for table in [
            self.payment_table,
            self.returns_table,
            self.top_table,
            self.low_table,
            self.customer_table,
            self.stock_table,
            self.expense_category_table,
            self.expenses_list_table,
            self.material_purchases_table,
            self.worker_wages_table,
        ]:
            table.setAlternatingRowColors(True)
            table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self._style_report_table(table)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._generate_report)

        export_layout = QHBoxLayout()
        self.export_pdf_btn = QPushButton()
        self.export_pdf_btn.clicked.connect(self._export_pdf)
        self.export_excel_btn = QPushButton()
        self.export_excel_btn.clicked.connect(self._export_excel)
        export_layout.addWidget(self.export_pdf_btn)
        export_layout.addWidget(self.export_excel_btn)

        self.tabs = QTabWidget()
        self.payment_breakdown_label = QLabel()
        self.return_reasons_label = QLabel()
        self.top_products_label = QLabel()
        self.low_products_label = QLabel()
        self.stock_alerts_label = QLabel()
        self.tabs.addTab(self._build_summary_tab(export_layout), "")
        self.tabs.addTab(self._build_products_tab(), "")
        self.tabs.addTab(self._build_customers_tab(), "")
        self.tabs.addTab(self._build_returns_tab(), "")
        self.tabs.addTab(self._build_stock_tab(), "")
        self.tabs.addTab(self._build_expenses_tab(), "")
        layout.addWidget(self.tabs)

        self.set_page_content_widget(content)
        self._reload_product_filter()
        self.apply_language(self._language)
        self._initialize_shift_defaults()
        self._generate_report()
        self._initialize_cashier()

    def _initialize_shift_defaults(self) -> None:
        now = datetime.now()
        self.open_time_input.setDateTime(datetime.combine(now.date(), time(9, 0)))
        self.close_time_input.setDateTime(now)
        self._load_shift_from_db()

    def _initialize_cashier(self) -> None:
        user = get_current_user()
        if user and not self.cashier_input.text().strip():
            self.cashier_input.setText(user.full_name)

    def _build_filters_row(self, include_product: bool = True) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.date_label)
        row.addWidget(self.date_filter)
        if include_product:
            row.addWidget(self.product_filter_label)
            row.addWidget(self.product_filter_combo)
        row.addStretch()
        return row

    def _style_report_table(self, table: QTableWidget) -> None:
        table.setAlternatingRowColors(True)
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        table.setMinimumHeight(160)
        table.verticalHeader().setDefaultSectionSize(28)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(table.columnCount() - 1, QHeaderView.ResizeMode.Stretch)

    def _build_summary_tab(self, export_layout: QHBoxLayout) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)
        vbox.addLayout(self.summary_filter_row)
        cards_grid = QGridLayout()
        cards_grid.setHorizontalSpacing(8)
        cards_grid.setVerticalSpacing(8)
        cards_grid.setContentsMargins(0, 0, 0, 0)
        card_specs = [
            ("total_sales", "💰", "Total Sales"),
            ("net_revenue", "🧾", "Net Revenue"),
            ("total_expenses", "💸", "Total Expenses"),
            ("net_cash_profit", "📈", "Net Cash Profit"),
            ("returns", "↩️", "Returns"),
            ("top_product", "🏷️", "Top Product"),
            ("top_customer", "👤", "Top Customer"),
            ("low_stock_alerts", "⚠️", "Low Stock Alerts"),
        ]
        for i, (key, icon, title) in enumerate(card_specs):
            card = self._create_summary_card(title, icon)
            self.summary_cards[key] = card
            cards_grid.addWidget(card.parentWidget(), i // 4, i % 4)
        vbox.addLayout(cards_grid)
        vbox.addWidget(self.summary_label)
        vbox.addWidget(self.payment_breakdown_label)
        vbox.addWidget(self.payment_table, 1)
        vbox.addLayout(export_layout)
        return tab

    def _create_summary_card(self, title: str, icon: str) -> QLabel:
        frame = QFrame()
        frame.setStyleSheet("QFrame {border: 1px solid #d9d9d9; border-radius: 8px; background: #ffffff;}")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)
        thumb = QLabel(icon)
        thumb.setStyleSheet("font-size: 18px;")
        layout.addWidget(thumb, 0, Qt.AlignmentFlag.AlignTop)
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(1)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 11px; color: #666;")
        value_label = QLabel("--")
        value_label.setStyleSheet("font-size: 14px; font-weight: 600; color: #1f2937;")
        value_label.setWordWrap(True)
        subtitle_label = QLabel("")
        subtitle_label.setStyleSheet("font-size: 10px; color: #888;")
        subtitle_label.setProperty("summarySubtitle", True)
        text_col.addWidget(title_label)
        text_col.addWidget(value_label)
        text_col.addWidget(subtitle_label)
        layout.addLayout(text_col, 1)
        frame.setMinimumHeight(74)
        frame.setMaximumHeight(90)
        value_label.setProperty("subtitleLabel", subtitle_label)
        return value_label

    def _set_summary_card(self, key: str, value: str, subtitle: str = "") -> None:
        card_label = self.summary_cards.get(key)
        if card_label is None:
            return
        card_label.setText(value)
        subtitle_label = card_label.property("subtitleLabel")
        if isinstance(subtitle_label, QLabel):
            subtitle_label.setText(subtitle)
            subtitle_label.setVisible(bool(subtitle))

    def _build_returns_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)
        vbox.addLayout(self.returns_filter_row)
        vbox.addWidget(self.return_reasons_label)
        vbox.addWidget(self.returns_table, 1)
        return tab

    def _build_products_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)
        vbox.addLayout(self.products_filter_row)
        vbox.addWidget(self.top_products_label)
        vbox.addWidget(self.top_table, 1)
        vbox.addWidget(self.low_products_label)
        vbox.addWidget(self.low_table, 1)
        return tab

    def _build_customers_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)
        vbox.addWidget(self.customer_table, 1)
        return tab

    def _build_stock_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        vbox.setContentsMargins(12, 12, 12, 12)
        vbox.setSpacing(10)
        vbox.addLayout(self.stock_filter_row)
        vbox.addWidget(self.stock_alerts_label)
        vbox.addWidget(self.stock_table, 1)
        return tab

    def _build_expenses_tab(self) -> QWidget:
        tab = QWidget()
        vbox = QVBoxLayout(tab)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("From Date:")); filters.addWidget(self.date_from_filter)
        filters.addWidget(QLabel("To Date:")); filters.addWidget(self.date_to_filter)
        filters.addWidget(QLabel("Category:")); filters.addWidget(self.expense_category_filter)
        filters.addWidget(QLabel("Vendor/Worker:")); filters.addWidget(self.expense_vendor_worker_filter)
        filters.addWidget(QLabel("Payment Method:")); filters.addWidget(self.expense_payment_filter)
        vbox.addLayout(filters)

        self.total_revenue_kpi = QLabel()
        self.total_expenses_kpi = QLabel()
        self.net_profit_kpi = QLabel()
        self.product_margin_kpi = QLabel()
        self.bills_kpi = QLabel()
        self.worker_wages_kpi = QLabel()
        kpi = QGridLayout()
        for i,w in enumerate([self.total_revenue_kpi,self.total_expenses_kpi,self.net_profit_kpi,self.product_margin_kpi,self.bills_kpi,self.worker_wages_kpi]):
            w.setStyleSheet("padding: 8px; border: 1px solid #d9d9d9; border-radius: 6px;")
            kpi.addWidget(w, i//3, i%3)
        vbox.addLayout(kpi)

        vbox.addWidget(QLabel("Expenses by Category")); vbox.addWidget(self.expense_category_table,1)
        vbox.addWidget(QLabel("Purchases list")); vbox.addWidget(self.expenses_list_table,1)
        vbox.addWidget(QLabel("Material Purchases")); vbox.addWidget(self.material_purchases_table,1)
        vbox.addWidget(QLabel("Worker Wages")); vbox.addWidget(self.worker_wages_table,1)
        return tab

    def _normalize_return_reason(self, reason: str) -> str:
        normalized_tokens = ("exchange", "replacement", "استبدال", "البديل")
        if any(token in reason.lower() for token in normalized_tokens):
            return "Return | Ref: Legacy Exchange"
        return reason

    def set_cashier_name(self, name: str) -> None:
        if not self.cashier_input.text().strip():
            self.cashier_input.setText(name)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.header_label.setText(t("reports.header", language=language))
        self.date_label.setText(f"{t('common.date', language=language)}:")
        self.product_filter_label.setText(f"{t('common.product_filter', language=language)}:")
        self._reload_product_filter()
        self.product_filter_combo.setItemText(0, t("common.all_products", language=language))
        self.shift_box.setTitle(t("reports.shift_box", language=language))
        self.cashier_label.setText(t("reports.cashier", language=language))
        self.open_time_label.setText(t("reports.open_time", language=language))
        self.close_time_label.setText(t("reports.close_time", language=language))
        self.opening_cash_label.setText(t("reports.opening_cash", language=language))
        self.actual_cash_label.setText(t("reports.actual_cash", language=language))
        self.expected_label.setText(t("reports.expected_cash", language=language))
        self.over_short_label.setText(t("reports.over_short", language=language))
        self.notes_label.setText(t("reports.notes", language=language))
        self.save_shift_btn.setText(t("reports.save_shift", language=language))
        self.summary_label.setText(t("reports.summary_placeholder", language=language))
        self.expected_cash_label.setText(
            t("reports.expected_label", language=language, amount="0.00")
        )
        self.diff_label.setText(t("reports.diff_label", language=language, amount="0.00"))
        self.payment_table.setHorizontalHeaderLabels(
            [t("reports.payment_method", language=language), t("common.total", language=language)]
        )
        self.returns_table.setHorizontalHeaderLabels(
            [
                t("common.reason", language=language),
                t("reports.count", language=language),
                t("common.total", language=language),
            ]
        )
        self.top_table.setHorizontalHeaderLabels(["Product", "SKU", "Qty", "Revenue"])
        self.low_table.setHorizontalHeaderLabels(["Product", "SKU", "Qty", "Movement"])
        self.customer_table.setHorizontalHeaderLabels(["Customer", "Phone", "Spend", "Loyalty", "Invoices / Last Purchase"])
        self.stock_table.setHorizontalHeaderLabels(
            [
                t("reports.product", language=language),
                t("reports.sku", language=language),
                t("reports.qty", language=language),
                t("inventory.table_min", language=language),
                t("reports.status", language=language),
            ]
        )
        self.expense_category_table.setHorizontalHeaderLabels(["Category", "Count", "Total Amount"])
        self.expenses_list_table.setHorizontalHeaderLabels(["Date", "Category", "Vendor/Worker", "Description", "Amount", "Payment Method"])
        self.material_purchases_table.setHorizontalHeaderLabels(["Material", "Qty Purchased", "Total Cost", "Average Unit Cost"])
        self.worker_wages_table.setHorizontalHeaderLabels(["Worker", "Period", "Total Paid"])
        self.export_pdf_btn.setText(t("reports.export_pdf", language=language))
        self.export_excel_btn.setText(t("reports.export_excel", language=language))
        self.payment_breakdown_label.setText(t("reports.payment_breakdown", language=language))
        self.return_reasons_label.setText(t("reports.return_reasons", language=language))
        self.top_products_label.setText(t("reports.top_products", language=language))
        self.low_products_label.setText(t("reports.low_products", language=language))
        self.stock_alerts_label.setText(t("reports.stock_alerts", language=language))
        self.tabs.setTabText(0, t("reports.summary_tab", language=language) if t("reports.summary_tab", language=language) != "reports.summary_tab" else "Summary")
        self.tabs.setTabText(1, t("reports.returns_tab", language=language) if t("reports.returns_tab", language=language) != "reports.returns_tab" else "Returns")
        self.tabs.setTabText(2, t("reports.products_tab", language=language) if t("reports.products_tab", language=language) != "reports.products_tab" else "Products")
        self.tabs.setTabText(3, t("reports.returns_tab", language=language) if t("reports.returns_tab", language=language) != "reports.returns_tab" else "Returns")
        self.tabs.setTabText(4, t("reports.stock_tab", language=language) if t("reports.stock_tab", language=language) != "reports.stock_tab" else "Stock")
        self.tabs.setTabText(5, "Expenses / Purchases")

    def _load_shift_from_db(self) -> None:
        date_iso = self.date_filter.date().toString("yyyy-MM-dd")
        session = fetch_shift_session_for_date(date_iso)
        if not session:
            self._initialize_cashier()
            return
        cashier, open_time, close_time, opening_cash, closing_cash_actual, notes = session
        self.cashier_input.setText(cashier)
        self.open_time_input.setDateTime(datetime.fromisoformat(open_time))
        self.close_time_input.setDateTime(datetime.fromisoformat(close_time))
        self.opening_cash_input.setValue(opening_cash)
        self.closing_cash_input.setValue(closing_cash_actual)
        self.notes_input.setPlainText(notes)

    def _generate_report(self) -> None:
        date_qt = self.date_filter.date()
        date_iso = date_qt.toString("yyyy-MM-dd")
        start_dt = datetime.combine(self.date_from_filter.date().toPyDate(), time.min)
        end_dt = datetime.combine(self.date_to_filter.date().toPyDate(), time.max)
        start_iso = start_dt.isoformat(timespec="seconds")
        end_iso = end_dt.isoformat(timespec="seconds")

        product_id = self.product_filter_combo.currentData()

        sales = sales_aggregate(start_iso, end_iso, product_id=product_id)
        payments = payment_breakdown(start_iso, end_iso, product_id=product_id)
        net_payments = payment_breakdown(
            start_iso,
            end_iso,
            include_returns=True,
            product_id=product_id,
        )
        returns = returns_aggregate(start_iso, end_iso, product_id=product_id)
        low = lowest_products(start_iso, end_iso, limit=5, product_id=product_id)
        top_rev = top_products_by_revenue(start_iso, end_iso, limit=10, product_id=product_id)
        customers = customer_aggregates(start_iso, end_iso, self.customer_filter_input.text())
        out_of_stock, near_out = stock_alerts()
        inventory_value = inventory_value_estimate()

        self._populate_table(self.payment_table, [(k, f"{v:.2f}") for k, v in payments.items()])
        normalized_reasons = [
            (self._normalize_return_reason(reason), count, total) for reason, count, total in returns.reasons
        ]
        self._populate_table(
            self.returns_table,
            [(reason, str(count), f"{total:.2f}") for reason, count, total in normalized_reasons],
        )
        self._populate_table(
            self.top_table,
            [(p.name, p.code, f"{p.qty:.2f}", f"{p.revenue:.2f}") for p in top_rev],
        )
        self._populate_table(
            self.low_table,
            [(p.name, p.code, f"{p.qty:.2f}", "Slow") for p in low],
        )
        self._populate_table(
            self.customer_table,
            [(c.customer, c.phone, f"{c.spend:.2f}", f"{c.points:.2f}", f"{c.invoice_count} | {c.last_purchase[:10]}") for c in customers],
        )
        stock_rows = []
        for name_ar, name_en, sku, qty, min_qty in out_of_stock:
            stock_rows.append(
                (
                    choose_name(name_ar, name_en, language=self._language),
                    sku,
                    f"{qty:.2f}",
                    f"{min_qty:.2f}",
                    t("reports.stock_out", language=self._language),
                )
            )
        for name_ar, name_en, sku, qty, min_qty in near_out:
            stock_rows.append(
                (
                    choose_name(name_ar, name_en, language=self._language),
                    sku,
                    f"{qty:.2f}",
                    f"{min_qty:.2f}",
                    t("reports.stock_near", language=self._language),
                )
            )
        self._populate_table(self.stock_table, stock_rows)

        expected_cash = self._compute_expected_cash(net_payments)
        self.expected_cash_label.setText(
            t("reports.expected_label", language=self._language, amount=f"{expected_cash:.2f}")
        )
        diff = float(self.closing_cash_input.value()) - expected_cash
        self.diff_label.setText(
            t("reports.diff_label", language=self._language, amount=f"{diff:.2f}")
        )

        self.summary_label.setText(
            t(
                "reports.summary_label",
                language=self._language,
                count=sales.invoice_count,
                subtotal=f"{sales.subtotal:.2f}",
                discounts=f"{sales.discounts:.2f}",
                net=f"{sales.net_sales:.2f}",
            )
        )
        expense_data = expense_report_data(
            start_iso,
            end_iso,
            category=self.expense_category_filter.currentData() or None,
            vendor_worker_term=self.expense_vendor_worker_filter.text(),
            payment_method=self.expense_payment_filter.text().strip() or None,
        )
        self._populate_table(self.expense_category_table, [(r.category, str(r.count), f"{r.total_amount:.2f}") for r in expense_data["by_category"]])
        self._populate_table(self.expenses_list_table, [(r.date, r.category, r.vendor_or_worker, r.description, f"{r.amount:.2f}", r.payment_method) for r in expense_data["purchases"]])
        self._populate_table(self.material_purchases_table, [(r.material, f"{r.qty_purchased:.2f}", f"{r.total_cost:.2f}", f"{r.avg_unit_cost:.2f}") for r in expense_data["material_purchases"]])
        self._populate_table(self.worker_wages_table, [(r.worker, r.period, f"{r.total_paid:.2f}") for r in expense_data["worker_wages"]])

        revenue = sales.net_sales - returns.return_total
        expenses = expense_data["total_expenses"]
        net_profit = revenue - expenses
        product_margin = sum(row.profit for row in production_history(start_iso, end_iso, "done", product_id))
        self.total_revenue_kpi.setText(f"Net Revenue\n{revenue:.2f}")
        self.total_expenses_kpi.setText(f"Total Expenses\n{expenses:.2f}")
        self.net_profit_kpi.setText(f"Net Cash Profit\n{net_profit:.2f}")
        self.product_margin_kpi.setText(f"Product Margin\n{product_margin:.2f}")
        self.bills_kpi.setText(f"Bills\n{expense_data['bills_expenses']:.2f}")
        self.worker_wages_kpi.setText(f"Worker Wages\n{expense_data['wages_expenses']:.2f}")

        top_product = top_rev[0] if top_rev else None
        top_customer = customers[0] if customers else None
        low_stock_count = len(out_of_stock) + len(near_out)
        self._set_summary_card("total_sales", f"{sales.subtotal:.2f}", f"{sales.invoice_count} invoices")
        self._set_summary_card("net_revenue", f"{revenue:.2f}", f"after returns {returns.return_total:.2f}")
        self._set_summary_card("total_expenses", f"{expenses:.2f}", f"{len(expense_data['purchases'])} entries")
        self._set_summary_card("net_cash_profit", f"{net_profit:.2f}")
        self._set_summary_card("returns", f"{returns.return_total:.2f}", f"{returns.return_count} returns")
        self._set_summary_card("top_product", top_product.name if top_product else "—", f"Qty {top_product.qty:.2f}" if top_product else "No sales")
        self._set_summary_card("top_customer", top_customer.customer if top_customer else "—", f"Spend {top_customer.spend:.2f}" if top_customer else "No customer data")
        self._set_summary_card("low_stock_alerts", str(low_stock_count), f"Out: {len(out_of_stock)} | Near: {len(near_out)}")

        self._last_report = ReportData(
            report_date=date_iso,
            report_number=f"DR-{date_qt.toString('yyyyMMdd')}",
            cashier=self.cashier_input.text().strip() or "N/A",
            shift_open=self.open_time_input.dateTime().toString(Qt.DateFormat.ISODate),
            shift_close=self.close_time_input.dateTime().toString(Qt.DateFormat.ISODate),
            opening_cash=float(self.opening_cash_input.value()),
            closing_cash_actual=float(self.closing_cash_input.value()),
            expected_cash=expected_cash,
            notes=self.notes_input.toPlainText().strip(),
            sales_summary=(
                sales.invoice_count,
                sales.subtotal,
                sales.discounts,
                sales.net_sales,
            ),
            payment_breakdown=list(payments.items()),
            returns_summary=(returns.return_count, returns.return_total),
            return_reasons=normalized_reasons,
            top_products=[(p.name, p.code, p.qty) for p in top_rev],
            low_products=[(p.name, p.code, p.qty) for p in low],
            out_of_stock=list(out_of_stock),
            near_out=list(near_out),
        )

    def _reload_product_filter(self) -> None:
        current_product_id = self.product_filter_combo.currentData()
        self.product_filter_combo.blockSignals(True)
        self.product_filter_combo.clear()
        self.product_filter_combo.addItem("", None)
        for product in list_products():
            label = choose_name(product.name_ar, product.name_en, language=self._language)
            self.product_filter_combo.addItem(f"{label} ({product.sku})", product.id)
        if current_product_id is not None:
            index = self.product_filter_combo.findData(current_product_id)
            if index >= 0:
                self.product_filter_combo.setCurrentIndex(index)
        self.product_filter_combo.blockSignals(False)

    def _refresh_cash_diff(self) -> None:
        if not self._last_report:
            return
        diff = float(self.closing_cash_input.value()) - self._last_report.expected_cash
        self.diff_label.setText(
            t("reports.diff_label", language=self._language, amount=f"{diff:.2f}")
        )

    def _compute_expected_cash(self, payments: Dict[str, float]) -> float:
        for method, total in payments.items():
            if "cash" in method.lower() or "نقد" in method:
                return total + float(self.opening_cash_input.value())
        return float(self.opening_cash_input.value())

    def _populate_table(self, table: QTableWidget, rows: List[Tuple[str, ...]]) -> None:
        table.setRowCount(0)
        for row_data in rows:
            row = table.rowCount()
            table.insertRow(row)
            for col, value in enumerate(row_data):
                table.setItem(row, col, QTableWidgetItem(str(value)))

    def _save_shift_session(self) -> None:
        save_shift_session(
            self.cashier_input.text().strip() or "N/A",
            self.open_time_input.dateTime().toString(Qt.DateFormat.ISODate),
            self.close_time_input.dateTime().toString(Qt.DateFormat.ISODate),
            float(self.opening_cash_input.value()),
            float(self.closing_cash_input.value()),
            self.notes_input.toPlainText().strip(),
        )
        QMessageBox.information(
            self,
            t("common.saved_title", language=self._language),
            t("reports.shift_saved", language=self._language),
        )

    def refresh_data_source(self) -> None:
        self._generate_report()

    def _export_pdf(self) -> None:
        if not self._last_report:
            QMessageBox.warning(
                self,
                t("common.export", language=self._language),
                t("reports.generate_first", language=self._language),
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("reports.export_pdf", language=self._language),
            f"{self._last_report.report_number}.pdf",
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
        export_daily_report_pdf(
            path,
            gallery,
            self._last_report.report_date,
            self._last_report.report_number,
            self._last_report.cashier,
            self._last_report.shift_open,
            self._last_report.shift_close,
            self._last_report.opening_cash,
            self._last_report.closing_cash_actual,
            self._last_report.expected_cash,
            self._last_report.notes,
            self._last_report.sales_summary,
            self._last_report.payment_breakdown,
            self._last_report.returns_summary,
            self._last_report.return_reasons,
            self._last_report.top_products,
            self._last_report.low_products,
            self._last_report.out_of_stock,
            self._last_report.near_out,
        )
        QMessageBox.information(
            self,
            t("common.export", language=self._language),
            t("reports.pdf_exported", language=self._language),
        )

    def _export_excel(self) -> None:
        if not self._last_report:
            QMessageBox.warning(
                self,
                t("common.export", language=self._language),
                t("reports.generate_first", language=self._language),
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("reports.export_excel", language=self._language),
            f"{self._last_report.report_number}.xlsx",
            f"{t('common.file_filter_excel', language=self._language)} (*.xlsx)",
        )
        if not path:
            return
        rows: List[List[str]] = [
            [t("reports.excel_title", language=self._language), ""],
            [t("reports.excel_date", language=self._language), self._last_report.report_date],
            [t("reports.excel_report_no", language=self._language), self._last_report.report_number],
            [t("reports.excel_cashier", language=self._language), self._last_report.cashier],
            [t("reports.excel_shift_open", language=self._language), self._last_report.shift_open],
            [t("reports.excel_shift_close", language=self._language), self._last_report.shift_close],
            [t("reports.excel_opening_cash", language=self._language), f"{self._last_report.opening_cash:.2f}"],
            [t("reports.excel_expected_cash", language=self._language), f"{self._last_report.expected_cash:.2f}"],
            [t("reports.excel_actual_cash", language=self._language), f"{self._last_report.closing_cash_actual:.2f}"],
            [
                t("reports.excel_over_short", language=self._language),
                f"{self._last_report.closing_cash_actual - self._last_report.expected_cash:.2f}",
            ],
            [t("reports.excel_notes", language=self._language), self._last_report.notes],
            ["", ""],
            [t("reports.excel_sales_movement", language=self._language), ""],
            [t("reports.excel_invoices", language=self._language), str(self._last_report.sales_summary[0])],
            [t("reports.excel_subtotal", language=self._language), f"{self._last_report.sales_summary[1]:.2f}"],
            [t("reports.excel_discounts", language=self._language), f"{self._last_report.sales_summary[2]:.2f}"],
            [t("reports.excel_net_sales", language=self._language), f"{self._last_report.sales_summary[3]:.2f}"],
            ["", ""],
            [t("reports.excel_payment_breakdown", language=self._language), ""],
        ]
        for method, total in self._last_report.payment_breakdown:
            rows.append([method, f"{total:.2f}"])
        rows.append(["", ""])
        rows.append([t("reports.excel_returns", language=self._language), ""])
        rows.append([t("reports.excel_return_count", language=self._language), str(self._last_report.returns_summary[0])])
        rows.append([t("reports.excel_return_value", language=self._language), f"{self._last_report.returns_summary[1]:.2f}"])
        for reason, count, total in self._last_report.return_reasons:
            rows.append([reason, f"{count} ({total:.2f})"])
        rows.append(["", ""])
        rows.append([t("reports.excel_top_products", language=self._language), ""])
        for name, code, qty in self._last_report.top_products:
            rows.append([f"{name} ({code})", f"{qty:.2f}"])
        rows.append([t("reports.excel_low_products", language=self._language), ""])
        for name, code, qty in self._last_report.low_products:
            rows.append([f"{name} ({code})", f"{qty:.2f}"])
        rows.append(["", ""])
        rows.append([t("reports.excel_stock_alerts", language=self._language), ""])
        for name_ar, name_en, sku, qty, min_qty in self._last_report.out_of_stock:
            rows.append(
                [
                    choose_name(name_ar, name_en, language=self._language),
                    f"{qty:.2f} - {t('reports.stock_out', language=self._language)}",
                ]
            )
        for name_ar, name_en, sku, qty, min_qty in self._last_report.near_out:
            rows.append(
                [
                    choose_name(name_ar, name_en, language=self._language),
                    f"{qty:.2f} - {t('reports.stock_near', language=self._language)}",
                ]
            )

        write_protected_workbook(
            path,
            [t("reports.excel_field", language=self._language), t("reports.excel_value", language=self._language)],
            rows,
            title=t("reports.excel_title", language=self._language),
        )
        QMessageBox.information(
            self,
            t("common.export", language=self._language),
            t("reports.excel_exported", language=self._language),
        )
