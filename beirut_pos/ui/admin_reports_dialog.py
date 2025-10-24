from datetime import datetime

from PyQt6.QtCore import Qt, QDate, QDateTime, QTime
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QDateTimeEdit,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QComboBox,
    QSizePolicy,
)

from ..core.db import get_conn, setting_get
from .common.big_dialog import BigDialog
from ..services.orders import order_manager
from ..services import staff as staff_service
from ..utils.currency import format_pounds


class AdminReportsDialog(BigDialog):
    """Dashboard of operational reports for managers."""

    def __init__(self):
        super().__init__("التقارير الإدارية", remember_key="reports", parent=None)
        self.currency = setting_get("currency", "EGP") or "EGP"

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_daily_tab(), "ملخص يومي")
        self.tabs.addTab(self._build_cashier_tab(), "حسب الكاشير")
        self.tabs.addTab(self._build_products_tab(), "الأصناف")
        self.tabs.addTab(self._build_discounts_tab(), "الخصومات")  # NEW!
        self.tabs.addTab(self._build_purchases_tab(), "المشتريات")  # NEW!
        self.tabs.addTab(self._build_profit_tab(), "الأرباح")
        self.tabs.addTab(self._build_price_log_tab(), "سجل الأسعار")
        self.tabs.addTab(self._build_inventory_tab(), "المخزون")
        self.tabs.addTab(self._build_attendance_tab(), "ساعات العمل")
        self.tabs.addTab(self._build_deductions_tab(), "خصومات الموظفين")
        self.tabs.addTab(self._build_stakeholder_tab(), "تقرير المساهمين")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(self.tabs)

        self._load_daily_report()
        self._load_cashier_report()
        self._load_product_report()
        self._load_discounts_report()  # NEW!
        self._load_purchases_report()  # NEW!
        self._load_profit_report()
        self._load_price_log()
        self._load_inventory_report()
        self._load_attendance_report()
        self._load_deductions_report()
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
        start_dt = QDateTime(QDate.currentDate().addDays(-6), QTime(0, 0, 0))
        self.daily_from = QDateTimeEdit(start_dt)
        self.daily_from.setCalendarPopup(True)
        self.daily_from.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.daily_from.setMinimumWidth(170)
        self.daily_from.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.daily_from)

        controls.addWidget(QLabel("إلى:"))
        end_dt = QDateTime(QDate.currentDate(), QTime(23, 59, 59))
        self.daily_to = QDateTimeEdit(end_dt)
        self.daily_to.setCalendarPopup(True)
        self.daily_to.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.daily_to.setMinimumWidth(170)
        self.daily_to.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.daily_to)

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
        start, end = self._datetime_bounds(self.daily_from, self.daily_to)
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

        controls.addWidget(QLabel("إلى:"))
        self.cashier_to = QDateEdit(QDate.currentDate())
        self.cashier_to.setCalendarPopup(True)
        self.cashier_to.setMinimumWidth(150)
        self.cashier_to.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.cashier_to)

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
        start, end = self._date_bounds(self.cashier_from, self.cashier_to)
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

        self.products_table = self._make_table([
            "المنتج", "الكمية", "إجمالي المبيعات"
        ])
        layout.addWidget(self.products_table, 1)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("من:"))
        self.products_from = QDateEdit(QDate.currentDate().addDays(-14))
        self.products_from.setCalendarPopup(True)
        controls.addWidget(self.products_from)

        controls.addWidget(QLabel("إلى:"))
        self.products_to = QDateEdit(QDate.currentDate())
        self.products_to.setCalendarPopup(True)
        controls.addWidget(self.products_to)

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
        start, end = self._date_bounds(self.products_from, self.products_to)
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

        controls.addWidget(QLabel("إلى:"))
        self.discounts_to = QDateEdit(QDate.currentDate())
        self.discounts_to.setCalendarPopup(True)
        self.discounts_to.setMinimumWidth(150)
        controls.addWidget(self.discounts_to)

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
        start, end = self._date_bounds(self.discounts_from, self.discounts_to)
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

        controls.addWidget(QLabel("إلى:"))
        self.purchases_to = QDateEdit(QDate.currentDate())
        self.purchases_to.setCalendarPopup(True)
        self.purchases_to.setMinimumWidth(150)
        controls.addWidget(self.purchases_to)

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
        start, end = self._date_bounds(self.purchases_from, self.purchases_to)
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
        widget = QWidget()
        layout = QVBoxLayout(widget)

        daily_title = QLabel("الربح اليومي")
        daily_title.setAlignment(Qt.AlignmentFlag.AlignRight)
        daily_title.setStyleSheet("font-weight:600;")
        layout.addWidget(daily_title)

        self.profit_daily_table = self._make_table([
            "التاريخ",
            "صافي المبيعات",
            "المشتريات",
            "صافي الربح",
        ])
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

        controls.addWidget(QLabel("إلى:"))
        self.profit_to = QDateEdit(QDate.currentDate())
        self.profit_to.setCalendarPopup(True)
        self.profit_to.setMinimumWidth(150)
        self.profit_to.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        controls.addWidget(self.profit_to)

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

        self.profit_monthly_table = self._make_table([
            "الشهر",
            "صافي المبيعات",
            "المشتريات",
            "صافي الربح",
        ])
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

        return widget

    def _load_profit_report(self):
        start, end = self._date_bounds(self.profit_from, self.profit_to)
        conn = get_conn()
        cur = conn.cursor()

        daily_query = """
            WITH sales AS (
                SELECT DATE(p.paid_at) AS day,
                       SUM(p.amount_cents) AS net_total
                FROM payments p
                WHERE p.paid_at BETWEEN ? AND ?
                GROUP BY day
            ),
            purchase_totals AS (
                SELECT DATE(pr.purchased_at) AS day,
                       SUM(pr.amount_cents) AS purchase_total
                FROM purchases pr
                WHERE pr.purchased_at BETWEEN ? AND ?
                GROUP BY day
            ),
            days AS (
                SELECT day FROM sales
                UNION
                SELECT day FROM purchase_totals
            )
            SELECT
                d.day AS day,
                COALESCE(sales.net_total, 0) AS net_sales,
                COALESCE(purchase_totals.purchase_total, 0) AS purchases_total
            FROM days d
            LEFT JOIN sales ON sales.day = d.day
            LEFT JOIN purchase_totals ON purchase_totals.day = d.day
            ORDER BY d.day DESC
        """

        cur.execute(daily_query, (start, end, start, end))
        daily_rows = cur.fetchall()

        monthly_query = """
            WITH sales AS (
                SELECT strftime('%Y-%m', p.paid_at) AS month,
                       SUM(p.amount_cents) AS net_total
                FROM payments p
                WHERE p.paid_at BETWEEN ? AND ?
                GROUP BY month
            ),
            purchase_totals AS (
                SELECT strftime('%Y-%m', pr.purchased_at) AS month,
                       SUM(pr.amount_cents) AS purchase_total
                FROM purchases pr
                WHERE pr.purchased_at BETWEEN ? AND ?
                GROUP BY month
            ),
            months AS (
                SELECT month FROM sales
                UNION
                SELECT month FROM purchase_totals
            )
            SELECT
                m.month AS month,
                COALESCE(sales.net_total, 0) AS net_sales,
                COALESCE(purchase_totals.purchase_total, 0) AS purchases_total
            FROM months m
            LEFT JOIN sales ON sales.month = m.month
            LEFT JOIN purchase_totals ON purchase_totals.month = m.month
            WHERE m.month IS NOT NULL
            ORDER BY m.month DESC
        """

        cur.execute(monthly_query, (start, end, start, end))
        monthly_rows = cur.fetchall()
        conn.close()

        daily_display = []
        daily_totals = {"sales": 0, "purchases": 0, "profit": 0}
        for row in daily_rows:
            day = row["day"] or ""
            sales_total = int(row["net_sales"] or 0)
            purchase_total = int(row["purchases_total"] or 0)
            profit = sales_total - purchase_total
            daily_display.append([
                day,
                self._money(sales_total),
                self._money(purchase_total),
                self._money(profit),
            ])
            daily_totals["sales"] += sales_total
            daily_totals["purchases"] += purchase_total
            daily_totals["profit"] += profit

        self._populate_table(self.profit_daily_table, daily_display)
        self.profit_daily_summary.setText(
            f"صافي المبيعات: {self._money(daily_totals['sales'])} | "
            f"إجمالي المشتريات: {self._money(daily_totals['purchases'])} | "
            f"صافي الربح: {self._money(daily_totals['profit'])}"
        )

        monthly_display = []
        monthly_totals = {"sales": 0, "purchases": 0, "profit": 0}
        for row in monthly_rows:
            month = row["month"] or ""
            sales_total = int(row["net_sales"] or 0)
            purchase_total = int(row["purchases_total"] or 0)
            profit = sales_total - purchase_total
            monthly_display.append([
                month,
                self._money(sales_total),
                self._money(purchase_total),
                self._money(profit),
            ])
            monthly_totals["sales"] += sales_total
            monthly_totals["purchases"] += purchase_total
            monthly_totals["profit"] += profit

        self._populate_table(self.profit_monthly_table, monthly_display)
        self.profit_monthly_summary.setText(
            f"صافي المبيعات: {self._money(monthly_totals['sales'])} | "
            f"إجمالي المشتريات: {self._money(monthly_totals['purchases'])} | "
            f"صافي الربح: {self._money(monthly_totals['profit'])}"
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
        cur.execute("""
            SELECT ts, username, entity_name, old_value, new_value, extra
            FROM audit_log WHERE action='price_change'
            ORDER BY id DESC LIMIT 200
        """)
        rows = cur.fetchall()
        conn.close()
        rows_list = [[r["ts"], r["username"], r["entity_name"], r["old_value"], r["new_value"], r["extra"]] for r in
                     rows]
        self._populate_table(self.price_table, rows_list)

    # -------------------------------------------------------------- inventory
    def _build_inventory_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.inventory_table = self._make_table(["المنتج", "المتاح", "الحد الأدنى"])
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
        entries = order_manager.catalog.get_low_stock()
        rows = [[n, self._format_qty(q or 0), self._format_qty(m or 0)] for n, q, m in entries]
        self._populate_table(self.inventory_table, rows)

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

        controls.addWidget(QLabel("إلى:"))
        self.attendance_to = QDateEdit(QDate.currentDate())
        self.attendance_to.setCalendarPopup(True)
        self.attendance_to.setMinimumWidth(150)
        controls.addWidget(self.attendance_to)

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
        start, end = self._date_bounds(self.attendance_from, self.attendance_to)
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
            username = row.get("username", "")
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
        self.stakeholder_from.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.stakeholder_from.setCalendarPopup(True)
        controls.addWidget(self.stakeholder_from)

        controls.addWidget(QLabel("إلى:"))
        self.stakeholder_to = QDateTimeEdit(QDateTime.currentDateTime())
        self.stakeholder_to.setDisplayFormat("yyyy-MM-dd HH:mm")
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
        cur.execute("""
            SELECT ts, username, action, entity_type, entity_name, old_value, new_value, extra
            FROM audit_log WHERE ts BETWEEN ? AND ? ORDER BY ts
        """, (start, end))
        rows = cur.fetchall()
        conn.close()

        table_rows = [
            [r["ts"], r["username"], r["action"], r["entity_type"], r["entity_name"], r["old_value"], r["new_value"],
             r["extra"]] for r in rows]
        self._populate_table(self.stakeholder_table, table_rows)
        self.stakeholder_summary.setText(f"عدد الأحداث: {len(table_rows)}")

    # ------------------------------------------------------------- utilities
    def _make_export_button(self, table: QTableWidget, default_name: str) -> QPushButton:
        button = QPushButton("تنزيل Excel")
        button.clicked.connect(lambda _, t=table, n=default_name: self._export_table(t, n))
        return button

    def _make_table(self, headers: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def _populate_table(self, table: QTableWidget, rows: list[list[str]]):
        table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                item = QTableWidgetItem(str(value or ""))
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r, c, item)
        if not rows:
            table.setRowCount(0)

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

    def _export_table(self, table: QTableWidget, default_name: str) -> None:
        """Export table to Excel with timestamped filename."""
        # Generate filename with current date and time
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
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
            from ..utils.excel import write_protected_workbook
            write_protected_workbook(path, headers, rows, title=default_name)
        except Exception as exc:
            QMessageBox.critical(self, "فشل التصدير", f"تعذر إنشاء ملف Excel:\n{exc}")
            return

        QMessageBox.information(
            self,
            "تم التصدير",
            "تم إنشاء ملف Excel محمي من التعديل بنجاح."
        )