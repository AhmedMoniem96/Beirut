# table_history_dialog.py
from __future__ import annotations

import csv
from datetime import datetime, timezone
from typing import Any

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QBrush, QColor, QPalette
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QDialogButtonBox,
)

from ..common.big_dialog import BigDialog
from ...core.db import get_conn
from ...services import texts
from ...services.orders import get_table_history
from ...utils.currency import format_pounds


DIALOG_BG_COLOR = "#1e1410"
DIALOG_TEXT_COLOR = "#eeeeee"
DIALOG_HIGHLIGHT_BG = "#5a402f"
DIALOG_HIGHLIGHT_TEXT = "#ffffff"


def _date_to_start(dt: QDate) -> str:
    return f"{dt.toString('yyyy-MM-dd')}T00:00:00"


def _date_to_end(dt: QDate) -> str:
    return f"{dt.toString('yyyy-MM-dd')}T23:59:59"


class TableHistoryDialog(BigDialog):
    def __init__(self, table_code: str, parent=None):
        title = texts.get(
            "tables.history.title",
            default=f"سجل الطلبات للطاولة {table_code}",
            table_code=table_code,
        )
        super().__init__(title, remember_key="table_history", parent=parent)
        self.table_code = table_code
        self._offset = 0
        self._rows: list[dict[str, Any]] = []
        self._has_more = False

        root = QVBoxLayout(self)

        filters = QHBoxLayout()
        filters.setSpacing(8)

        from_label = QLabel(texts.get("tables.history.from", default="من تاريخ"))
        filters.addWidget(from_label)

        self.from_date = QDateEdit()
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        self.from_date.setCalendarPopup(True)
        self.from_date.setDate(QDate.currentDate().addDays(-30))
        filters.addWidget(self.from_date)

        to_label = QLabel(texts.get("tables.history.to", default="إلى تاريخ"))
        filters.addWidget(to_label)

        self.to_date = QDateEdit()
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        self.to_date.setCalendarPopup(True)
        self.to_date.setDate(QDate.currentDate())
        filters.addWidget(self.to_date)

        search_label = QLabel(texts.get("tables.history.search_label", default="بحث"))
        filters.addWidget(search_label)

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            texts.get(
                "tables.history.search_placeholder",
                default="رقم الطلب، اسم الكاشير، أو ملاحظة",
            )
        )
        self.search.returnPressed.connect(self._apply_filters)
        filters.addWidget(self.search, 1)

        self.apply_btn = QPushButton(texts.get("tables.history.apply", default="تطبيق"))
        self.apply_btn.clicked.connect(self._apply_filters)
        filters.addWidget(self.apply_btn)

        self.export_btn = QPushButton(texts.get("tables.history.export", default="تصدير"))
        self.export_btn.clicked.connect(self._export_csv)
        filters.addWidget(self.export_btn)

        root.addLayout(filters)

        self.table = QTableWidget(0, 8)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        headers = [
            texts.get("tables.history.headers.order_id", default="رقم الطلب"),
            texts.get("tables.history.headers.client_name", default="اسم العميل"),
            texts.get("tables.history.headers.opened_at", default="وقت الفتح"),
            texts.get("tables.history.headers.paid_at", default="وقت الدفع"),
            texts.get("tables.history.headers.total", default="الإجمالي"),
            texts.get("tables.history.headers.discount", default="الخصم"),
            texts.get("tables.history.headers.cashier", default="الكاشير"),
            texts.get("tables.history.headers.items_count", default="عدد العناصر"),
        ]
        self.table.setHorizontalHeaderLabels(headers)
        self.table.cellDoubleClicked.connect(self._open_detail)
        root.addWidget(self.table, 1)

        self.empty_label = QLabel(texts.get("tables.history.no_results"))
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        root.addWidget(self.empty_label)

        pager = QHBoxLayout()
        pager.setSpacing(8)

        self.prev_btn = QPushButton(texts.get("tables.history.pagination.prev", default="السابق"))
        self.prev_btn.clicked.connect(self._prev_page)
        pager.addWidget(self.prev_btn)

        self.next_btn = QPushButton(texts.get("tables.history.pagination.next", default="التالي"))
        self.next_btn.clicked.connect(self._next_page)
        pager.addWidget(self.next_btn)

        pager.addStretch(1)

        size_label = QLabel(texts.get("tables.history.page_size", default="عدد النتائج"))
        pager.addWidget(size_label)

        self.page_size = QSpinBox()
        self.page_size.setRange(10, 200)
        self.page_size.setSingleStep(5)
        self.page_size.setValue(25)
        self.page_size.valueChanged.connect(self._on_page_size_changed)
        pager.addWidget(self.page_size)

        self.page_label = QLabel()
        pager.addWidget(self.page_label)

        root.addLayout(pager)

        self._apply_filters()

    def _current_page_size(self) -> int:
        return int(self.page_size.value())

    def _apply_filters(self) -> None:
        self._offset = 0
        self._refresh()

    def _on_page_size_changed(self, _value: int) -> None:
        self._offset = 0
        self._refresh()

    def _prev_page(self) -> None:
        step = self._current_page_size()
        if self._offset <= 0:
            return
        self._offset = max(0, self._offset - step)
        self._refresh()

    def _next_page(self) -> None:
        if not self._has_more:
            return
        self._offset += self._current_page_size()
        self._refresh()

    def _refresh(self) -> None:
        from_date = _date_to_start(self.from_date.date()) if self.from_date.date().isValid() else None
        to_date = _date_to_end(self.to_date.date()) if self.to_date.date().isValid() else None
        query = self.search.text().strip() or None
        page_size = self._current_page_size()

        conn = get_conn()
        try:
            rows = get_table_history(
                conn,
                self.table_code,
                date_from=from_date,
                date_to=to_date,
                q=query,
                limit=page_size + 1,
                offset=self._offset,
            )
        finally:
            conn.close()

        self._has_more = len(rows) > page_size
        if self._has_more:
            rows = rows[:page_size]
        self._rows = rows

        self.table.setRowCount(len(rows))
        for row_idx, data in enumerate(rows):
            # data from get_table_history is dict-like; use .get for safety
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(data.get("order_id"))))
            client_cell = (data.get("client_name") or "").strip()
            self.table.setItem(row_idx, 1, QTableWidgetItem(client_cell))
            self.table.setItem(row_idx, 2, QTableWidgetItem(data.get("opened_at") or ""))
            paid_display = data.get("paid_at") or data.get("closed_at") or ""
            self.table.setItem(row_idx, 3, QTableWidgetItem(paid_display))
            self.table.setItem(row_idx, 4, QTableWidgetItem(format_pounds(data.get("total_cents", 0))))
            self.table.setItem(row_idx, 5, QTableWidgetItem(format_pounds(data.get("discount_cents", 0))))
            self.table.setItem(row_idx, 6, QTableWidgetItem(data.get("cashier") or ""))
            items_count_raw = data.get("items_count", 0)
            try:
                items_count = float(items_count_raw)
            except (TypeError, ValueError):
                items_count = 0.0
            if abs(items_count - round(items_count)) < 1e-6:
                items_str = str(int(round(items_count)))
            else:
                items_str = f"{items_count:g}"
            self.table.setItem(row_idx, 7, QTableWidgetItem(items_str))

        self.table.setVisible(bool(rows))
        self.empty_label.setVisible(not rows)
        self.prev_btn.setEnabled(self._offset > 0)
        self.next_btn.setEnabled(self._has_more)

        page_number = (self._offset // page_size) + 1
        self.page_label.setText(
            texts.get("tables.history.pagination.page", default=f"الصفحة {page_number}", page=page_number)
        )

    def _open_detail(self, row: int, _column: int) -> None:
        if row < 0 or row >= len(self._rows):
            return
        order_id = self._rows[row]["order_id"]
        dlg = OrderDetailsDialog(order_id, parent=self)
        dlg.exec()
        # refresh the listing so totals / status reflect anything changed externally
        self._refresh()

    def _export_csv(self) -> None:
        if not self._rows:
            QMessageBox.information(
                self,
                texts.get("tables.history.export", default="تصدير"),
                texts.get("tables.history.export.empty", default="لا توجد بيانات لتصديرها."),
            )
            return

        default_name = texts.get(
            "tables.history.export_filename",
            default=f"table_history_{self.table_code}_{datetime.utcnow().date().isoformat()}.csv",
            table=self.table_code,
            date=datetime.utcnow().date().isoformat(),
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            texts.get("tables.history.export", default="تصدير"),
            default_name,
            "CSV Files (*.csv)",
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow([
                    texts.get("tables.history.headers.order_id", default="رقم الطلب"),
                    texts.get("tables.history.headers.client_name", default="اسم العميل"),
                    texts.get("tables.history.headers.opened_at", default="وقت الفتح"),
                    texts.get("tables.history.headers.paid_at", default="وقت الدفع"),
                    texts.get("tables.history.headers.total", default="الإجمالي"),
                    texts.get("tables.history.headers.discount", default="الخصم"),
                    texts.get("tables.history.headers.cashier", default="الكاشير"),
                    texts.get("tables.history.headers.items_count", default="عدد العناصر"),
                ])
                for row in self._rows:
                    items_count_raw = row.get("items_count", 0)
                    try:
                        items_count = float(items_count_raw)
                    except (TypeError, ValueError):
                        items_count = 0.0
                    if abs(items_count - round(items_count)) < 1e-6:
                        items_cell = int(round(items_count))
                    else:
                        items_cell = items_count
                    writer.writerow([
                        row.get("order_id"),
                        (row.get("client_name") or "").strip(),
                        row.get("opened_at", ""),
                        row.get("paid_at") or row.get("closed_at") or "",
                        format_pounds(row.get("total_cents", 0)),
                        format_pounds(row.get("discount_cents", 0)),
                        row.get("cashier", ""),
                        items_cell,
                    ])
        except Exception as exc:  # pragma: no cover - UI feedback only
            QMessageBox.critical(
                self,
                texts.get("tables.history.export", default="تصدير"),
                texts.get("tables.history.export.error", default="تعذر تصدير السجل: {error}", error=exc),
            )
            return

        QMessageBox.information(
            self,
            texts.get("tables.history.export", default="تصدير"),
            texts.get("tables.history.export.success", default="تم تصدير السجل بنجاح."),
        )


class OrderDetailsDialog(BigDialog):
    def __init__(self, order_id: int, parent=None):
        title = texts.get(
            "tables.history.details.title",
            default=f"تفاصيل الطلب #{order_id}",
            order_id=order_id,
        )
        super().__init__(title, remember_key="table_history_details", parent=parent)
        self.order_id = order_id

        root = QVBoxLayout(self)

        self.meta_grid = QGridLayout()
        self.meta_grid.setSpacing(8)
        self.meta_grid.setColumnStretch(1, 1)
        root.addLayout(self.meta_grid)

        self._meta_static_labels: list[QLabel] = []
        self._meta_value_labels: list[QLabel] = []

        def _add_row(row: int, label_key: str, default: str) -> QLabel:
            lab = QLabel(texts.get(label_key, default=default))
            lab.setStyleSheet(f"color: {DIALOG_TEXT_COLOR};")
            self._meta_static_labels.append(lab)
            value = QLabel("-")
            value.setWordWrap(True)
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setStyleSheet(f"color: {DIALOG_TEXT_COLOR};")
            self._meta_value_labels.append(value)
            self.meta_grid.addWidget(lab, row, 0)
            self.meta_grid.addWidget(value, row, 1)
            return value

        # Meta rows: explicitly include opened, closed, paid so times are unambiguous
        self.table_label = _add_row(0, "tables.history.details.table", "الطاولة")
        self.client_label = _add_row(1, "tables.history.details.client_name", "اسم العميل")
        self.opened_label = _add_row(2, "tables.history.details.opened_at", "وقت الفتح")
        self.closed_label = _add_row(3, "tables.history.details.closed_at", "وقت الإغلاق")
        self.paid_label = _add_row(4, "tables.history.details.paid_at", "وقت الدفع")
        self.cashier_label = _add_row(5, "tables.history.details.cashier", "الكاشير")
        self.subtotal_label = _add_row(6, "tables.history.details.subtotal", "الإجمالي قبل الخصم")
        self.discount_label = _add_row(7, "tables.history.details.discount", "الخصم")
        self.total_label = _add_row(8, "tables.history.details.total", "الإجمالي بعد الخصم")
        self.note_label = _add_row(9, "tables.history.details.discount_reason", "سبب الخصم")

        # helper to format ISO -> local nicely as Arabic-style: DD-MM-YYYY H:MM ص/م
        # assumes stored ISO is UTC when no tzinfo is present (project currently writes datetime.utcnow())
        def _fmt_dt(iso_str: str | None) -> str:
            if not iso_str:
                return ""
            try:
                dt = datetime.fromisoformat(str(iso_str))
            except Exception:
                return str(iso_str)
            # treat naive datetimes as UTC (project uses utcnow())
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            try:
                local = dt.astimezone()  # convert to local system tz
            except Exception:
                local = dt
            hour = local.hour
            minute = local.minute
            hour12 = hour % 12 or 12
            suffix = "ص" if hour < 12 else "م"
            return f"{local.day:02d}-{local.month:02d}-{local.year} {hour12}:{minute:02d} {suffix}"

        # attach helper to instance so _load can use it
        self._fmt_dt = _fmt_dt

        self.items_table = QTableWidget(0, 5)
        self.items_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.items_table.verticalHeader().setVisible(False)
        items_header = self.items_table.horizontalHeader()
        items_header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        items_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        items_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        items_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.items_table.setHorizontalHeaderLabels([
            texts.get("tables.history.details.items_header.product", default="الصنف"),
            texts.get("tables.history.details.items_header.qty", default="الكمية"),
            texts.get("tables.history.details.items_header.price", default="السعر"),
            texts.get("tables.history.details.items_header.total", default="الإجمالي"),
            texts.get("tables.history.details.items_header.note", default="ملاحظة"),
        ])
        root.addWidget(self.items_table, 1)

        self.payments_label = QLabel("")
        self.payments_label.setWordWrap(True)
        self.payments_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.payments_label.setStyleSheet(f"color: {DIALOG_TEXT_COLOR};")
        root.addWidget(self.payments_label)

        # buttons area: only Close (view-only)
        btns_layout = QHBoxLayout()
        btns_layout.addStretch(1)

        close_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_buttons.rejected.connect(self.reject)
        close_buttons.accepted.connect(self.accept)
        btns_layout.addWidget(close_buttons)

        root.addLayout(btns_layout)

        self._apply_dark_theme()

        self._load()

    def _load(self) -> None:
        conn = get_conn()
        try:
            cur = conn.cursor()
            # fetch order metadata and times
            order = cur.execute(
                """
                SELECT o.table_code,
                       COALESCE(NULLIF(o.client_name, ''), tc.client_name, '') AS client_name,
                       o.opened_at,
                       o.closed_at,
                       o.status,
                       o.paid_at,
                       o.discount_cents,
                       o.discount_reason,
                       o.opened_by
                FROM orders o
                LEFT JOIN table_clients tc ON tc.table_code = UPPER(o.table_code)
                WHERE o.id=?
                """,
                (self.order_id,),
            ).fetchone()
            if not order:
                QMessageBox.warning(
                    self,
                    self.windowTitle(),
                    texts.get(
                        "tables.history.details.missing",
                        default="تعذر تحميل تفاصيل الطلب المحدد.",
                    ),
                )
                self.reject()
                return

            items = cur.execute(
                """
                SELECT product_name, qty, price_cents, COALESCE(note, '') AS note
                FROM order_items
                WHERE order_id=?
                ORDER BY id
                """,
                (self.order_id,),
            ).fetchall()

            payments = cur.execute(
                """
                SELECT method, amount_cents, paid_at, cashier
                FROM payments
                WHERE order_id=?
                ORDER BY paid_at
                """,
                (self.order_id,),
            ).fetchall()
        finally:
            conn.close()

        # compute totals
        subtotal = 0
        for it in items:
            price = int(it["price_cents"] or 0)
            qty = float(it["qty"] or 0)
            subtotal += int(round(price * qty))

        discount = int(order["discount_cents"] or 0)
        total = max(subtotal - discount, 0)

        # --- set meta fields (use sqlite3.Row indexing) ---
        table_code = order["table_code"] if "table_code" in order.keys() else ""
        client_name = (order["client_name"] if "client_name" in order.keys() else "") or ""
        self.table_label.setText(table_code or "")
        self.client_label.setText(client_name.strip() or "-")
        self.opened_label.setText(self._fmt_dt(order["opened_at"] if "opened_at" in order.keys() else None))
        self.closed_label.setText(self._fmt_dt(order["closed_at"] if "closed_at" in order.keys() else None))

        # paid_at: prefer last payment timestamp when available, otherwise fall back to closed_at
        if payments:
            paid_at_raw = payments[-1]["paid_at"] if "paid_at" in payments[-1].keys() else payments[-1]["paid_at"]
        else:
            paid_at_raw = order["closed_at"] if "closed_at" in order.keys() else None
        self.paid_label.setText(self._fmt_dt(paid_at_raw))

        cashiers = ", ".join(sorted({p["cashier"] for p in payments if p["cashier"]}))
        self.cashier_label.setText(cashiers or "-")
        self.subtotal_label.setText(format_pounds(subtotal))
        self.discount_label.setText(format_pounds(discount))
        self.total_label.setText(format_pounds(total))

        note = (order["discount_reason"] if "discount_reason" in order.keys() else "").strip()
        self.note_label.setText(note or "-")

        # ensure table cleared then populate
        self.items_table.clearContents()
        self.items_table.setRowCount(len(items))
        for idx, it in enumerate(items):
            self.items_table.setItem(idx, 0, self._make_table_item(it["product_name"]))
            qty = float(it["qty"] or 0)
            qty_str = str(int(qty)) if qty.is_integer() else f"{qty:g}"
            self.items_table.setItem(
                idx,
                1,
                self._make_table_item(qty_str, Qt.AlignmentFlag.AlignCenter),
            )
            price = int(it["price_cents"] or 0)
            self.items_table.setItem(
                idx,
                2,
                self._make_table_item(
                    format_pounds(price),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
            )
            line_total = int(round(price * qty))
            self.items_table.setItem(
                idx,
                3,
                self._make_table_item(
                    format_pounds(line_total),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                ),
            )
            self.items_table.setItem(idx, 4, self._make_table_item(it["note"] or ""))

        self.items_table.viewport().update()

        # payments: format times robustly
        prefix = texts.get("tables.history.details.payments", default="المدفوعات")
        if payments:
            parts = []
            for pay in payments:
                try:
                    paid_at_raw = pay["paid_at"] if "paid_at" in pay.keys() else None
                except Exception:
                    paid_at_raw = None
                pay_time = self._fmt_dt(paid_at_raw)
                method = pay["method"] if "method" in pay.keys() else ""
                amount_cents = int(pay["amount_cents"] or 0) if "amount_cents" in pay.keys() else int(pay[1] or 0)
                parts.append(
                    texts.get(
                        "tables.history.details.payments_entry",
                        default=f"{method} — {format_pounds(amount_cents)} في {pay_time}",
                        method=method,
                        amount=format_pounds(amount_cents),
                        time=pay_time,
                    )
                )
            payments_text = "\n".join(parts)
        else:
            payments_text = texts.get("tables.history.details.no_payments", default="لا يوجد مدفوعات مسجلة.")

        self.payments_label.setText(f"{prefix}:\n{payments_text}")

    def _apply_dark_theme(self) -> None:
        bg = QColor(DIALOG_BG_COLOR)
        text = QColor(DIALOG_TEXT_COLOR)
        highlight = QColor(DIALOG_HIGHLIGHT_BG)
        highlight_text = QColor(DIALOG_HIGHLIGHT_TEXT)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, bg)
        palette.setColor(QPalette.ColorRole.WindowText, text)
        palette.setColor(QPalette.ColorRole.Base, bg)
        palette.setColor(QPalette.ColorRole.Text, text)
        palette.setColor(QPalette.ColorRole.ButtonText, text)
        palette.setColor(QPalette.ColorRole.Highlight, highlight)
        palette.setColor(QPalette.ColorRole.HighlightedText, highlight_text)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        table_palette = self.items_table.palette()
        table_palette.setColor(QPalette.ColorRole.Window, bg)
        table_palette.setColor(QPalette.ColorRole.Base, bg)
        table_palette.setColor(QPalette.ColorRole.AlternateBase, bg)
        table_palette.setColor(QPalette.ColorRole.Text, text)
        table_palette.setColor(QPalette.ColorRole.Highlight, highlight)
        table_palette.setColor(QPalette.ColorRole.HighlightedText, highlight_text)
        self.items_table.setPalette(table_palette)

        table_stylesheet = (
            "QTableWidget {"
            f"background-color: {DIALOG_BG_COLOR};"
            f"color: {DIALOG_TEXT_COLOR};"
            f"gridline-color: {DIALOG_HIGHLIGHT_BG};"
            "}"
            f"QTableWidget::item:selected {{ background-color: {DIALOG_HIGHLIGHT_BG}; color: {DIALOG_HIGHLIGHT_TEXT}; }}"
            f"QHeaderView::section {{ background-color: {DIALOG_BG_COLOR}; color: {DIALOG_TEXT_COLOR}; }}"
            f"QTableCornerButton::section {{ background-color: {DIALOG_BG_COLOR}; }}"
        )
        self.items_table.setStyleSheet(table_stylesheet)

        for label in [*self._meta_static_labels, *self._meta_value_labels, self.payments_label]:
            label.setStyleSheet(f"color: {DIALOG_TEXT_COLOR};")

    def _make_table_item(
        self,
        text: str,
        alignment: Qt.Alignment | None = None,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setForeground(QBrush(QColor(DIALOG_TEXT_COLOR)))
        if alignment is not None:
            item.setTextAlignment(int(alignment))
        return item
