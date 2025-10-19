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
)

from ..core.db import get_conn, setting_get
from .common.big_dialog import BigDialog
from ..services.orders import order_manager
from ..utils.currency import format_pounds
from ..utils.excel import write_protected_workbook


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
        self.tabs.addTab(self._build_stakeholder_tab(), "تقرير المساهمين")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self._load_daily_report()
        self._load_cashier_report()
        self._load_product_report()
        self._load_price_log()
        self._load_inventory_report()
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
        controls.addWidget(QLabel("من:"))
        self.daily_from = QDateEdit(QDate.currentDate().addDays(-6))
        self.daily_from.setCalendarPopup(True)
        controls.addWidget(self.daily_from)

        controls.addWidget(QLabel("إلى:"))
        self.daily_to = QDateEdit(QDate.currentDate())
        self.daily_to.setCalendarPopup(True)
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
        controls.addWidget(QLabel("من:"))
        self.cashier_from = QDateEdit(QDate.currentDate().addDays(-6))
        self.cashier_from.setCalendarPopup(True)
        controls.addWidget(self.cashier_from)

        controls.addWidget(QLabel("إلى:"))
        self.cashier_to = QDateEdit(QDate.currentDate())
        self.cashier_to.setCalendarPopup(True)
        controls.addWidget(self.cashier_to)

        controls.addWidget(QLabel("الكاشير:"))
        self.cashier_filter = QComboBox()
        self.cashier_filter.addItem("الكل", "")
        self._populate_cashier_filter()
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
        rows_list = [[r["ts"], r["username"], r["entity_name"], r["old_value"], r["new_value"], r["extra"]] for r in rows]
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

        table_rows = [[r["ts"], r["username"], r["action"], r["entity_type"], r["entity_name"], r["old_value"], r["new_value"], r["extra"]] for r in rows]
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
        path, _ = QFileDialog.getSaveFileName(self, "تصدير التقرير", f"{default_name}.xlsx", "Excel (*.xlsx)")
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
            write_protected_workbook(path, headers, rows, title=default_name)
        except Exception as exc:
            QMessageBox.critical(self, "فشل التصدير", f"تعذر إنشاء ملف Excel:\n{exc}")
            return

        QMessageBox.information(self, "تم التصدير", "تم إنشاء ملف Excel محمي من التعديل.")
