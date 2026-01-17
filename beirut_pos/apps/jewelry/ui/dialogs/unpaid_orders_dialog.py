"""Dialog for unpaid and partially paid orders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QHeaderView,
)

from ...services.db import (
    JewelryUnpaidOrder,
    create_order_payment,
    fetch_invoice_details,
    list_payment_methods,
    list_unpaid_orders,
)
from ...services.i18n import choose_name, get_ui_language, t
from ...services.session import get_current_user


@dataclass
class OrderSummary:
    order: JewelryUnpaidOrder
    payment_status_label: str
    payment_order_status_label: str


class AddPaymentDialog(QDialog):
    def __init__(self, remaining_total: float, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.payment_method_label = QLabel()
        self.payment_method_combo = None
        self._build_payment_method_input(form_layout)

        self.amount_input = QDoubleSpinBox()
        max_amount = max(remaining_total, 0.01)
        self.amount_input.setRange(0.01, max_amount)
        self.amount_input.setDecimals(2)
        self.amount_input.setValue(max_amount)
        self.reference_input = QLineEdit()
        self.notes_input = QTextEdit()
        self.notes_input.setMinimumHeight(80)

        self.amount_label = QLabel()
        self.reference_label = QLabel()
        self.notes_label = QLabel()
        form_layout.addRow(self.amount_label, self.amount_input)
        form_layout.addRow(self.reference_label, self.reference_input)
        form_layout.addRow(self.notes_label, self.notes_input)
        layout.addLayout(form_layout)

        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_btn = QPushButton()
        self.add_btn = QPushButton()
        self.cancel_btn.clicked.connect(self.reject)
        self.add_btn.clicked.connect(self.accept)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.add_btn)
        layout.addLayout(actions)

        self.apply_language(self._language)

    def _build_payment_method_input(self, form_layout: QFormLayout) -> None:
        from PyQt6.QtWidgets import QComboBox

        methods = list_payment_methods()
        combo = QComboBox()
        for _, name_ar, name_en in methods:
            combo.addItem(choose_name(name_ar, name_en))
        self.payment_method_combo = combo
        form_layout.addRow(self.payment_method_label, combo)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.setWindowTitle(t("payment.add_title", language=language))
        self.payment_method_label.setText(t("common.payment_method", language=language))
        self.amount_label.setText(t("payment.amount", language=language))
        self.reference_label.setText(t("payment.reference", language=language))
        self.notes_label.setText(t("payment.note", language=language))
        self.cancel_btn.setText(t("payment.cancel", language=language))
        self.add_btn.setText(t("payment.add", language=language))

    def payment_method(self) -> str:
        if self.payment_method_combo is None:
            return ""
        return self.payment_method_combo.currentText().strip()

    def amount(self) -> float:
        return float(self.amount_input.value())

    def reference(self) -> str:
        return self.reference_input.text().strip()

    def notes(self) -> str:
        return self.notes_input.toPlainText().strip()


class OrderDetailsDialog(QDialog):
    def __init__(self, summary: OrderSummary, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self.setModal(True)
        self.setMinimumWidth(640)

        invoice, items = fetch_invoice_details(summary.order.invoice_no)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.order_no_label = QLabel()
        self.date_label = QLabel()
        self.customer_label = QLabel()
        self.phone_label = QLabel()
        self.total_label = QLabel()
        self.paid_label = QLabel()
        self.remaining_label = QLabel()
        self.status_label = QLabel()

        self.order_no_value = QLabel(invoice.invoice_no)
        self.date_value = QLabel(invoice.datetime)
        self.customer_value = QLabel(invoice.customer_name or "-")
        self.phone_value = QLabel(invoice.customer_phone or "-")
        self.total_value = QLabel(f"{summary.order.total:.2f}")
        self.paid_value = QLabel(f"{summary.order.paid_total:.2f}")
        self.remaining_value = QLabel(f"{summary.order.remaining_total:.2f}")
        self.status_value = QLabel(summary.payment_status_label)

        form_layout.addRow(self.order_no_label, self.order_no_value)
        form_layout.addRow(self.date_label, self.date_value)
        form_layout.addRow(self.customer_label, self.customer_value)
        form_layout.addRow(self.phone_label, self.phone_value)
        form_layout.addRow(self.total_label, self.total_value)
        form_layout.addRow(self.paid_label, self.paid_value)
        form_layout.addRow(self.remaining_label, self.remaining_value)
        form_layout.addRow(self.status_label, self.status_value)
        layout.addLayout(form_layout)

        self.items_label = QLabel()
        layout.addWidget(self.items_label)

        table = QTableWidget(0, 5)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setHorizontalHeaderLabels(
            [
                t("common.product", language=self._language),
                t("common.code", language=self._language),
                t("common.qty", language=self._language),
                t("common.price", language=self._language),
                t("common.total", language=self._language),
            ]
        )
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for item in items:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(item.product_name))
            table.setItem(row, 1, QTableWidgetItem(item.product_code))
            table.setItem(row, 2, QTableWidgetItem(f"{item.qty:.2f}"))
            table.setItem(row, 3, QTableWidgetItem(f"{item.unit_price:.2f}"))
            table.setItem(row, 4, QTableWidgetItem(f"{item.line_total:.2f}"))
        layout.addWidget(table)

        actions = QHBoxLayout()
        actions.addStretch()
        close_btn = QPushButton()
        close_btn.clicked.connect(self.accept)
        actions.addWidget(close_btn)
        layout.addLayout(actions)

        self.items_table = table
        self.close_btn = close_btn
        self.apply_language(self._language)

    def apply_language(self, language: str) -> None:
        self._language = language
        self.setWindowTitle(t("order_details.title", language=language))
        self.order_no_label.setText(t("order_details.order_no", language=language))
        self.date_label.setText(t("order_details.date", language=language))
        self.customer_label.setText(t("order_details.customer", language=language))
        self.phone_label.setText(t("order_details.phone", language=language))
        self.total_label.setText(t("order_details.total", language=language))
        self.paid_label.setText(t("order_details.paid", language=language))
        self.remaining_label.setText(t("order_details.remaining", language=language))
        self.status_label.setText(t("order_details.payment_status", language=language))
        self.items_label.setText(t("order_details.items", language=language))
        self.items_table.setHorizontalHeaderLabels(
            [
                t("common.product", language=language),
                t("common.code", language=language),
                t("common.qty", language=language),
                t("common.price", language=language),
                t("common.total", language=language),
            ]
        )
        self.close_btn.setText(t("unpaid_orders.action_close", language=language))


class UnpaidOrdersDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._language = get_ui_language()
        self.setModal(True)
        self.resize(1100, 640)

        layout = QVBoxLayout(self)
        header = QLabel()
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)
        self.header_label = header

        self.filter_tabs = QTabBar()
        self.filter_tabs.addTab("")
        self.filter_tabs.addTab("")
        self.filter_tabs.addTab("")
        self.filter_tabs.currentChanged.connect(self._refresh_table)
        layout.addWidget(self.filter_tabs)

        filters_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self._refresh_table)
        self.all_dates_toggle = QCheckBox()
        self.all_dates_toggle.setChecked(True)
        self.all_dates_toggle.toggled.connect(self._toggle_dates)

        self.date_from_input = QDateEdit()
        self.date_from_input.setCalendarPopup(True)
        self.date_from_input.setDate(QDate(2000, 1, 1))
        self.date_from_input.dateChanged.connect(self._refresh_table)
        self.date_to_input = QDateEdit()
        self.date_to_input.setCalendarPopup(True)
        self.date_to_input.setDate(QDate.currentDate())
        self.date_to_input.dateChanged.connect(self._refresh_table)

        self.date_from_label = QLabel()
        self.date_to_label = QLabel()

        filters_layout.addWidget(self.search_input, 2)
        filters_layout.addWidget(self.all_dates_toggle)
        filters_layout.addWidget(self.date_from_label)
        filters_layout.addWidget(self.date_from_input)
        filters_layout.addWidget(self.date_to_label)
        filters_layout.addWidget(self.date_to_input)
        layout.addLayout(filters_layout)

        self.table = QTableWidget(0, 9)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.selectionModel().selectionChanged.connect(self._update_action_state)
        layout.addWidget(self.table)

        actions = QHBoxLayout()
        self.add_payment_btn = QPushButton()
        self.open_order_btn = QPushButton()
        self.close_btn = QPushButton()
        self.add_payment_btn.clicked.connect(self._open_payment_dialog)
        self.open_order_btn.clicked.connect(self._open_order_details)
        self.close_btn.clicked.connect(self.accept)
        actions.addWidget(self.add_payment_btn)
        actions.addWidget(self.open_order_btn)
        actions.addStretch()
        actions.addWidget(self.close_btn)
        layout.addLayout(actions)

        self._toggle_dates(self.all_dates_toggle.isChecked())
        self.apply_language(self._language)
        self._refresh_table()

    def _toggle_dates(self, checked: bool) -> None:
        self.date_from_input.setEnabled(not checked)
        self.date_to_input.setEnabled(not checked)
        self._refresh_table()

    def _status_filter(self) -> str:
        index = self.filter_tabs.currentIndex()
        if index == 1:
            return "PARTIAL"
        if index == 2:
            return "OVERDUE"
        return "UNPAID"

    def _selected_order(self) -> Optional[OrderSummary]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        summary = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(summary, OrderSummary):
            return summary
        return None

    def _refresh_table(self) -> None:
        if not self.table:
            return
        status_filter = self._status_filter()
        search = self.search_input.text().strip()
        date_from = None
        date_to = None
        if not self.all_dates_toggle.isChecked():
            date_from = self.date_from_input.date().toString("yyyy-MM-dd")
            date_to = self.date_to_input.date().toString("yyyy-MM-dd")
        orders = list_unpaid_orders(
            status_filter=status_filter,
            search=search,
            date_from=date_from,
            date_to=date_to,
        )
        self.table.setRowCount(0)
        for order in orders:
            summary = self._build_summary(order)
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._set_item(row, 0, order.invoice_no, summary)
            self._set_item(row, 1, order.datetime)
            customer_text = order.customer_name or "-"
            if order.customer_phone:
                customer_text = f"{customer_text} ({order.customer_phone})"
            self._set_item(row, 2, customer_text)
            self._set_item(row, 3, f"{order.total:.2f}", align_right=True)
            self._set_item(row, 4, f"{order.paid_total:.2f}", align_right=True)
            self._set_item(row, 5, f"{order.remaining_total:.2f}", align_right=True)
            self._set_item(row, 6, order.payment_due_date or "-")
            self._set_item(row, 7, summary.payment_status_label)
            self._set_item(row, 8, summary.payment_order_status_label or "-")
        self._update_action_state()

    def _build_summary(self, order: JewelryUnpaidOrder) -> OrderSummary:
        status_key = (order.payment_status or "").upper()
        status_label = {
            "UNPAID": t("payment.status.unpaid", language=self._language),
            "PARTIAL": t("payment.status.partial", language=self._language),
            "PAID": t("payment.status.paid", language=self._language),
        }.get(status_key, order.payment_status)
        order_status_label = choose_name(
            order.payment_order_status_name_ar,
            order.payment_order_status_name_en,
            language=self._language,
        )
        return OrderSummary(
            order=order,
            payment_status_label=status_label,
            payment_order_status_label=order_status_label,
        )

    def _set_item(
        self,
        row: int,
        column: int,
        text: str,
        summary: Optional[OrderSummary] = None,
        align_right: bool = False,
    ) -> None:
        item = QTableWidgetItem(text)
        if align_right:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if summary is not None:
            item.setData(Qt.ItemDataRole.UserRole, summary)
        self.table.setItem(row, column, item)

    def _update_action_state(self) -> None:
        has_selection = self._selected_order() is not None
        self.add_payment_btn.setEnabled(has_selection)
        self.open_order_btn.setEnabled(has_selection)

    def _open_payment_dialog(self) -> None:
        summary = self._selected_order()
        if not summary:
            return
        dialog = AddPaymentDialog(summary.order.remaining_total, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        if not dialog.payment_method():
            QMessageBox.warning(
                self,
                t("payment.add_title", language=self._language),
                t("payment.method_required", language=self._language),
            )
            return
        if dialog.amount() <= 0:
            QMessageBox.warning(
                self,
                t("payment.add_title", language=self._language),
                t("payment.amount_required", language=self._language),
            )
            return
        user = get_current_user()
        cashier_name = user.full_name if user else ""
        try:
            create_order_payment(
                summary.order.id,
                dialog.payment_method(),
                dialog.amount(),
                cashier_name=cashier_name,
                notes=dialog.notes(),
                reference=dialog.reference(),
            )
        except ValueError as exc:
            QMessageBox.warning(
                self,
                t("payment.add_title", language=self._language),
                str(exc),
            )
            return
        self._refresh_table()

    def _open_order_details(self) -> None:
        summary = self._selected_order()
        if not summary:
            return
        dialog = OrderDetailsDialog(summary, self)
        dialog.exec()

    def apply_language(self, language: str) -> None:
        self._language = language
        self.setWindowTitle(t("unpaid_orders.title", language=language))
        self.header_label.setText(t("unpaid_orders.title", language=language))
        self.filter_tabs.setTabText(0, t("unpaid_orders.filter_unpaid", language=language))
        self.filter_tabs.setTabText(1, t("unpaid_orders.filter_partial", language=language))
        self.filter_tabs.setTabText(2, t("unpaid_orders.filter_overdue", language=language))
        self.search_input.setPlaceholderText(t("unpaid_orders.search_placeholder", language=language))
        self.all_dates_toggle.setText(t("unpaid_orders.all_dates", language=language))
        self.date_from_label.setText(t("common.from", language=language))
        self.date_to_label.setText(t("common.to", language=language))
        self.table.setHorizontalHeaderLabels(
            [
                t("unpaid_orders.column_order_no", language=language),
                t("unpaid_orders.column_date", language=language),
                t("unpaid_orders.column_customer", language=language),
                t("unpaid_orders.column_grand_total", language=language),
                t("unpaid_orders.column_paid", language=language),
                t("unpaid_orders.column_remaining", language=language),
                t("unpaid_orders.column_due_date", language=language),
                t("unpaid_orders.column_payment_status", language=language),
                t("unpaid_orders.column_payment_order_status", language=language),
            ]
        )
        self.add_payment_btn.setText(t("unpaid_orders.action_add_payment", language=language))
        self.open_order_btn.setText(t("unpaid_orders.action_open_order", language=language))
        self.close_btn.setText(t("unpaid_orders.action_close", language=language))
        self._refresh_table()
