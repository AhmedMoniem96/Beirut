import json
import calendar
from datetime import datetime, timezone

from collections import Counter
from dataclasses import dataclass

from PyQt6.QtCore import Qt, QDate, QDateTime, QTime, QSize, QLocale
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDateTimeEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QFileDialog,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QComboBox,
    QSizePolicy,
    QTimeEdit,
)
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap

from beirut_pos.core.db import get_conn, setting_get
from .common.big_dialog import BigDialog
from ..services.orders import order_manager
from ..services import staff as staff_service
from ..services import maintenance as maintenance_service
from beirut_pos.utils.currency import format_pounds
from .theme.components import DSTable, KpiCard


CLEANUP_STATIC_PASSWORD = "mn3mbasha"


@dataclass
class ReportCell:
    text: str
    thumbnail: QPixmap | bytes | str | None = None
    badge: str | None = None


class AdminReportsDialog(BigDialog):
    """Dashboard of operational reports for managers."""

    def __init__(self, actor_username: str | None = None):
        super().__init__("التقارير الإدارية", remember_key="reports", parent=None)
        self.currency = setting_get("currency", "EGP") or "EGP"
        self.actor_username = (actor_username or "").strip()

        # Start the reports window larger by default to give the winnings/profit
        # visuals room to breathe. If the user has a saved geometry it will
        # override the resize below.
        self.setMinimumSize(1100, 750)
        if not setting_get("geom_reports", ""):
            self.resize(1220, 840)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_daily_tab(), "ملخص يومي")
        self.tabs.addTab(self._build_order_items_tab(), "تفاصيل الطلبات")
        self.tabs.addTab(self._build_cashier_tab(), "حسب الكاشير")
        self.tabs.addTab(self._build_products_tab(), "الأصناف")
        self.tabs.addTab(self._build_discounts_tab(), "الخصومات")  # NEW!
        self.tabs.addTab(self._build_purchases_tab(), "المشتريات")  # NEW!
        self.tabs.addTab(self._build_profit_tab(), "الأرباح")
        self.tabs.addTab(self._build_price_log_tab(), "سجل الأسعار")
        self.tabs.addTab(self._build_deleted_items_tab(), "حذف العناصر")
        self.tabs.addTab(self._build_inventory_tab(), "المخزون")
        self.tabs.addTab(self._build_attendance_tab(), "ساعات العمل")
        self.tabs.addTab(self._build_shift_summary_tab(), "ملخص الورديات")
        self.tabs.addTab(self._build_deductions_tab(), "خصومات الموظفين")
        self.tabs.addTab(self._build_payroll_history_tab(), "سجل الرواتب")
        self.tabs.addTab(self._build_stakeholder_tab(), "تقرير المساهمين")
        self.tabs.currentChanged.connect(self._reload_current_tab)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self.tabs)

        self.cleanup_panel = self._build_cleanup_panel()
        layout.addWidget(self.cleanup_panel)

        self._load_daily_report()
        self._load_order_items_report()
        self._load_cashier_report()
        self._load_product_report()
        self._load_discounts_report()  # NEW!
        self._load_purchases_report()  # NEW!
        self._load_profit_report()
        self._load_price_log()
        self._load_deleted_items_report()
        self._load_inventory_report()
        self._load_attendance_report()
        self._load_shift_report()
        self._load_deductions_report()
        self._load_payroll_history()
        self._load_stakeholder_report()

    # ------------------------------------------------------------------ daily
    def _build_daily_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.daily_table = self._make_table(
            [
                "التاريخ",
                "عدد الطلبات",
                "عدد العناصر",
                "الإجمالي قبل الخصم",
                "الخصم",
                "الإجمالي النهائي",
                "نقدي",
                "بطاقات",
            ]
        )
        layout.addWidget(self.daily_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        controls.addWidget(QLabel("من:"))
        self.daily_from_date = QDateEdit(QDate.currentDate().addDays(-6))
        self.daily_from_date.setCalendarPopup(True)
        self.daily_from_date.setDisplayFormat("yyyy-MM-dd")
        self.daily_from_date.setMinimumWidth(140)
        self.daily_from_date.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.daily_from_date)

        controls.addWidget(QLabel("الساعة:"))

        self.daily_from_time = QTimeEdit(QTime(0, 0))
        self._configure_time_edit(self.daily_from_time)
        self.daily_from_time.setMinimumWidth(90)
        self.daily_from_time.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        controls.addWidget(self._wrap_ltr(self.daily_from_time))

        controls.addWidget(QLabel("إلى:"))
        self.daily_to_date = QDateEdit(QDate.currentDate())
        self.daily_to_date.setCalendarPopup(True)
        self.daily_to_date.setDisplayFormat("yyyy-MM-dd")
        self.daily_to_date.setMinimumWidth(140)
        self.daily_to_date.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.daily_to_date)

        controls.addWidget(QLabel("الساعة:"))

        self.daily_to_time = QTimeEdit(QTime(23, 59))
        self._configure_time_edit(self.daily_to_time)
        self.daily_to_time.setMinimumWidth(90)
        self.daily_to_time.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        controls.addWidget(self._wrap_ltr(self.daily_to_time))

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_daily_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.daily_table, "daily_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.daily_summary = QLabel("")
        self.daily_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.daily_summary)

        return widget

    def _load_daily_report(self):
        start, end = self._datetime_bounds_from_date_time(
            self.daily_from_date,
            self.daily_from_time,
            self.daily_to_date,
            self.daily_to_time,
        )
        query = """
            WITH paid AS (
                SELECT
                    p.order_id,
                    DATE(p.paid_at) AS day,
                    SUM(p.amount_cents) AS net_total,
                    SUM(CASE WHEN p.method='cash' THEN p.amount_cents ELSE 0 END) AS cash_total,
                    SUM(CASE WHEN p.method='cash' THEN 0 ELSE p.amount_cents END) AS card_total
                FROM payments p
                WHERE p.paid_at BETWEEN ? AND ?
                GROUP BY p.order_id, day
            ),
            items AS (
                SELECT order_id, SUM(price_cents * qty) AS gross_total, SUM(qty) AS items_qty
                FROM order_items
                GROUP BY order_id
            )
            SELECT
                paid.day AS day,
                COUNT(paid.order_id) AS orders_count,
                COALESCE(SUM(items.items_qty),0) AS items_count,
                COALESCE(SUM(items.gross_total),0) AS gross_total,
                COALESCE(SUM(paid.net_total),0) AS net_total,
                COALESCE(SUM(paid.cash_total),0) AS cash_total,
                COALESCE(SUM(paid.card_total),0) AS card_total
            FROM paid
            LEFT JOIN items ON items.order_id = paid.order_id
            GROUP BY paid.day
            ORDER BY paid.day DESC
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (start, end))
        rows = cur.fetchall()
        conn.close()

        table_rows = []
        totals = {"orders": 0, "items": 0.0, "gross": 0, "net": 0, "cash": 0, "card": 0}
        for row in rows:
            gross = int(row["gross_total"] or 0)
            net = int(row["net_total"] or 0)
            discount = gross - net
            cash = int(row["cash_total"] or 0)
            card = int(row["card_total"] or 0)
            items_count = float(row["items_count"] or 0)
            orders_count = int(row["orders_count"] or 0)
            table_rows.append(
                [
                    row["day"],
                    str(orders_count),
                    self._format_qty(items_count),
                    self._money(gross),
                    self._money(discount),
                    self._money(net),
                    self._money(cash),
                    self._money(card),
                ]
            )
            totals["orders"] += orders_count
            totals["items"] += items_count
            totals["gross"] += gross
            totals["net"] += net
            totals["cash"] += cash
            totals["card"] += card

        self._populate_table(self.daily_table, table_rows)
        summary = (
            f"إجمالي الطلبات: {totals['orders']} | "
            f"عدد العناصر: {self._format_qty(totals['items'])} | "
            f"صافي المبيعات: {self._money(totals['net'])}"
        )
        self.daily_summary.setText(summary)

    # ---------------------------------------------------------- order items
    def _build_order_items_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.order_items_table = self._make_table(
            [
                "اليوم",
                "التاريخ",
                "التصنيف",
                "رقم الطلب",
                "رقم الطاولة",
                "توقيت الفتح",
                "وقت الدفع",
                "العدد",
                "السعر",
                "القيمة",
            ]
        )
        layout.addWidget(self.order_items_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        controls.addWidget(QLabel("من:"))

        self.order_items_from = QDateEdit(QDate.currentDate().addDays(-6))
        self.order_items_from.setCalendarPopup(True)
        self.order_items_from.setMinimumWidth(150)
        controls.addWidget(self.order_items_from)

        controls.addWidget(QLabel("الساعة:"))
        self.order_items_from_time = QTimeEdit(QTime(0, 0))
        self._configure_time_edit(self.order_items_from_time)
        self.order_items_from_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.order_items_from_time))

        controls.addWidget(QLabel("إلى:"))
        self.order_items_to = QDateEdit(QDate.currentDate())
        self.order_items_to.setCalendarPopup(True)
        self.order_items_to.setMinimumWidth(150)
        controls.addWidget(self.order_items_to)

        controls.addWidget(QLabel("الساعة:"))
        self.order_items_to_time = QTimeEdit(QTime(23, 59))
        self._configure_time_edit(self.order_items_to_time)
        self.order_items_to_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.order_items_to_time))

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_order_items_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.order_items_table, "order_items_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.order_items_summary = QLabel("")
        self.order_items_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.order_items_summary)

        return widget

    def _load_order_items_report(self):
        start, end = self._datetime_bounds_from_date_time(
            self.order_items_from,
            self.order_items_from_time,
            self.order_items_to,
            self.order_items_to_time,
        )

        query = """
            WITH paid_orders AS (
                SELECT
                    o.id,
                    o.opened_at,
                    o.table_code,
                    MIN(p.paid_at) AS paid_at
                FROM orders o
                JOIN payments p ON p.order_id = o.id
                WHERE o.status = 'paid' AND p.paid_at BETWEEN ? AND ?
                GROUP BY o.id, o.opened_at, o.table_code
            )
            SELECT
                paid_orders.id AS order_id,
                paid_orders.opened_at,
                paid_orders.table_code,
                paid_orders.paid_at,
                oi.product_name,
                oi.price_cents,
                oi.qty
            FROM paid_orders
            JOIN order_items oi ON oi.order_id = paid_orders.id
            ORDER BY paid_orders.opened_at DESC, paid_orders.id DESC, oi.id ASC
        """

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (start, end))
        rows = cur.fetchall()
        conn.close()

        table_rows: list[list[str]] = []
        totals = {"qty": 0.0, "value": 0}

        for row in rows:
            opened_at = row["opened_at"] or ""
            paid_at = row["paid_at"] or ""
            opened_dt = self._parse_iso_datetime(opened_at)
            paid_dt = self._parse_iso_datetime(paid_at)
            qty = float(row["qty"] or 0)
            price = int(row["price_cents"] or 0)
            value = int(round(price * qty))

            date_value = opened_dt.date() if opened_dt else None
            table_rows.append(
                [
                    self._weekday_name(date_value),
                    date_value.isoformat() if date_value else "",
                    row["product_name"] or "—",
                    str(row["order_id"] or ""),
                    (row["table_code"] or "").strip(),
                    opened_dt.strftime("%I:%M %p") if opened_dt else "",
                    paid_dt.strftime("%I:%M %p") if paid_dt else "",
                    self._format_qty(qty),
                    self._money(price),
                    self._money(value),
                ]
            )

            totals["qty"] += qty
            totals["value"] += value

        self._populate_table(self.order_items_table, table_rows)
        self.order_items_summary.setText(
            f"عدد الصفوف: {len(table_rows)} | إجمالي الكمية: {self._format_qty(totals['qty'])} | إجمالي القيمة: {self._money(totals['value'])}"
        )

    # --------------------------------------------------------------- cashier
    def _build_cashier_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.cashier_table = self._make_table(
            [
                "الكاشير",
                "عدد الطلبات",
                "الإجمالي قبل الخصم",
                "الإجمالي النهائي",
                "نقدي",
                "بطاقات",
                "متوسط الطلب",
            ]
        )
        layout.addWidget(self.cashier_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        controls.addWidget(QLabel("من:"))
        self.cashier_from = QDateEdit(QDate.currentDate().addDays(-6))
        self.cashier_from.setCalendarPopup(True)
        self.cashier_from.setMinimumWidth(150)
        self.cashier_from.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.cashier_from)

        controls.addWidget(QLabel("الساعة:"))
        self.cashier_from_time = QTimeEdit(QTime(0, 0))
        self._configure_time_edit(self.cashier_from_time)
        self.cashier_from_time.setMinimumWidth(90)
        self.cashier_from_time.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        controls.addWidget(self._wrap_ltr(self.cashier_from_time))

        controls.addWidget(QLabel("إلى:"))
        self.cashier_to = QDateEdit(QDate.currentDate())
        self.cashier_to.setCalendarPopup(True)
        self.cashier_to.setMinimumWidth(150)
        self.cashier_to.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.cashier_to)

        controls.addWidget(QLabel("الساعة:"))
        self.cashier_to_time = QTimeEdit(QTime(23, 59))
        self._configure_time_edit(self.cashier_to_time)
        self.cashier_to_time.setMinimumWidth(90)
        self.cashier_to_time.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        controls.addWidget(self._wrap_ltr(self.cashier_to_time))

        controls.addWidget(QLabel("الكاشير:"))
        self.cashier_filter = QComboBox()
        self.cashier_filter.addItem("الكل", "")
        self._populate_cashier_filter()
        self.cashier_filter.setMinimumWidth(180)
        self.cashier_filter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.cashier_filter)

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_cashier_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.cashier_table, "cashier_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.cashier_summary = QLabel("")
        self.cashier_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.cashier_summary)

        return widget

    def _populate_cashier_filter(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT cashier FROM payments WHERE cashier IS NOT NULL ORDER BY cashier")
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            cashier = (row["cashier"] or "").strip()
            if cashier:
                self.cashier_filter.addItem(cashier, cashier)

    def _load_cashier_report(self):
        start, end = self._datetime_bounds_from_date_time(
            self.cashier_from,
            self.cashier_from_time,
            self.cashier_to,
            self.cashier_to_time,
        )
        cashier = self.cashier_filter.currentData()
        query = """
            WITH pay AS (
                SELECT
                    p.order_id,
                    p.cashier,
                    SUM(p.amount_cents) AS net_total,
                    SUM(CASE WHEN p.method='cash' THEN p.amount_cents ELSE 0 END) AS cash_total,
                    SUM(CASE WHEN p.method='cash' THEN 0 ELSE p.amount_cents END) AS card_total
                FROM payments p
                WHERE p.paid_at BETWEEN ? AND ?
                GROUP BY p.order_id, p.cashier
            ),
            items AS (
                SELECT order_id, SUM(price_cents * qty) AS gross_total
                FROM order_items
                GROUP BY order_id
            )
            SELECT
                pay.cashier AS cashier,
                COUNT(pay.order_id) AS orders_count,
                COALESCE(SUM(items.gross_total),0) AS gross_total,
                COALESCE(SUM(pay.net_total),0) AS net_total,
                COALESCE(SUM(pay.cash_total),0) AS cash_total,
                COALESCE(SUM(pay.card_total),0) AS card_total
            FROM pay
            LEFT JOIN items ON items.order_id = pay.order_id
            WHERE (? = '' OR pay.cashier = ?)
            GROUP BY pay.cashier
            ORDER BY net_total DESC
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (start, end, cashier, cashier))
        rows = cur.fetchall()
        conn.close()

        table_rows = []
        totals = {"orders": 0, "gross": 0, "net": 0, "cash": 0, "card": 0}
        for row in rows:
            gross = int(row["gross_total"] or 0)
            net = int(row["net_total"] or 0)
            cash_total = int(row["cash_total"] or 0)
            card_total = int(row["card_total"] or 0)
            orders_count = int(row["orders_count"] or 0)
            avg_order = net / orders_count if orders_count else 0
            cashier_name = row["cashier"] or "غير محدد"
            table_rows.append([
                cashier_name,
                str(orders_count),
                self._money(gross),
                self._money(net),
                self._money(cash_total),
                self._money(card_total),
                self._money(int(avg_order)),
            ])
            totals["orders"] += orders_count
            totals["gross"] += gross
            totals["net"] += net
            totals["cash"] += cash_total
            totals["card"] += card_total

        self._populate_table(self.cashier_table, table_rows)
        summary = (
            f"عدد الطلبات: {totals['orders']} | "
            f"صافي المبيعات: {self._money(totals['net'])} | "
            f"نقدي: {self._money(totals['cash'])} · بطاقات: {self._money(totals['card'])}"
        )
        self.cashier_summary.setText(summary)

    # ------------------------------------------------------------- products
    def _build_products_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        cards_row = QHBoxLayout()
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(12)
        self.products_card_total = KpiCard("🛍️", "عدد الأصناف", "—")
        self.products_card_qty = KpiCard("📦", "إجمالي الكمية", "—")
        self.products_card_sales = KpiCard("💰", "إجمالي المبيعات", "—")
        for card in (
            self.products_card_total,
            self.products_card_qty,
            self.products_card_sales,
        ):
            cards_row.addWidget(card)
        cards_row.addStretch(1)
        layout.addLayout(cards_row)

        self.products_table = DSTable(0, 3)
        self.products_table.set_headers([
            "المنتج", "الكمية", "إجمالي المبيعات"
        ])
        self.products_table.set_column_alignments(
            [
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                Qt.AlignmentFlag.AlignCenter,
                Qt.AlignmentFlag.AlignCenter,
            ]
        )
        layout.addWidget(self.products_table, 1)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("من:"))
        self.products_from = QDateEdit(QDate.currentDate().addDays(-14))
        self.products_from.setCalendarPopup(True)
        controls.addWidget(self.products_from)

        controls.addWidget(QLabel("الساعة:"))
        self.products_from_time = QTimeEdit(QTime(0, 0))
        self._configure_time_edit(self.products_from_time)
        self.products_from_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.products_from_time))

        controls.addWidget(QLabel("إلى:"))
        self.products_to = QDateEdit(QDate.currentDate())
        self.products_to.setCalendarPopup(True)
        controls.addWidget(self.products_to)

        controls.addWidget(QLabel("الساعة:"))
        self.products_to_time = QTimeEdit(QTime(23, 59))
        self._configure_time_edit(self.products_to_time)
        self.products_to_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.products_to_time))

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_product_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.products_table, "products_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.products_summary = QLabel("")
        self.products_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.products_summary)

        return widget

    def _load_product_report(self):
        start, end = self._datetime_bounds_from_date_time(
            self.products_from,
            self.products_from_time,
            self.products_to,
            self.products_to_time,
        )
        query = """
            WITH paid_orders AS (
                SELECT DISTINCT order_id FROM payments WHERE paid_at BETWEEN ? AND ?
            )
            SELECT oi.product_name AS product, SUM(oi.qty) AS qty,
                   SUM(oi.price_cents * oi.qty) AS total
            FROM order_items oi
            JOIN paid_orders po ON po.order_id = oi.order_id
            GROUP BY oi.product_name
            ORDER BY total DESC
            LIMIT 50
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (start, end))
        rows = cur.fetchall()
        conn.close()

        rows_list = []
        total_qty = 0.0
        total_sales = 0
        for row in rows:
            qty = float(row["qty"] or 0)
            total = int(row["total"] or 0)
            rows_list.append([
                row["product"],
                self._format_qty(qty),
                self._money(total),
            ])
            total_qty += qty
            total_sales += total

        self._populate_table(self.products_table, rows_list)
        self.products_summary.setText(
            f"عدد الأصناف: {len(rows_list)} | إجمالي الكمية: {self._format_qty(total_qty)} | إجمالي المبيعات: {self._money(total_sales)}"
        )
        self.products_card_total.value_label.setText(str(len(rows_list)))
        self.products_card_qty.value_label.setText(self._format_qty(total_qty))
        self.products_card_sales.value_label.setText(self._money(total_sales))

    # ------------------------------------------------------------ discounts (NEW!)
    def _build_discounts_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.discounts_table = self._make_table([
            "التاريخ", "الطاولة", "اسم العميل", "المبلغ", "السبب", "الكاشير"
        ])
        layout.addWidget(self.discounts_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        controls.addWidget(QLabel("من:"))
        self.discounts_from = QDateEdit(QDate.currentDate().addDays(-14))
        self.discounts_from.setCalendarPopup(True)
        self.discounts_from.setMinimumWidth(150)
        controls.addWidget(self.discounts_from)

        controls.addWidget(QLabel("الساعة:"))
        self.discounts_from_time = QTimeEdit(QTime(0, 0))
        self._configure_time_edit(self.discounts_from_time)
        self.discounts_from_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.discounts_from_time))

        controls.addWidget(QLabel("إلى:"))
        self.discounts_to = QDateEdit(QDate.currentDate())
        self.discounts_to.setCalendarPopup(True)
        self.discounts_to.setMinimumWidth(150)
        controls.addWidget(self.discounts_to)

        controls.addWidget(QLabel("الساعة:"))
        self.discounts_to_time = QTimeEdit(QTime(23, 59))
        self._configure_time_edit(self.discounts_to_time)
        self.discounts_to_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.discounts_to_time))

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_discounts_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.discounts_table, "discounts_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.discounts_summary = QLabel("")
        self.discounts_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.discounts_summary)

        return widget

    def _load_discounts_report(self):
        start, end = self._datetime_bounds_from_date_time(
            self.discounts_from,
            self.discounts_from_time,
            self.discounts_to,
            self.discounts_to_time,
        )
        query = """
            SELECT
                o.closed_at,
                o.table_code,
                COALESCE(NULLIF(o.client_name, ''), tc.client_name, '') AS client_name,
                o.discount_cents,
                o.discount_reason,
                p.cashier
            FROM orders o
            LEFT JOIN payments p ON p.order_id = o.id
            LEFT JOIN table_clients tc ON tc.table_code = UPPER(o.table_code)
            WHERE o.discount_cents > 0
                AND o.closed_at BETWEEN ? AND ?
            ORDER BY o.closed_at DESC
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (start, end))
        rows = cur.fetchall()
        conn.close()

        rows_list = []
        total_discount = 0
        for row in rows:
            discount_amount = int(row["discount_cents"] or 0)
            reason = (row["discount_reason"] or "").strip() or "غير محدد"
            cashier = (row["cashier"] or "").strip() or "غير محدد"
            closed_at = (row["closed_at"] or "").strip()

            rows_list.append([
                closed_at,
                row["table_code"] or "",
                (row["client_name"] or "").strip(),
                self._money(discount_amount),
                reason,
                cashier,
            ])
            total_discount += discount_amount

        self._populate_table(self.discounts_table, rows_list)
        self.discounts_summary.setText(
            f"عدد الخصومات: {len(rows_list)} | إجمالي الخصومات: {self._money(total_discount)}"
        )

    # ----------------------------------------------------------- purchases (NEW!)
    def _build_purchases_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.purchases_table = self._make_table([
            "التاريخ", "المورد", "رقم الفاتورة", "المبلغ", "ملاحظات", "المسجل"
        ])
        layout.addWidget(self.purchases_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        controls.addWidget(QLabel("من:"))
        self.purchases_from = QDateEdit(QDate.currentDate().addDays(-30))
        self.purchases_from.setCalendarPopup(True)
        self.purchases_from.setMinimumWidth(150)
        controls.addWidget(self.purchases_from)

        controls.addWidget(QLabel("الساعة:"))
        self.purchases_from_time = QTimeEdit(QTime(0, 0))
        self._configure_time_edit(self.purchases_from_time)
        self.purchases_from_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.purchases_from_time))

        controls.addWidget(QLabel("إلى:"))
        self.purchases_to = QDateEdit(QDate.currentDate())
        self.purchases_to.setCalendarPopup(True)
        self.purchases_to.setMinimumWidth(150)
        controls.addWidget(self.purchases_to)

        controls.addWidget(QLabel("الساعة:"))
        self.purchases_to_time = QTimeEdit(QTime(23, 59))
        self._configure_time_edit(self.purchases_to_time)
        self.purchases_to_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.purchases_to_time))

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_purchases_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.purchases_table, "purchases_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.purchases_summary = QLabel("")
        self.purchases_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.purchases_summary)

        return widget

    def _load_purchases_report(self):
        start, end = self._datetime_bounds_from_date_time(
            self.purchases_from,
            self.purchases_from_time,
            self.purchases_to,
            self.purchases_to_time,
        )
        query = """
            SELECT
                purchased_at,
                supplier,
                invoice_no,
                amount_cents,
                notes,
                recorded_by
            FROM purchases
            WHERE purchased_at BETWEEN ? AND ?
            ORDER BY purchased_at DESC
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, (start, end))
        rows = cur.fetchall()
        conn.close()

        rows_list = []
        total_amount = 0
        for row in rows:
            amount = int(row["amount_cents"] or 0)
            purchased_at = (row["purchased_at"] or "").strip()
            rows_list.append([
                purchased_at,
                row["supplier"] or "—",
                row["invoice_no"] or "—",
                self._money(amount),
                (row["notes"] or "").strip() or "—",
                row["recorded_by"] or "—",
            ])
            total_amount += amount

        self._populate_table(self.purchases_table, rows_list)
        self.purchases_summary.setText(
            f"عدد المشتريات: {len(rows_list)} | إجمالي المشتريات: {self._money(total_amount)}"
        )

    # --------------------------------------------------------------- profits
    def _build_profit_tab(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)

        daily_title = QLabel("الربح اليومي")
        daily_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        daily_title.setStyleSheet("font-weight:600;")
        layout.addWidget(daily_title)

        self.profit_daily_strip = self._build_range_strip(kind="detail")
        layout.addWidget(self.profit_daily_strip)

        self.profit_daily_table = self._make_table([
            "التاريخ",
            "صافي المبيعات",
            "المشتريات",
            "صافي الربح",
        ], include_thumbnail=True)
        layout.addWidget(self.profit_daily_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        controls.addWidget(QLabel("من:"))
        self.profit_from = QDateEdit(QDate.currentDate().addDays(-6))
        self.profit_from.setCalendarPopup(True)
        self.profit_from.setMinimumWidth(150)
        self.profit_from.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.profit_from)

        controls.addWidget(QLabel("الساعة:"))
        self.profit_from_time = QTimeEdit(QTime(0, 0))
        self._configure_time_edit(self.profit_from_time)
        self.profit_from_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.profit_from_time))

        controls.addWidget(QLabel("إلى:"))
        self.profit_to = QDateEdit(QDate.currentDate())
        self.profit_to.setCalendarPopup(True)
        self.profit_to.setMinimumWidth(150)
        self.profit_to.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.profit_to)

        controls.addWidget(QLabel("الساعة:"))
        self.profit_to_time = QTimeEdit(QTime(23, 59))
        self._configure_time_edit(self.profit_to_time)
        self.profit_to_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.profit_to_time))

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_profit_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.profit_daily_table, "profit_daily_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.profit_daily_summary = QLabel("")
        self.profit_daily_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.profit_daily_summary)

        monthly_title = QLabel("الربح الشهري")
        monthly_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        monthly_title.setStyleSheet("font-weight:600; margin-top:16px;")
        layout.addWidget(monthly_title)

        self.profit_monthly_strip = self._build_range_strip(kind="month")
        layout.addWidget(self.profit_monthly_strip)

        self.profit_monthly_table = self._make_table([
            "الشهر",
            "صافي المبيعات",
            "المشتريات",
            "صافي الربح",
        ], include_thumbnail=True)
        layout.addWidget(self.profit_monthly_table, 1)

        monthly_controls = QHBoxLayout()
        monthly_controls.setSpacing(12)
        monthly_controls.setContentsMargins(8, 0, 8, 0)
        monthly_controls.addWidget(self._make_export_button(self.profit_monthly_table, "profit_monthly_report"))
        monthly_controls.addStretch(1)
        layout.addLayout(monthly_controls)

        self.profit_monthly_summary = QLabel("")
        self.profit_monthly_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.profit_monthly_summary)

        detail_title = QLabel("التقرير الشهري التفصيلي")
        detail_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        detail_title.setStyleSheet("font-weight:600; margin-top:16px;")
        layout.addWidget(detail_title)

        self.monthly_detail_strip = self._build_range_strip(kind="day")
        layout.addWidget(self.monthly_detail_strip)

        picker_layout = QHBoxLayout()
        picker_layout.setSpacing(12)
        picker_layout.setContentsMargins(8, 0, 8, 0)
        picker_layout.addWidget(QLabel("الشهر:"))
        self.month_picker = QComboBox()
        self.month_picker.setMinimumWidth(140)
        picker_layout.addWidget(self.month_picker)
        picker_layout.addWidget(QLabel("السنة:"))
        self.year_picker = QComboBox()
        self.year_picker.setMinimumWidth(120)
        picker_layout.addWidget(self.year_picker)

        month_refresh = QPushButton("عرض التقرير")
        month_refresh.clicked.connect(self._load_monthly_detail)
        picker_layout.addWidget(month_refresh)
        picker_layout.addStretch(1)
        layout.addLayout(picker_layout)

        self.monthly_detail_table = self._make_table([
            "اليوم",
            "صافي المبيعات",
            "المشتريات",
            "صافي الربح",
        ], include_thumbnail=True)
        layout.addWidget(self.monthly_detail_table, 1)

        self.monthly_detail_summary = QLabel("")
        self.monthly_detail_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.monthly_detail_summary)

        self._refresh_month_picker_defaults()
        self.month_picker.currentIndexChanged.connect(self._load_monthly_detail)
        self.year_picker.currentIndexChanged.connect(self._load_monthly_detail)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        return scroll

    def _load_profit_report(self):
        conn = None
        try:
            start, end = self._datetime_bounds_from_date_time(
                self.profit_from,
                self.profit_from_time,
                self.profit_to,
                self.profit_to_time,
            )
            conn = get_conn()
            cur = conn.cursor()

            daily_query = (
                "WITH sales AS ("
                "SELECT DATE(p.paid_at) AS day, SUM(p.amount_cents) AS net_total FROM payments p "
                "WHERE p.paid_at BETWEEN ? AND ? GROUP BY day"  # noqa: E501
                "), purchase_totals AS ("
                "SELECT DATE(pr.purchased_at) AS day, SUM(pr.amount_cents) AS purchase_total FROM purchases pr "
                "WHERE pr.purchased_at BETWEEN ? AND ? GROUP BY day"  # noqa: E501
                "), days AS (SELECT day FROM sales UNION SELECT day FROM purchase_totals) "
                "SELECT d.day AS day, COALESCE(sales.net_total, 0) AS net_sales, "
                "COALESCE(purchase_totals.purchase_total, 0) AS purchases_total FROM days d "
                "LEFT JOIN sales ON sales.day = d.day LEFT JOIN purchase_totals ON purchase_totals.day = d.day "
                "ORDER BY d.day DESC"
            )

            monthly_query = (
                "WITH sales AS ("
                "SELECT strftime('%Y-%m', paid_at) AS month, SUM(amount_cents) AS net_total FROM payments "
                "WHERE paid_at BETWEEN ? AND ? GROUP BY month"  # noqa: E501
                "), purchase_totals AS ("
                "SELECT strftime('%Y-%m', purchased_at) AS month, SUM(amount_cents) AS purchase_total FROM purchases "
                "WHERE purchased_at BETWEEN ? AND ? GROUP BY month"  # noqa: E501
                "), months AS (SELECT month FROM sales UNION SELECT month FROM purchase_totals) "
                "SELECT m.month AS month, COALESCE(sales.net_total, 0) AS net_sales, "
                "COALESCE(purchase_totals.purchase_total, 0) AS purchases_total FROM months m "
                "LEFT JOIN sales ON sales.month = m.month LEFT JOIN purchase_totals ON purchase_totals.month = m.month "
                "WHERE m.month IS NOT NULL ORDER BY m.month DESC"
            )

            cur.execute(daily_query, (start, end, start, end))
            daily_rows = cur.fetchall()
            daily_payroll_net = staff_service.daily_payroll_expense()
            start_label = (start or "").split("T")[0]
            end_label = (end or "").split("T")[0]
            self._update_range_strip(self.profit_daily_strip, start_label, end_label, kind="detail")
            month_day_counts: Counter[str] = Counter()
            for row in daily_rows:
                day_value = row["day"] or ""
                if day_value:
                    month_day_counts[day_value[:7]] += 1

            cur.execute(monthly_query, (start, end, start, end))
            monthly_rows = cur.fetchall()

            daily_display = []
            daily_totals = {"sales": 0, "purchases": 0, "profit": 0, "payroll": 0}
            for row in daily_rows:
                day = row["day"] or ""
                sales_total = int(row["net_sales"] or 0)
                purchase_total = int(row["purchases_total"] or 0)
                payroll_deduction = daily_payroll_net if day else 0
                profit = sales_total - purchase_total - payroll_deduction
                day_thumb = self._make_date_thumbnail(day, kind="detail")
                daily_display.append([
                    self._thumbnail_cell(day, day_thumb),
                    day,
                    self._money(sales_total),
                    self._money(purchase_total),
                    self._money(profit),
                ])
                daily_totals["sales"] += sales_total
                daily_totals["purchases"] += purchase_total
                daily_totals["profit"] += profit
                daily_totals["payroll"] += payroll_deduction

            self._populate_table(self.profit_daily_table, daily_display)
            self.profit_daily_summary.setText(
                f"صافي المبيعات: {self._money(daily_totals['sales'])} | "
                f"إجمالي المشتريات: {self._money(daily_totals['purchases'])} | "
                f"الرواتب اليومية المحتسبة: {self._money(daily_totals['payroll'])} | "
                f"صافي الربح بعد الرواتب: {self._money(daily_totals['profit'])}"
            )

            monthly_display = []
            monthly_totals = {"sales": 0, "purchases": 0, "profit": 0, "payroll": 0}
            range_months = [row["month"] for row in monthly_rows if row["month"]]
            if range_months:
                self._update_range_strip(
                    self.profit_monthly_strip,
                    range_months[-1],
                    range_months[0],
                    kind="month",
                )
            else:
                self._update_range_strip(self.profit_monthly_strip, start_label[:7], end_label[:7], kind="month")
            for row in monthly_rows:
                month = row["month"] or ""
                sales_total = int(row["net_sales"] or 0)
                purchase_total = int(row["purchases_total"] or 0)
                payroll_days = month_day_counts.get(month, 0)
                payroll_deduction = daily_payroll_net * payroll_days
                profit = sales_total - purchase_total - payroll_deduction
                month_thumb = self._make_date_thumbnail(month, kind="month")
                monthly_display.append([
                    self._thumbnail_cell(month, month_thumb),
                    month,
                    self._money(sales_total),
                    self._money(purchase_total),
                    self._money(profit),
                ])
                monthly_totals["sales"] += sales_total
                monthly_totals["purchases"] += purchase_total
                monthly_totals["profit"] += profit
                monthly_totals["payroll"] += payroll_deduction

            self._populate_table(self.profit_monthly_table, monthly_display)
            self.profit_monthly_summary.setText(
                f"صافي المبيعات: {self._money(monthly_totals['sales'])} | "
                f"إجمالي المشتريات: {self._money(monthly_totals['purchases'])} | "
                f"الرواتب اليومية المحتسبة: {self._money(monthly_totals['payroll'])} | "
                f"صافي الربح بعد الرواتب: {self._money(monthly_totals['profit'])}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "تقرير الأرباح", f"تعذر تحميل التقرير:\n{exc}")
        finally:
            if conn:
                conn.close()

    def _refresh_month_picker_defaults(self):
        month_names = [
            "يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
            "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر",
        ]
        years = self._available_years()
        current_year = str(datetime.now().year)
        selected_year = current_year if current_year in years else (years[0] if years else current_year)
        selected_month = datetime.now().month

        self.year_picker.blockSignals(True)
        self.month_picker.blockSignals(True)
        self.year_picker.clear()
        for y in years or [current_year]:
            self.year_picker.addItem(y, int(y))
        idx_year = max(self.year_picker.findData(int(selected_year)), 0)
        self.year_picker.setCurrentIndex(idx_year)

        self.month_picker.clear()
        for i, label in enumerate(month_names, start=1):
            self.month_picker.addItem(label, i)
        idx_month = max(self.month_picker.findData(selected_month), 0)
        self.month_picker.setCurrentIndex(idx_month)
        self.month_picker.blockSignals(False)
        self.year_picker.blockSignals(False)
        self._load_monthly_detail()

    def _available_years(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "WITH years AS ("
            "SELECT strftime('%Y', paid_at) AS y FROM payments "
            "UNION ALL SELECT strftime('%Y', purchased_at) AS y FROM purchases"
            ") SELECT DISTINCT y FROM years WHERE y IS NOT NULL ORDER BY y DESC"
        )
        years = [row[0] for row in cur.fetchall() if row[0]]
        conn.close()
        return years

    def _load_monthly_detail(self):
        try:
            year = int(self.year_picker.currentData() or self.year_picker.currentText())
        except Exception:
            year = datetime.now().year
        try:
            month = int(self.month_picker.currentData() or self.month_picker.currentText())
        except Exception:
            month = datetime.now().month

        last_day = calendar.monthrange(year, month)[1]
        start_iso = datetime(year, month, 1, 0, 0).isoformat()
        end_iso = datetime(year, month, last_day, 23, 59, 59).isoformat()

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "WITH sales AS ("
            "SELECT DATE(p.paid_at) AS day, SUM(p.amount_cents) AS net_total FROM payments p "
            "WHERE p.paid_at BETWEEN ? AND ? GROUP BY day"  # noqa: E501
            "), purchase_totals AS ("
            "SELECT DATE(pr.purchased_at) AS day, SUM(pr.amount_cents) AS purchase_total FROM purchases pr "
            "WHERE pr.purchased_at BETWEEN ? AND ? GROUP BY day"  # noqa: E501
            "), days AS (SELECT day FROM sales UNION SELECT day FROM purchase_totals) "
            "SELECT d.day AS day, COALESCE(sales.net_total, 0) AS net_sales, "
            "COALESCE(purchase_totals.purchase_total, 0) AS purchases_total FROM days d "
            "LEFT JOIN sales ON sales.day = d.day LEFT JOIN purchase_totals ON purchase_totals.day = d.day "
            "ORDER BY d.day",
            (start_iso, end_iso, start_iso, end_iso),
        )
        daily_rows = cur.fetchall()
        conn.close()

        payroll_per_day = staff_service.daily_payroll_expense()
        payroll_days = len({row["day"] for row in daily_rows if row["day"]})
        month_label = f"{year}-{month:02d}"
        self._update_range_strip(self.monthly_detail_strip, month_label, month_label, kind="day")

        table_rows = []
        totals = {"sales": 0, "purchases": 0, "profit": 0, "payroll": 0}
        for row in daily_rows:
            day = row["day"] or ""
            sales_total = int(row["net_sales"] or 0)
            purchase_total = int(row["purchases_total"] or 0)
            profit = sales_total - purchase_total - payroll_per_day
            day_thumb = self._make_date_thumbnail(day, kind="day")
            table_rows.append([
                self._thumbnail_cell(day, day_thumb),
                day,
                self._money(sales_total),
                self._money(purchase_total),
                self._money(profit),
            ])
            totals["sales"] += sales_total
            totals["purchases"] += purchase_total
            totals["profit"] += profit

        totals["payroll"] = payroll_per_day * payroll_days
        self._populate_table(self.monthly_detail_table, table_rows)
        net_after_payroll = totals["profit"]
        self.monthly_detail_summary.setText(
            f"صافي المبيعات: {self._money(totals['sales'])} | "
            f"إجمالي المشتريات: {self._money(totals['purchases'])} | "
            f"الرواتب اليومية المحتسبة: {self._money(totals['payroll'])} | "
            f"صافي الربح بعد الرواتب: {self._money(net_after_payroll)}"
        )

    # ------------------------------------------------------------- price log
    def _build_price_log_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.price_table = self._make_table([
            "الوقت", "المستخدم", "العنصر", "السعر القديم", "السعر الجديد", "تفاصيل"
        ])
        layout.addWidget(self.price_table, 1)

        controls = QHBoxLayout()
        refresh = QPushButton("تحديث السجل")
        refresh.clicked.connect(self._load_price_log)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.price_table, "price_log"))
        controls.addStretch(1)
        layout.addLayout(controls)

        return widget

    def _load_price_log(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT ts, username, entity_name, old_value, new_value, extra "
            "FROM audit_log WHERE action='price_change' ORDER BY id DESC LIMIT 200"
        )
        rows = cur.fetchall()
        conn.close()
        rows_list = [[r["ts"], r["username"], r["entity_name"], r["old_value"], r["new_value"], r["extra"]] for r in
                     rows]
        self._populate_table(self.price_table, rows_list)

    # --------------------------------------------------------- deleted items
    def _build_deleted_items_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.deleted_items_table = self._make_table([
            "التوقيت",
            "المستخدم",
            "رقم الطاولة",
            "العنصر",
            "الكمية",
            "السعر للوحدة",
            "الملاحظة",
        ])
        layout.addWidget(self.deleted_items_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        controls.addWidget(QLabel("من:"))
        start_dt = QDateTime.currentDateTime()
        start_dt.setDate(QDate.currentDate().addDays(-6))
        start_dt.setTime(QTime(0, 0))
        self.deleted_items_from = QDateTimeEdit(start_dt)
        self.deleted_items_from.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        self.deleted_items_from.setCalendarPopup(True)
        controls.addWidget(self.deleted_items_from)

        controls.addWidget(QLabel("إلى:"))
        self.deleted_items_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.deleted_items_to.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        self.deleted_items_to.setCalendarPopup(True)
        controls.addWidget(self.deleted_items_to)

        controls.addWidget(QLabel("الطاولة:"))
        self.deleted_items_table_filter = QLineEdit()
        self.deleted_items_table_filter.setPlaceholderText("مثال: A1")
        self.deleted_items_table_filter.setMaximumWidth(120)
        controls.addWidget(self.deleted_items_table_filter)

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_deleted_items_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.deleted_items_table, "deleted_items"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.deleted_items_summary = QLabel("")
        self.deleted_items_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.deleted_items_summary)

        return widget

    def _load_deleted_items_report(self):
        start, end = self._datetime_bounds(self.deleted_items_from, self.deleted_items_to)
        table_filter = self.deleted_items_table_filter.text().strip().upper()
        query = (
            "SELECT ts, username, entity_name, old_value, new_value, extra "
            "FROM audit_log WHERE action='order_item_deleted' AND ts BETWEEN ? AND ?"
        )
        params: list[str] = [start, end]
        if table_filter:
            query += " AND UPPER(entity_name)=?"
            params.append(table_filter)
        query += " ORDER BY ts DESC"

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(query, params)
        rows = cur.fetchall()
        conn.close()

        table_rows: list[list[str]] = []
        for row in rows:
            ts = (row["ts"] or "").replace("T", " ")[:19]
            username = row.get("username", "") if isinstance(row, dict) else row["username"]
            table_code = (row["entity_name"] or "").strip()
            product = row["old_value"] or ""
            qty_raw = row["new_value"]
            try:
                qty = float(qty_raw) if qty_raw is not None else 0.0
            except (TypeError, ValueError):
                qty = 0.0

            unit_price_cents = None
            note = ""
            extra_raw = row["extra"]
            if extra_raw:
                try:
                    extra_data = json.loads(extra_raw)
                    unit_price_cents = extra_data.get("unit_price_cents")
                    note = extra_data.get("note") or ""
                except Exception:
                    note = str(extra_raw)

            unit_price = self._money(int(unit_price_cents)) if unit_price_cents is not None else "-"

            table_rows.append([
                ts,
                username,
                table_code,
                product,
                f"{qty:g}",
                unit_price,
                note,
            ])

        self._populate_table(self.deleted_items_table, table_rows)
        self.deleted_items_summary.setText(f"عدد العمليات: {len(table_rows)}")

    # -------------------------------------------------------------- inventory
    def _build_inventory_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        cards_row = QHBoxLayout()
        cards_row.setContentsMargins(0, 0, 0, 0)
        cards_row.setSpacing(12)
        self.inventory_card_items = KpiCard("📋", "منتجات متتبعة", "—")
        self.inventory_card_low = KpiCard("⚠️", "دون الحد الأدنى", "—")
        self.inventory_card_packages = KpiCard("📦", "متوسط العبوة", "—")
        for card in (
            self.inventory_card_items,
            self.inventory_card_low,
            self.inventory_card_packages,
        ):
            cards_row.addWidget(card)
        cards_row.addStretch(1)
        layout.addLayout(cards_row)

        self.inventory_table = DSTable(0, 5)
        self.inventory_table.set_headers([
            "المنتج",
            "القسم",
            "المتاح",
            "الحد الأدنى",
            "حجم العبوة",
        ])
        self.inventory_table.set_column_alignments(
            [
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                Qt.AlignmentFlag.AlignCenter,
                Qt.AlignmentFlag.AlignCenter,
                Qt.AlignmentFlag.AlignCenter,
            ]
        )
        layout.addWidget(self.inventory_table, 1)

        controls = QHBoxLayout()
        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_inventory_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.inventory_table, "inventory_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        return widget

    def _load_inventory_report(self):
        entries = order_manager.catalog.inventory_overview()
        rows = [
            [
                r["name"],
                r["category"],
                self._format_qty(r.get("stock_qty", 0)),
                self._format_qty(r.get("min_stock", 0)),
                self._format_qty(r.get("package_size", 0)),
            ]
            for r in entries
            if r.get("track_stock", True)
        ]
        self._populate_table(self.inventory_table, rows)
        tracked = len(rows)
        low_stock = sum(
            1
            for r in entries
            if r.get("track_stock", True)
            and float(r.get("stock_qty", 0) or 0) < float(r.get("min_stock", 0) or 0)
        )
        avg_package = 0.0
        if tracked:
            package_total = sum(float(r.get("package_size", 0) or 0) for r in entries if r.get("track_stock", True))
            avg_package = package_total / tracked if package_total else 0.0
        self.inventory_card_items.value_label.setText(str(tracked))
        self.inventory_card_low.value_label.setText(str(low_stock))
        self.inventory_card_packages.value_label.setText(self._format_qty(avg_package))

    # --------------------------------------------------------- attendance log
    def _build_attendance_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.attendance_table = self._make_table([
            "الموظف",
            "الدور",
            "عدد الجلسات",
            "إجمالي الساعات",
            "إجمالي الدقائق",
        ])
        layout.addWidget(self.attendance_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.addWidget(QLabel("من:"))
        self.attendance_from = QDateEdit(QDate.currentDate().addDays(-6))
        self.attendance_from.setCalendarPopup(True)
        self.attendance_from.setMinimumWidth(150)
        controls.addWidget(self.attendance_from)

        controls.addWidget(QLabel("الساعة:"))
        self.attendance_from_time = QTimeEdit(QTime(0, 0))
        self._configure_time_edit(self.attendance_from_time)
        self.attendance_from_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.attendance_from_time))

        controls.addWidget(QLabel("إلى:"))
        self.attendance_to = QDateEdit(QDate.currentDate())
        self.attendance_to.setCalendarPopup(True)
        self.attendance_to.setMinimumWidth(150)
        controls.addWidget(self.attendance_to)

        controls.addWidget(QLabel("الساعة:"))
        self.attendance_to_time = QTimeEdit(QTime(23, 59))
        self._configure_time_edit(self.attendance_to_time)
        self.attendance_to_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.attendance_to_time))

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_attendance_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.attendance_table, "attendance_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.attendance_summary = QLabel("")
        self.attendance_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.attendance_summary)

        return widget

    def _load_attendance_report(self):
        start, end = self._datetime_bounds_from_date_time(
            self.attendance_from,
            self.attendance_from_time,
            self.attendance_to,
            self.attendance_to_time,
        )
        try:
            entries = staff_service.summarize_session_hours(start, end)
        except Exception as exc:
            QMessageBox.warning(self, "ساعات العمل", f"تعذر تحميل التقرير:\n{exc}")
            self._populate_table(self.attendance_table, [])
            self.attendance_summary.setText("تعذر تحميل البيانات")
            return

        table_rows = []
        total_hours = 0.0
        total_sessions = 0
        for entry in entries:
            username = entry.get("username", "")
            role = entry.get("role", "")
            sessions = int(entry.get("sessions", 0) or 0)
            hours = float(entry.get("hours", 0.0) or 0.0)
            minutes = int(entry.get("minutes", 0) or 0)
            table_rows.append([
                username,
                role,
                str(sessions),
                f"{hours:.2f}",
                str(minutes),
            ])
            total_hours += hours
            total_sessions += sessions

        self._populate_table(self.attendance_table, table_rows)
        self.attendance_summary.setText(
            f"عدد الجلسات: {total_sessions} | إجمالي الساعات: {total_hours:.2f}"
        )

    # --------------------------------------------------------- shift summary
    def _build_shift_summary_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.shift_table = self._make_table([
            "الموظف",
            "بداية الوردية",
            "نهاية الوردية",
            "المدة",
            "طلبات فتحت",
            "طلبات أغلقت",
            "طلبات ملغاة",
            "عدد المدفوعات",
            "إجمالي التحصيل",
            "إجمالي الخصومات",
        ])
        layout.addWidget(self.shift_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        controls.addWidget(QLabel("من:"))
        self.shift_from_date = QDateEdit(QDate.currentDate().addDays(-1))
        self.shift_from_date.setCalendarPopup(True)
        controls.addWidget(self.shift_from_date)

        controls.addWidget(QLabel("الساعة:"))
        self.shift_from_time = QTimeEdit(QTime(0, 0))
        self._configure_time_edit(self.shift_from_time)
        self.shift_from_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.shift_from_time))

        controls.addWidget(QLabel("إلى:"))
        self.shift_to_date = QDateEdit(QDate.currentDate())
        self.shift_to_date.setCalendarPopup(True)
        controls.addWidget(self.shift_to_date)

        controls.addWidget(QLabel("الساعة:"))
        self.shift_to_time = QTimeEdit(QTime(23, 59))
        self._configure_time_edit(self.shift_to_time)
        self.shift_to_time.setMinimumWidth(90)
        controls.addWidget(self._wrap_ltr(self.shift_to_time))

        controls.addWidget(QLabel("الموظف:"))
        self.shift_user_filter = QComboBox()
        self.shift_user_filter.addItem("الكل", "")
        self._populate_shift_user_filter()
        controls.addWidget(self.shift_user_filter)

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_shift_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.shift_table, "shift_summary"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.shift_summary = QLabel("")
        self.shift_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.shift_summary)

        return widget

    def _populate_shift_user_filter(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT username FROM users ORDER BY username")
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            username = (row["username"] or "").strip()
            if username:
                self.shift_user_filter.addItem(username, username)

    def _load_shift_report(self):
        start_iso, end_iso = self._datetime_bounds_from_date_time(
            self.shift_from_date,
            self.shift_from_time,
            self.shift_to_date,
            self.shift_to_time,
        )
        try:
            start_dt = datetime.fromisoformat(start_iso)
            end_dt = datetime.fromisoformat(end_iso)
        except ValueError:
            QMessageBox.warning(self, "ملخص الورديات", "تواريخ غير صالحة.")
            return

        username_filter = self.shift_user_filter.currentData() or ""
        now = datetime.now()

        try:
            sessions = staff_service.list_sessions_between(start_dt, end_dt)
        except Exception as exc:
            QMessageBox.warning(self, "ملخص الورديات", f"تعذر تحميل البيانات:\n{exc}")
            self._populate_table(self.shift_table, [])
            self.shift_summary.setText("تعذر تحميل البيانات")
            return

        rows: list[list[str]] = []
        totals = {
            "sessions": 0,
            "seconds": 0,
            "opened": 0,
            "closed": 0,
            "voided": 0,
            "payments": 0,
            "net": 0,
            "discounts": 0,
        }

        for session in sessions:
            username = session.get("username", "")
            if username_filter and username != username_filter:
                continue
            session_start = max(session.get("login_at") or start_dt, start_dt)
            raw_end = session.get("logout_at") or now
            session_end = min(raw_end, end_dt)
            if session_end <= session_start:
                continue

            metrics = staff_service.summarize_shift_activity(username, session_start, session_end)
            duration = int(metrics.get("duration_seconds", 0) or 0)
            if duration <= 0 and metrics.get("orders_opened", 0) <= 0 and metrics.get("payments_count", 0) <= 0:
                continue

            rows.append([
                username,
                session_start.strftime("%Y-%m-%d %I:%M %p"),
                session_end.strftime("%Y-%m-%d %I:%M %p"),
                self._format_duration(duration),
                str(metrics.get("orders_opened", 0)),
                str(metrics.get("orders_closed", 0)),
                str(metrics.get("voided_orders", 0)),
                str(metrics.get("payments_count", 0)),
                self._money(int(metrics.get("payments_total_cents", 0))),
                self._money(int(metrics.get("discount_cents", 0))),
            ])

            totals["sessions"] += 1
            totals["seconds"] += duration
            totals["opened"] += int(metrics.get("orders_opened", 0))
            totals["closed"] += int(metrics.get("orders_closed", 0))
            totals["voided"] += int(metrics.get("voided_orders", 0))
            totals["payments"] += int(metrics.get("payments_count", 0))
            totals["net"] += int(metrics.get("payments_total_cents", 0))
            totals["discounts"] += int(metrics.get("discount_cents", 0))

        self._populate_table(self.shift_table, rows)
        if rows:
            hours_total = totals["seconds"] / 3600.0 if totals["seconds"] else 0
            summary = (
                f"عدد الورديات: {totals['sessions']} | "
                f"إجمالي الساعات: {hours_total:.2f} | "
                f"صافي التحصيل: {self._money(totals['net'])} | "
                f"الخصومات: {self._money(totals['discounts'])}"
            )
        else:
            summary = "لا توجد بيانات للفترة المحددة."
        self.shift_summary.setText(summary)

    # ---------------------------------------------------------- staff payroll
    def _build_deductions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.deductions_table = self._make_table([
            "الموظف",
            "الدور",
            "الراتب",
            "الخصومات",
            "السلف",
            "الصافي",
        ])
        layout.addWidget(self.deductions_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_deductions_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.deductions_table, "deductions_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.deductions_summary = QLabel("")
        self.deductions_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.deductions_summary)

        return widget

    def _load_deductions_report(self):
        rows = staff_service.list_payroll_rows()
        table_rows: list[list[str]] = []
        totals = {"salary": 0, "deductions": 0, "loans": 0, "net": 0}

        for row in rows:
            username = row.get("display_name") or row.get("username", "")
            role = row.get("role", "")
            salary = int(row.get("salary_cents") or 0)
            deduction = int(row.get("deductions_cents") or 0)
            loan = int(row.get("loan_cents") or 0)
            net = salary - deduction - loan

            table_rows.append([
                username,
                role,
                self._money(salary),
                self._money(deduction),
                self._money(loan),
                self._money(net),
            ])

            totals["salary"] += salary
            totals["deductions"] += deduction
            totals["loans"] += loan
            totals["net"] += net

        self._populate_table(self.deductions_table, table_rows)
        self.deductions_summary.setText(
            f"عدد الموظفين: {len(table_rows)} | "
            f"إجمالي الرواتب: {self._money(totals['salary'])} | "
            f"إجمالي الخصومات: {self._money(totals['deductions'])} | "
            f"إجمالي السلف: {self._money(totals['loans'])} | "
            f"صافي الرواتب: {self._money(totals['net'])}"
        )

    def _build_payroll_history_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.payroll_history_table = self._make_table([
            "التوقيت",
            "المصدر",
            "الموظف",
            "الدور",
            "نوع الأجر",
            "الراتب",
            "الخصومات",
            "السلف",
            "الصافي",
        ])
        layout.addWidget(self.payroll_history_table, 1)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        controls.setContentsMargins(8, 0, 8, 0)
        controls.addWidget(QLabel("من:"))
        start_dt = QDateTime.currentDateTime()
        start_dt.setDate(QDate.currentDate().addDays(-6))
        start_dt.setTime(QTime(0, 0))
        self.payroll_history_from = QDateTimeEdit(start_dt)
        self.payroll_history_from.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        self.payroll_history_from.setCalendarPopup(True)
        controls.addWidget(self.payroll_history_from)

        controls.addWidget(QLabel("إلى:"))
        self.payroll_history_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.payroll_history_to.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        self.payroll_history_to.setCalendarPopup(True)
        controls.addWidget(self.payroll_history_to)

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_payroll_history)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.payroll_history_table, "payroll_history"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.payroll_history_summary = QLabel("")
        self.payroll_history_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.payroll_history_summary)

        return widget

    def _load_payroll_history(self):
        start, end = self._datetime_bounds(self.payroll_history_from, self.payroll_history_to)
        try:
            rows = staff_service.list_payroll_history(start, end)
        except Exception as exc:
            QMessageBox.warning(self, "سجل الرواتب", f"تعذر تحميل السجل:\n{exc}")
            self._populate_table(self.payroll_history_table, [])
            self.payroll_history_summary.setText("تعذر تحميل البيانات")
            return

        table_rows: list[list[str]] = []
        totals = {"salary": 0, "deductions": 0, "loans": 0, "net": 0}
        for row in rows:
            recorded_at = row.get("recorded_at", "")
            source = str(row.get("source") or "system")
            if source == "system":
                display_source = "مستخدم النظام"
            elif source == "manual":
                display_source = "موظف خارجي"
            elif source == "payout":
                display_source = "صرف راتب"
            else:
                display_source = source
            period = str(row.get("salary_period") or "monthly")
            period_label = "شهري" if period == "monthly" else "يومي"
            salary = int(row.get("salary_cents") or 0)
            deduction = int(row.get("deductions_cents") or 0)
            loan = int(row.get("loan_cents") or 0)
            net = int(row.get("net_cents") or (salary - deduction - loan))
            table_rows.append([
                recorded_at.replace("T", " ")[:16],
                display_source,
                row.get("display_name", ""),
                row.get("role", ""),
                period_label,
                self._money(salary),
                self._money(deduction),
                self._money(loan),
                self._money(net),
            ])

            totals["salary"] += salary
            totals["deductions"] += deduction
            totals["loans"] += loan
            totals["net"] += net

        self._populate_table(self.payroll_history_table, table_rows)
        if table_rows:
            summary = (
                f"عدد السجلات: {len(table_rows)} | "
                f"إجمالي الرواتب: {self._money(totals['salary'])} | "
                f"إجمالي الخصومات: {self._money(totals['deductions'])} | "
                f"إجمالي السلف: {self._money(totals['loans'])} | "
                f"صافي المسجل: {self._money(totals['net'])}"
            )
        else:
            summary = "لا توجد بيانات في الفترة المحددة."
        self.payroll_history_summary.setText(summary)

    # ------------------------------------------------------ stakeholders log
    def _build_stakeholder_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.stakeholder_table = self._make_table([
            "الوقت", "المستخدم", "الإجراء", "النوع", "العنصر", "القيمة السابقة", "القيمة الجديدة", "تفاصيل إضافية"
        ])
        layout.addWidget(self.stakeholder_table, 1)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("من:"))
        start_dt = QDateTime.currentDateTime()
        start_dt.setTime(QTime(0, 0))
        self.stakeholder_from = QDateTimeEdit(start_dt)
        self.stakeholder_from.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        self.stakeholder_from.setCalendarPopup(True)
        controls.addWidget(self.stakeholder_from)

        controls.addWidget(QLabel("إلى:"))
        self.stakeholder_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.stakeholder_to.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        self.stakeholder_to.setCalendarPopup(True)
        controls.addWidget(self.stakeholder_to)

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_stakeholder_report)
        controls.addWidget(refresh)
        controls.addWidget(self._make_export_button(self.stakeholder_table, "stakeholder_report"))
        controls.addStretch(1)
        layout.addLayout(controls)

        self.stakeholder_summary = QLabel("")
        self.stakeholder_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.stakeholder_summary)

        return widget

    def _load_stakeholder_report(self):
        start, end = self._datetime_bounds(self.stakeholder_from, self.stakeholder_to)
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT ts, username, action, entity_type, entity_name, old_value, new_value, extra "
            "FROM audit_log WHERE ts BETWEEN ? AND ? ORDER BY ts",
            (start, end),
        )
        rows = cur.fetchall()
        conn.close()

        table_rows = [
            [r["ts"], r["username"], r["action"], r["entity_type"], r["entity_name"], r["old_value"], r["new_value"],
             r["extra"]] for r in rows]
        self._populate_table(self.stakeholder_table, table_rows)
        self.stakeholder_summary.setText(f"عدد الأحداث: {len(table_rows)}")

    # ----------------------------------------------------- destructive tools
    def _build_cleanup_panel(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("CleanupPanel")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        layout.addWidget(QLabel("حذف البيانات من:"))
        self.cleanup_from = QDateTimeEdit(QDateTime.currentDateTime().addDays(-30))
        self.cleanup_from.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        self.cleanup_from.setCalendarPopup(True)
        layout.addWidget(self.cleanup_from)

        layout.addWidget(QLabel("إلى:"))
        self.cleanup_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.cleanup_to.setDisplayFormat("yyyy-MM-dd hh:mm AP")
        self.cleanup_to.setCalendarPopup(True)
        layout.addWidget(self.cleanup_to)

        layout.addWidget(QLabel("كلمة المرور:"))
        self.cleanup_password = QLineEdit()
        self.cleanup_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.cleanup_password.setPlaceholderText("كلمة مرور المدير")
        self.cleanup_password.setMinimumWidth(160)
        layout.addWidget(self.cleanup_password)

        self.cleanup_button = QPushButton("حذف البيانات للفترة")
        self.cleanup_button.clicked.connect(self._handle_cleanup)
        self.cleanup_button.setEnabled(bool(self.actor_username))
        layout.addWidget(self.cleanup_button)

        self.cleanup_status = QLabel("")
        self.cleanup_status.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.cleanup_status.setWordWrap(True)
        layout.addWidget(self.cleanup_status, 1)

        frame.setStyleSheet(
            "#CleanupPanel { border: 1px solid rgba(0,0,0,0.15); border-radius: 12px; }"
        )
        return frame

    def _handle_cleanup(self):
        if not self.actor_username:
            QMessageBox.warning(self, "حذف البيانات", "يجب تسجيل الدخول بحساب مدير لإتمام العملية.")
            return

        password = self.cleanup_password.text().strip()
        if not password:
            QMessageBox.warning(self, "حذف البيانات", "أدخل كلمة المرور لتأكيد العملية.")
            return

        if password != CLEANUP_STATIC_PASSWORD:
            QMessageBox.warning(self, "حذف البيانات", "كلمة المرور غير صحيحة.")
            return

        start_dt = self.cleanup_from.dateTime().toPyDateTime()
        end_dt = self.cleanup_to.dateTime().toPyDateTime()

        confirm = QMessageBox.question(
            self,
            "تأكيد الحذف",
            "سيتم حذف جميع الطلبات، المدفوعات، المشتريات والملاحظات في هذه الفترة. هل تريد المتابعة؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            summary = maintenance_service.purge_activity_between(start_dt, end_dt)
        except Exception as exc:
            QMessageBox.critical(self, "حذف البيانات", f"تعذر حذف البيانات:\n{exc}")
            return

        self.cleanup_password.clear()
        removed_orders = summary.get("orders", 0)
        removed_payments = summary.get("order_payments", 0) + summary.get("payments", 0)
        removed_purchases = summary.get("purchases", 0)
        removed_expenses = summary.get("expenses", 0)
        removed_sessions = summary.get("user_sessions", 0)
        status = (
            f"تم حذف {removed_orders} طلبًا، {removed_payments} عملية دفع، "
            f"{removed_purchases} مشتريات، {removed_expenses} مصروفات و {removed_sessions} جلسات." 
        )
        self.cleanup_status.setText(status)
        QMessageBox.information(self, "حذف البيانات", status)
        self._reload_all_reports()

    def _reload_current_tab(self, index: int | None = None):
        idx = self.tabs.currentIndex() if index is None else index
        loaders = {
            0: self._load_daily_report,
            1: self._load_order_items_report,
            2: self._load_cashier_report,
            3: self._load_product_report,
            4: self._load_discounts_report,
            5: self._load_purchases_report,
            6: self._load_profit_report,
            7: self._load_price_log,
            8: self._load_deleted_items_report,
            9: self._load_inventory_report,
            10: self._load_attendance_report,
            11: self._load_shift_report,
            12: self._load_deductions_report,
            13: self._load_payroll_history,
            14: self._load_stakeholder_report,
        }
        loader = loaders.get(idx)
        if loader:
            loader()

    def _reload_all_reports(self):
        self._load_daily_report()
        self._load_order_items_report()
        self._load_cashier_report()
        self._load_product_report()
        self._load_discounts_report()
        self._load_purchases_report()
        self._load_profit_report()
        self._load_price_log()
        self._load_deleted_items_report()
        self._load_inventory_report()
        self._load_attendance_report()
        self._load_shift_report()
        self._load_deductions_report()
        self._load_payroll_history()
        self._load_stakeholder_report()


    # ------------------------------------------------------------- utilities
    def _make_export_button(self, table: QTableWidget, default_name: str) -> QPushButton:
        button = QPushButton("تنزيل Excel")
        button.clicked.connect(lambda _, t=table, n=default_name: self._export_table(t, n))
        return button

    def _build_range_strip(self, *, kind: str = "day") -> QFrame:
        """Lightweight range indicator used above the profit tables."""

        palettes = {
            "day": ("#FFF7E6", "#F0B46F"),
            "month": ("#E6F4FF", "#8DC4F5"),
            "detail": ("#F5F0FF", "#B7A1F5"),
        }
        bg, accent = palettes.get(kind, palettes["day"])

        strip = QFrame()
        strip.setObjectName("RangeStrip")
        strip.setFrameShape(QFrame.Shape.StyledPanel)
        strip.setStyleSheet(
            f"#RangeStrip {{"
            f"background: {bg};"
            "border: 1px solid #e0e0e0;"
            "border-radius: 10px;"
            "padding: 8px 10px;"
            "}"
            "#RangeStrip QLabel {"
            "font-weight: 600;"
            "}"
            "#RangeStrip .Accent {"
            f"color: {accent};"
            "}"
        )

        layout = QHBoxLayout(strip)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(6)

        prefix = QLabel("الفترة:")
        prefix.setProperty("class", "Accent")
        layout.addWidget(prefix)

        start_label = QLabel("—")
        start_label.setObjectName("RangeStart")
        layout.addWidget(start_label)

        dash = QLabel("–")
        dash.setProperty("class", "Accent")
        layout.addWidget(dash)

        end_label = QLabel("—")
        end_label.setObjectName("RangeEnd")
        layout.addWidget(end_label)

        layout.addStretch(1)

        strip.start_label = start_label  # type: ignore[attr-defined]
        strip.end_label = end_label  # type: ignore[attr-defined]
        return strip

    def _update_range_strip(self, strip: QFrame, start_label: str, end_label: str, *, kind: str = "day") -> None:
        """Refresh the displayed date range for the provided strip widget."""

        if strip is None:
            return

        start_text = (start_label or "—").strip() or "—"
        end_text = (end_label or start_text).strip() or start_text

        start_widget = getattr(strip, "start_label", None)
        end_widget = getattr(strip, "end_label", None)

        if isinstance(start_widget, QLabel):
            start_widget.setText(start_text)
        if isinstance(end_widget, QLabel):
            end_widget.setText(end_text)

        # Update styling to keep the accent color aligned with the strip kind
        palettes = {
            "day": "#F0B46F",
            "month": "#8DC4F5",
            "detail": "#B7A1F5",
        }
        accent = palettes.get(kind)
        if accent:
            for widget in (start_widget, end_widget):
                if isinstance(widget, QLabel):
                    widget.setStyleSheet(f"color: {accent};")

    def _make_table(self, headers: list[str], *, include_thumbnail: bool = False) -> QTableWidget:
        labels = list(headers)
        thumbnail_column = -1
        if include_thumbnail:
            thumbnail_column = 0
            labels = ["معاينة"] + labels

        table = QTableWidget(0, len(labels))
        table.setHorizontalHeaderLabels(labels)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setWordWrap(True)
        header = table.horizontalHeader()
        header.setMinimumSectionSize(110)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        table.setProperty("thumbnail_column", thumbnail_column)
        if include_thumbnail:
            table.setIconSize(QSize(self._thumbnail_size(), self._thumbnail_size()))
            header.resizeSection(0, self._thumbnail_size() + 12)
        return table

    def _populate_table(self, table: QTableWidget, rows: list[list[str]]):
        table.setRowCount(len(rows))
        thumb_col = table.property("thumbnail_column")
        if thumb_col is None:
            thumb_col = -1
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                cell = self._normalize_cell(value)
                display = cell.text
                item = QTableWidgetItem(display)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setToolTip(display)
                table.setItem(r, c, item)

                if thumb_col == c:
                    table.setCellWidget(r, c, self._build_thumbnail_widget(cell))
        if not rows:
            table.setRowCount(0)

    def _thumbnail_size(self) -> int:
        return 72

    def _make_date_thumbnail(self, label: str, *, kind: str = "day") -> QPixmap | None:
        label = (label or "").strip()
        if not label:
            return None

        size = self._thumbnail_size()
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)

        palettes = {
            "day": ("#FAD8B6", "#E8A86B"),
            "month": ("#C5E5FF", "#7CB7E3"),
            "detail": ("#E7D8FF", "#B094F7"),
        }
        start, end = palettes.get(kind, palettes["day"])

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(start))
        painter.drawRoundedRect(0, 0, size - 1, size - 1, 12, 12)

        painter.setBrush(QColor(end))
        painter.drawRoundedRect(6, 6, size - 13, size - 13, 10, 10)

        text = label
        if kind == "month" and len(label) >= 7:
            text = f"{label[5:7]} / {label[:4]}"
        elif len(label) >= 10:
            text = f"{label[-2:]}\n{label[5:7]}"

        painter.setPen(QColor("#1B0F08"))
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)
        painter.setFont(font)
        painter.drawText(pixmap.rect().adjusted(6, 6, -6, -6), Qt.AlignmentFlag.AlignCenter, text)

        painter.setBrush(QColor("#F0C674"))
        painter.setPen(QColor("#6B4B2A"))
        painter.drawEllipse(size - 26, size - 26, 20, 20)
        font.setPointSize(7)
        painter.setFont(font)
        painter.drawText(pixmap.rect().adjusted(size - 28, size - 28, -4, -4), Qt.AlignmentFlag.AlignCenter, self.currency[:2])
        painter.end()

        return pixmap

    def _normalize_cell(self, value):
        if isinstance(value, ReportCell):
            return value
        if isinstance(value, dict):
            return ReportCell(
                text=str(value.get("text") or ""),
                thumbnail=value.get("thumbnail"),
                badge=value.get("badge"),
            )
        if isinstance(value, tuple) and len(value) >= 2:
            return ReportCell(text=str(value[0] or ""), thumbnail=value[1], badge=value[2] if len(value) > 2 else None)
        return ReportCell(text=str(value or ""))

    def _build_thumbnail_widget(self, cell: "ReportCell") -> QWidget:
        size = self._thumbnail_size()
        label = QLabel()
        label.setFixedSize(size, size)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            "border: 1px solid #d9d9d9; border-radius: 8px; background: #fafafa; padding: 6px;"
        )

        pixmap: QPixmap | None = None
        if isinstance(cell.thumbnail, QPixmap):
            pixmap = cell.thumbnail
        elif isinstance(cell.thumbnail, (bytes, bytearray)):
            pixmap = QPixmap()
            pixmap.loadFromData(cell.thumbnail)
        elif isinstance(cell.thumbnail, str) and cell.thumbnail.strip():
            pixmap = QPixmap(cell.thumbnail)

        if pixmap is not None and not pixmap.isNull():
            scaled = pixmap.scaled(size - 16, size - 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(scaled)
        else:
            badge = (cell.badge or cell.text or "—").strip()
            label.setText(badge[:3])
            label.setStyleSheet(
                "border: 1px solid #d9d9d9; border-radius: 8px; background: #f5f5f5; padding: 6px; color: #666;"
            )
        return label

    def _thumbnail_cell(self, label: str, thumbnail: QPixmap | bytes | str | None = None) -> "ReportCell":
        return ReportCell(text=label or "", thumbnail=thumbnail, badge=(label or "").strip()[:2])

    def _money(self, cents: int) -> str:
        return format_pounds(cents, self.currency)

    def _format_qty(self, qty) -> str:
        try:
            q = float(qty)
        except (TypeError, ValueError):
            return "0"
        if abs(q - round(q)) < 1e-6:
            return str(int(round(q)))
        return f"{q:.2f}"

    def _format_duration(self, seconds: int) -> str:
        seconds = max(int(seconds or 0), 0)
        hours, rem = divmod(seconds, 3600)
        minutes, secs = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _weekday_name(self, date_obj):
        if not date_obj:
            return ""
        names = [
            "الإثنين",
            "الثلاثاء",
            "الأربعاء",
            "الخميس",
            "الجمعة",
            "السبت",
            "الأحد",
        ]
        try:
            return names[date_obj.weekday()]
        except Exception:
            return ""

    def _parse_iso_datetime(self, value: str | None):
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except Exception:
            return None

        # Stored timestamps are in UTC; normalize to local time for display so
        # report rows match the table history dialog.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        try:
            return dt.astimezone()
        except Exception:
            return dt

    def _configure_time_edit(self, widget: QTimeEdit) -> None:
        widget.setDisplayFormat("hh:mm AP")
        widget.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        widget.setLocale(QLocale(QLocale.Language.English, QLocale.Country.UnitedStates))
        line_edit = widget.lineEdit()
        if line_edit is not None:
            line_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            line_edit.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )

    def _wrap_ltr(self, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        container.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        return container

    def _date_bounds(self, start_widget: QDateEdit, end_widget: QDateEdit) -> tuple[str, str]:
        s = datetime.combine(start_widget.date().toPyDate(), datetime.min.time())
        e = datetime.combine(end_widget.date().toPyDate(), datetime.max.time())
        return s.isoformat(), e.isoformat()

    def _datetime_bounds(self, start_widget: QDateTimeEdit, end_widget: QDateTimeEdit) -> tuple[str, str]:
        s = start_widget.dateTime().toPyDateTime()
        e = end_widget.dateTime().toPyDateTime()
        if e < s:
            e = s
        return s.isoformat(), e.isoformat()

    def _datetime_bounds_from_date_time(
        self,
        start_date_widget: QDateEdit,
        start_time_widget: QTimeEdit,
        end_date_widget: QDateEdit,
        end_time_widget: QTimeEdit,
    ) -> tuple[str, str]:
        start_dt = datetime.combine(
            start_date_widget.date().toPyDate(), start_time_widget.time().toPyTime()
        )
        end_dt = datetime.combine(
            end_date_widget.date().toPyDate(), end_time_widget.time().toPyTime()
        )
        if end_dt < start_dt:
            end_dt = start_dt
        return start_dt.isoformat(), end_dt.isoformat()

    def _export_table(self, table: QTableWidget, default_name: str) -> None:
        # Export table to Excel with timestamped filename.
        # Generate filename with current date and time
        timestamp = datetime.now().strftime("%Y-%m-%d_%I-%M-%S_%p")
        suggested_filename = f"{default_name}_{timestamp}.xlsx"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "تصدير التقرير",
            suggested_filename,
            "Excel (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"

        headers = [table.horizontalHeaderItem(c).text() for c in range(table.columnCount())]
        rows = [
            [table.item(r, c).text() if table.item(r, c) else "" for c in range(table.columnCount())]
            for r in range(table.rowCount())
        ]

        try:
            from beirut_pos.utils.excel import write_protected_workbook
            write_protected_workbook(path, headers, rows, title=default_name)
        except Exception as exc:
            QMessageBox.critical(self, "فشل التصدير", f"تعذر إنشاء ملف Excel:\n{exc}")
            return

        QMessageBox.information(
            self,
            "تم التصدير",
            "تم إنشاء ملف Excel محمي من التعديل بنجاح."
        )
