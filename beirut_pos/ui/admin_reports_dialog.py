from datetime import datetime

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QComboBox,
)

from ..core.db import get_conn, setting_get
from .common.big_dialog import BigDialog
from ..services.orders import order_manager


class AdminReportsDialog(BigDialog):
    """Dashboard of operational reports for managers."""

    def __init__(self):
        super().__init__("التقارير الإدارية", remember_key="reports", parent=None)
        self.currency = setting_get("currency", "EGP") or "EGP"

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_daily_tab(), "ملخص يومي")
        self.tabs.addTab(self._build_cashier_tab(), "حسب الكاشير")
        self.tabs.addTab(self._build_products_tab(), "الأصناف")
        self.tabs.addTab(self._build_price_log_tab(), "سجل الأسعار")
        self.tabs.addTab(self._build_inventory_tab(), "المخزون")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self._load_daily_report()
        self._load_cashier_report()
        self._load_product_report()
        self._load_price_log()
        self._load_inventory_report()

    # ------------------------------------------------------------------ daily
    def _build_daily_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("من:"))
        self.daily_from = QDateEdit()
        self.daily_from.setCalendarPopup(True)
        self.daily_from.setDate(QDate.currentDate().addDays(-6))
        controls.addWidget(self.daily_from)

        controls.addWidget(QLabel("إلى:"))
        self.daily_to = QDateEdit()
        self.daily_to.setCalendarPopup(True)
        self.daily_to.setDate(QDate.currentDate())
        controls.addWidget(self.daily_to)

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_daily_report)
        controls.addWidget(refresh)
        controls.addStretch(1)
        layout.addLayout(controls)

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

        self.daily_summary = QLabel("")
        self.daily_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.daily_summary)

        return widget

    def _load_daily_report(self):
        start, end = self._date_bounds(self.daily_from, self.daily_to)
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
        totals = {
            "orders": 0,
            "items": 0.0,
            "gross": 0,
            "net": 0,
            "cash": 0,
            "card": 0,
        }
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

        controls = QHBoxLayout()
        controls.addWidget(QLabel("من:"))
        self.cashier_from = QDateEdit()
        self.cashier_from.setCalendarPopup(True)
        self.cashier_from.setDate(QDate.currentDate().addDays(-6))
        controls.addWidget(self.cashier_from)

        controls.addWidget(QLabel("إلى:"))
        self.cashier_to = QDateEdit()
        self.cashier_to.setCalendarPopup(True)
        self.cashier_to.setDate(QDate.currentDate())
        controls.addWidget(self.cashier_to)

        controls.addWidget(QLabel("الكاشير:"))
        self.cashier_filter = QComboBox()
        self.cashier_filter.addItem("الكل", "")
        self._populate_cashier_filter()
        controls.addWidget(self.cashier_filter)

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_cashier_report)
        controls.addWidget(refresh)
        controls.addStretch(1)
        layout.addLayout(controls)

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

        self.cashier_summary = QLabel("")
        self.cashier_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.cashier_summary)

        return widget

    def _populate_cashier_filter(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT cashier FROM payments ORDER BY cashier")
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
        totals = {
            "orders": 0,
            "gross": 0,
            "net": 0,
            "cash": 0,
            "card": 0,
        }
        for row in rows:
            gross = int(row["gross_total"] or 0)
            net = int(row["net_total"] or 0)
            cash_total = int(row["cash_total"] or 0)
            card_total = int(row["card_total"] or 0)
            orders_count = int(row["orders_count"] or 0)
            avg_order = net / orders_count if orders_count else 0
            cashier_name = row["cashier"] or "غير محدد"
            table_rows.append(
                [
                    cashier_name,
                    str(orders_count),
                    self._money(gross),
                    self._money(net),
                    self._money(cash_total),
                    self._money(card_total),
                    self._money(int(avg_order)),
                ]
            )
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

        controls = QHBoxLayout()
        controls.addWidget(QLabel("من:"))
        self.products_from = QDateEdit()
        self.products_from.setCalendarPopup(True)
        self.products_from.setDate(QDate.currentDate().addDays(-14))
        controls.addWidget(self.products_from)

        controls.addWidget(QLabel("إلى:"))
        self.products_to = QDateEdit()
        self.products_to.setCalendarPopup(True)
        self.products_to.setDate(QDate.currentDate())
        controls.addWidget(self.products_to)

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_product_report)
        controls.addWidget(refresh)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.products_table = self._make_table([
            "المنتج",
            "الكمية",
            "إجمالي المبيعات",
        ])
        layout.addWidget(self.products_table, 1)

        self.products_summary = QLabel("")
        self.products_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.products_summary)

        return widget

    def _load_product_report(self):
        start, end = self._date_bounds(self.products_from, self.products_to)
        query = """
            WITH paid_orders AS (
                SELECT DISTINCT order_id
                FROM payments
                WHERE paid_at BETWEEN ? AND ?
            )
            SELECT
                oi.product_name AS product,
                SUM(oi.qty) AS qty,
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

        table_rows = []
        total_qty = 0.0
        total_sales = 0
        for row in rows:
            qty = float(row["qty"] or 0)
            total = int(row["total"] or 0)
            table_rows.append([
                row["product"],
                self._format_qty(qty),
                self._money(total),
            ])
            total_qty += qty
            total_sales += total

        self._populate_table(self.products_table, table_rows)
        summary = (
            f"عدد الأصناف: {len(table_rows)} | "
            f"إجمالي الكمية: {self._format_qty(total_qty)} | "
            f"إجمالي المبيعات: {self._money(total_sales)}"
        )
        self.products_summary.setText(summary)

    # ------------------------------------------------------------- price log
    def _build_price_log_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.price_table = self._make_table([
            "الوقت",
            "المستخدم",
            "العنصر",
            "السعر القديم",
            "السعر الجديد",
            "تفاصيل",
        ])
        layout.addWidget(self.price_table, 1)

        refresh = QPushButton("تحديث السجل")
        refresh.clicked.connect(self._load_price_log)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)

        return widget

    def _load_price_log(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT ts, username, entity_name, old_value, new_value, extra
            FROM audit_log
            WHERE action='price_change'
            ORDER BY id DESC
            LIMIT 200
            """
        )
        rows = cur.fetchall()
        conn.close()

        table_rows = []
        for row in rows:
            table_rows.append([
                row["ts"],
                row["username"],
                row["entity_name"] or "",
                row["old_value"] or "",
                row["new_value"] or "",
                row["extra"] or "",
            ])
        self._populate_table(self.price_table, table_rows)

    # -------------------------------------------------------------- inventory
    def _build_inventory_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        intro = QLabel("الأصناف التي وصلت أو تجاوزت حد التنبيه للمخزون.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.inventory_table = self._make_table([
            "المنتج",
            "المتاح",
            "الحد الأدنى",
        ])
        layout.addWidget(self.inventory_table, 1)

        refresh = QPushButton("تحديث")
        refresh.clicked.connect(self._load_inventory_report)
        layout.addWidget(refresh, alignment=Qt.AlignmentFlag.AlignLeft)

        return widget

    def _load_inventory_report(self):
        entries = order_manager.catalog.get_low_stock()
        table_rows = []
        for name, qty, min_qty in entries:
            table_rows.append([
                name,
                self._format_qty(qty if qty is not None else 0),
                self._format_qty(min_qty if min_qty is not None else 0),
            ])
        self._populate_table(self.inventory_table, table_rows)

    # ------------------------------------------------------------- utilities
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
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(r, c, item)
        if not rows:
            table.setRowCount(0)

    def _money(self, cents: int) -> str:
        return f"{cents/100:,.2f} {self.currency}"

    def _format_qty(self, qty) -> str:
        try:
            q = float(qty)
        except (TypeError, ValueError):
            return "0"
        if abs(q - round(q)) < 1e-6:
            return str(int(round(q)))
        return f"{q:.2f}"

    def _date_bounds(self, start_widget: QDateEdit, end_widget: QDateEdit) -> tuple[str, str]:
        start_date = start_widget.date().toPyDate()
        end_date = end_widget.date().toPyDate()
        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())
        return start.isoformat(), end.isoformat()
