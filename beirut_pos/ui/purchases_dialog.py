# beirut_pos/ui/purchases_dialog.py
from __future__ import annotations

from PyQt6.QtCore import Qt, QDateTime
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDateTimeEdit,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QStackedLayout,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from .common.big_dialog import BigDialog
from .theme.components import DSTable, KpiCard, DSButton, DSSelect, DSTextField
from ..services import purchases
from ..utils.currency import format_pounds


class PurchasesDialog(BigDialog):
    def __init__(self, actor: str, parent=None):
        super().__init__("المشتريات", remember_key="purchases", parent=parent)
        self._actor = actor

        root = QVBoxLayout(self)

        intro = QLabel(
            "سجّل كل مشتريات المخزون هنا لتبقى حساباتك دقيقة وتتبع المصروفات بسهولة."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.cards_row = QHBoxLayout()
        self.cards_row.setContentsMargins(0, 0, 0, 0)
        self.cards_row.setSpacing(12)
        self.total_card = KpiCard("💰", "إجمالي الإنفاق", "—")
        self.avg_card = KpiCard("📊", "متوسط العملية", "—")
        self.count_card = KpiCard("🧾", "عدد المشتريات", "—")
        for card in (self.total_card, self.avg_card, self.count_card):
            self.cards_row.addWidget(card)
        self.cards_row.addStretch(1)
        root.addLayout(self.cards_row)

        self.filter_bar = QHBoxLayout()
        self.filter_bar.setSpacing(8)
        self.filter_bar.setContentsMargins(0, 0, 0, 0)
        self.filter_supplier = DSTextField("بحث باسم المورد")
        self.filter_invoice = DSTextField("رقم الفاتورة")
        self.filter_min_amount = DSTextField("حد أدنى للمبلغ")
        for field in (self.filter_supplier, self.filter_invoice, self.filter_min_amount):
            field.setFixedWidth(180)
            self.filter_bar.addWidget(field)

        self.views = DSSelect()
        self.views.addItems(["كل العمليات", "آخر 7 أيام", "هذا الشهر", "مشتريات كبيرة (>500)"])
        self.filter_bar.addWidget(self.views)

        self.btn_apply_filters = DSButton("تطبيق الفلاتر", variant="secondary")
        self.btn_apply_filters.clicked.connect(self._apply_filters)
        self.btn_clear_filters = DSButton("إعادة التعيين", variant="link")
        self.btn_clear_filters.clicked.connect(self._clear_filters)
        self.filter_bar.addWidget(self.btn_apply_filters)
        self.filter_bar.addWidget(self.btn_clear_filters)
        self.filter_bar.addStretch(1)
        root.addLayout(self.filter_bar)

        self.table = DSTable(0, 6)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.set_headers([
            "التاريخ",
            "المورد",
            "رقم الفاتورة",
            "المبلغ",
            "ملاحظات",
            "أضيف بواسطة",
        ])
        self.table.set_column_alignments(
            [
                Qt.AlignmentFlag.AlignCenter,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                Qt.AlignmentFlag.AlignCenter,
                Qt.AlignmentFlag.AlignCenter,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                Qt.AlignmentFlag.AlignCenter,
            ]
        )

        self._table_stack = QStackedLayout()
        self._table_stack.setContentsMargins(0, 0, 0, 0)
        self._table_stack.addWidget(self.table)

        self.empty_state = self._build_state(
            "لا توجد عمليات شراء بعد.", "أضف أول عملية", self._focus_form
        )
        self.loading_state = self._build_state("يتم التحميل…", None, None)
        self.error_state = self._build_state(
            "تعذر تحميل المشتريات.", "إعادة المحاولة", self._refresh
        )
        self._table_stack.addWidget(self.empty_state)
        self._table_stack.addWidget(self.loading_state)
        self._table_stack.addWidget(self.error_state)

        table_host = QWidget()
        table_layout = QVBoxLayout(table_host)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(6)
        table_layout.addLayout(self._table_stack)
        self._pagination_bar = QHBoxLayout()
        self._pagination_bar.setSpacing(8)
        self._pagination_bar.setContentsMargins(0, 0, 0, 0)
        table_layout.addLayout(self._pagination_bar)
        root.addWidget(table_host, 1)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(12)

        def _configure_field(widget, *, multiline: bool = False) -> None:
            widget.setMinimumWidth(260)
            if multiline:
                widget.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
                )
            else:
                if hasattr(widget, "setMinimumHeight"):
                    widget.setMinimumHeight(34)
                widget.setSizePolicy(
                    QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
                )
            if isinstance(widget, (QLineEdit, QDateTimeEdit, QSpinBox)):
                widget.setStyleSheet("padding: 6px 10px;")
            elif isinstance(widget, QTextEdit):
                widget.setStyleSheet("padding: 8px 10px;")

        self.when = QDateTimeEdit(QDateTime.currentDateTime())
        self.when.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.when.setCalendarPopup(True)
        _configure_field(self.when)
        form.addRow("تاريخ الشراء:", self.when)

        self.supplier = QLineEdit()
        self.supplier.setPlaceholderText("اسم المورد أو الجهة")
        _configure_field(self.supplier)
        form.addRow("المورد:", self.supplier)

        self.invoice = QLineEdit()
        self.invoice.setPlaceholderText("رقم الفاتورة أو المرجع (اختياري)")
        _configure_field(self.invoice)
        form.addRow("رقم الفاتورة:", self.invoice)

        self.amount = QSpinBox()
        self.amount.setRange(0, 50_000_000)
        self.amount.setSuffix(" ج.م")
        self.amount.setSingleStep(10)
        _configure_field(self.amount)
        form.addRow("المبلغ بالجنيه:", self.amount)

        self.notes = QTextEdit()
        self.notes.setPlaceholderText("ملاحظات حول الشراء، البنود أو طريقة الدفع…")
        self.notes.setMinimumHeight(90)
        _configure_field(self.notes, multiline=True)
        form.addRow("ملاحظات:", self.notes)

        root.addWidget(form_host, 0)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.btn_refresh = DSButton("تحديث السجل", variant="secondary")
        self.btn_refresh.clicked.connect(self._refresh)
        buttons.addWidget(self.btn_refresh)
        self.btn_save = DSButton("حفظ الشراء")
        self.btn_save.clicked.connect(self._on_save)
        self.btn_save.setDefault(True)
        buttons.addWidget(self.btn_save)
        root.addLayout(buttons)

        self._all_records: list[purchases.PurchaseRecord] = []
        self._filtered_records: list[purchases.PurchaseRecord] = []
        self._page_size = 12
        self._page_index = 0
        self._refresh()

    def _build_state(self, message: str, cta: str | None, action) -> QWidget:
        wrapper = QWidget()
        layout = QVBoxLayout(wrapper)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)

        label = QLabel(message)
        label.setProperty("data-typo", "title")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        if cta:
            btn = DSButton(cta)
            btn.clicked.connect(action)
            layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return wrapper

    def _refresh(self) -> None:
        self._show_state(self.loading_state)
        try:
            records = purchases.list_purchases()
        except Exception as exc:  # pragma: no cover - UI feedback
            self._show_state(self.error_state)
            QMessageBox.critical(self, "خطأ", f"تعذر تحميل المشتريات: {exc}")
            return

        self._all_records = records
        self._apply_filters()
        self._update_cards()

    def _on_save(self) -> None:
        supplier = self.supplier.text().strip()
        if not supplier:
            QMessageBox.warning(self, "معلومات ناقصة", "يرجى إدخال اسم المورد أولاً.")
            return

        amount_pounds = self.amount.value()
        if amount_pounds <= 0:
            QMessageBox.warning(self, "مبلغ غير صالح", "أدخل مبلغاً أكبر من صفر بالجنيه.")
            return

        when_dt = self.when.dateTime().toPyDateTime()
        invoice = self.invoice.text().strip()
        notes = self.notes.toPlainText().strip()

        try:
            record = purchases.create_purchase(
                supplier=supplier,
                amount_pounds=amount_pounds,
                invoice_no=invoice,
                notes=notes,
                recorded_by=self._actor,
                purchased_at=when_dt,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "مدخلات غير صحيحة", str(exc))
            return
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "خطأ", f"تعذر حفظ الشراء: {exc}")
            return

        self._all_records.insert(0, record)
        self._apply_filters()
        self._update_cards()
        self._clear_form()
        QMessageBox.information(self, "تم الحفظ", "تم تسجيل عملية الشراء بنجاح.")

    def _set_row_values(self, row: int, record: purchases.PurchaseRecord) -> None:
        values = (
            record.purchased_at.strftime("%Y-%m-%d %H:%M"),
            record.supplier,
            record.invoice_no,
            format_pounds(record.amount_pounds),
            record.display_notes,
            record.recorded_by or "",
        )
        for col, value in enumerate(values):
            self.table.setItem(row, col, QTableWidgetItem(value))

    # ----------------------------- Filtering & pagination helpers ----------
    def _apply_filters(self) -> None:
        supplier_term = self.filter_supplier.text().strip().lower()
        invoice_term = self.filter_invoice.text().strip().lower()
        min_amount = self.filter_min_amount.text().strip()
        try:
            min_amount_val = int(min_amount) if min_amount else 0
        except ValueError:
            min_amount_val = 0

        view = self.views.currentText()
        def _view_filter(rec: purchases.PurchaseRecord) -> bool:
            if view == "آخر 7 أيام":
                return (QDateTime.currentDateTime().toPyDateTime() - rec.purchased_at).days <= 7
            if view == "هذا الشهر":
                now = QDateTime.currentDateTime().toPyDateTime()
                return rec.purchased_at.year == now.year and rec.purchased_at.month == now.month
            if view.startswith("مشتريات كبيرة"):
                return rec.amount_pounds >= 500
            return True

        filtered = []
        for rec in self._all_records:
            if supplier_term and supplier_term not in rec.supplier.lower():
                continue
            if invoice_term and invoice_term not in rec.invoice_no.lower():
                continue
            if min_amount_val and rec.amount_pounds < min_amount_val:
                continue
            if not _view_filter(rec):
                continue
            filtered.append(rec)

        self._filtered_records = filtered
        self._page_index = 0
        self._render_table_page()

    def _render_table_page(self) -> None:
        total = len(self._filtered_records)
        if not total:
            self.table.setRowCount(0)
            self._show_state(self.empty_state)
            return

        self._show_state(self.table)
        page_count = max(1, (total + self._page_size - 1) // self._page_size)
        self._page_index = max(0, min(self._page_index, page_count - 1))
        start = self._page_index * self._page_size
        rows = self._filtered_records[start : start + self._page_size]

        self.table.setRowCount(0)
        for record in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_row_values(row, record)

        self._ensure_pagination_footer(page_count)

    def _ensure_pagination_footer(self, page_count: int) -> None:
        self._clear_layout(self._pagination_bar)
        self._pagination_bar.setContentsMargins(0, 8, 0, 0)

        prev_btn = DSButton("السابق", variant="secondary")
        prev_btn.clicked.connect(lambda: self._change_page(-1))
        next_btn = DSButton("التالي", variant="secondary")
        next_btn.clicked.connect(lambda: self._change_page(1))
        prev_btn.setEnabled(self._page_index > 0)
        next_btn.setEnabled(self._page_index < page_count - 1)

        page_label = QLabel(f"صفحة {self._page_index + 1} من {page_count}")
        page_label.setProperty("data-typo", "caption")

        self._pagination_bar.addWidget(prev_btn)
        self._pagination_bar.addWidget(next_btn)
        self._pagination_bar.addWidget(page_label)
        self._pagination_bar.addStretch(1)

    def _change_page(self, delta: int) -> None:
        self._page_index += delta
        self._render_table_page()

    def _clear_filters(self) -> None:
        self.filter_supplier.clear()
        self.filter_invoice.clear()
        self.filter_min_amount.clear()
        self.views.setCurrentIndex(0)
        self._apply_filters()

    def _show_state(self, widget: QWidget) -> None:
        index = self._table_stack.indexOf(widget)
        if index >= 0:
            self._table_stack.setCurrentIndex(index)
        self.table.setVisible(widget is self.table)

    def _clear_layout(self, layout: QHBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _update_cards(self) -> None:
        total_amount = sum(r.amount_pounds for r in self._all_records)
        count = len(self._all_records)
        avg = total_amount / count if count else 0
        self.total_card.set_value(format_pounds(total_amount))
        self.avg_card.set_value(format_pounds(int(avg)))
        self.count_card.set_value(f"{count} عملية")

    def _clear_form(self) -> None:
        self.when.setDateTime(QDateTime.currentDateTime())
        self.supplier.clear()
        self.invoice.clear()
        self.amount.setValue(0)
        self.notes.clear()
        self.supplier.setFocus()

    def _focus_form(self) -> None:
        self.supplier.setFocus()

