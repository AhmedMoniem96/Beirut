"""Reports tab for Jewelry app."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (
    QDateEdit,
    QDateTimeEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from beirut_pos.utils.excel import write_protected_workbook

from ...services.db import fetch_shift_session_for_date, save_shift_session
from ...services.pdf_exports import GalleryInfo, export_daily_report_pdf
from ...services.reports import lowest_products, payment_breakdown, returns_aggregate, sales_aggregate, stock_alerts, top_products
from ...services.session import get_current_user
from ...services.settings import load_gallery_settings


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


class ReportsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._last_report: Optional[ReportData] = None

        main_layout = QVBoxLayout(self)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        content = QWidget()
        scroll_area.setWidget(content)
        layout = QVBoxLayout(content)
        header = QLabel("Reports (التقارير)")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        filters = QHBoxLayout()
        self.date_filter = QDateEdit()
        self.date_filter.setCalendarPopup(True)
        self.date_filter.setDate(QDate.currentDate())
        self.date_filter.dateChanged.connect(self._load_shift_from_db)
        self.refresh_btn = QPushButton("Generate (إنشاء)")
        self.refresh_btn.clicked.connect(self._generate_report)
        filters.addWidget(QLabel("Date (التاريخ):"))
        filters.addWidget(self.date_filter)
        filters.addWidget(self.refresh_btn)

        shift_box = QGroupBox("Shift Info (بيانات الوردية)")
        shift_layout = QFormLayout(shift_box)
        self.cashier_input = QLineEdit()
        self.cashier_input.setReadOnly(True)
        self.open_time_input = QDateTimeEdit()
        self.open_time_input.setCalendarPopup(True)
        self.close_time_input = QDateTimeEdit()
        self.close_time_input.setCalendarPopup(True)
        self.opening_cash_input = QDoubleSpinBox()
        self.opening_cash_input.setRange(0, 999999)
        self.opening_cash_input.setDecimals(2)
        self.closing_cash_input = QDoubleSpinBox()
        self.closing_cash_input.setRange(0, 999999)
        self.closing_cash_input.setDecimals(2)
        self.opening_cash_input.valueChanged.connect(self._refresh_cash_diff)
        self.closing_cash_input.valueChanged.connect(self._refresh_cash_diff)
        self.expected_cash_label = QLabel("Expected: 0.00")
        self.diff_label = QLabel("Over/Short: 0.00")
        self.notes_input = QTextEdit()
        self.notes_input.setMinimumHeight(90)
        self.notes_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        shift_layout.addRow("Cashier (الكاشير):", self.cashier_input)
        shift_layout.addRow("Open Time (فتح):", self.open_time_input)
        shift_layout.addRow("Close Time (إغلاق):", self.close_time_input)
        shift_layout.addRow("Opening Cash (بداية):", self.opening_cash_input)
        shift_layout.addRow("Actual Cash (نقد فعلي):", self.closing_cash_input)
        shift_layout.addRow("Expected (متوقع):", self.expected_cash_label)
        shift_layout.addRow("Over/Short (فرق):", self.diff_label)
        shift_layout.addRow("Notes (ملاحظات):", self.notes_input)

        save_shift_btn = QPushButton("Save Shift Session (حفظ الوردية)")
        save_shift_btn.clicked.connect(self._save_shift_session)

        self.summary_label = QLabel("Daily report summary will appear here.")

        self.payment_table = QTableWidget(0, 2)
        self.payment_table.setHorizontalHeaderLabels(["Payment Method", "Total"])
        self.returns_table = QTableWidget(0, 3)
        self.returns_table.setHorizontalHeaderLabels(["Reason", "Count", "Total"])
        self.top_table = QTableWidget(0, 3)
        self.top_table.setHorizontalHeaderLabels(["Product", "Code", "Qty"])
        self.low_table = QTableWidget(0, 3)
        self.low_table.setHorizontalHeaderLabels(["Product", "Code", "Qty"])
        self.stock_table = QTableWidget(0, 5)
        self.stock_table.setHorizontalHeaderLabels(["Product", "SKU", "Qty", "Min", "Status"])
        for table in [
            self.payment_table,
            self.returns_table,
            self.top_table,
            self.low_table,
            self.stock_table,
        ]:
            table.setAlternatingRowColors(True)

        export_layout = QHBoxLayout()
        self.export_pdf_btn = QPushButton("Export PDF (تصدير PDF)")
        self.export_pdf_btn.clicked.connect(self._export_pdf)
        self.export_excel_btn = QPushButton("Export Excel (تصدير Excel)")
        self.export_excel_btn.clicked.connect(self._export_excel)
        export_layout.addWidget(self.export_pdf_btn)
        export_layout.addWidget(self.export_excel_btn)

        top_section = QWidget()
        top_layout = QVBoxLayout(top_section)
        top_layout.addLayout(filters)
        top_layout.addWidget(shift_box)
        top_layout.addWidget(save_shift_btn)
        top_layout.addWidget(self.summary_label)

        tables_section = QWidget()
        tables_layout = QVBoxLayout(tables_section)
        tables_layout.addWidget(QLabel("Payment Breakdown (تفاصيل الدفع)"))
        tables_layout.addWidget(self.payment_table)
        tables_layout.addWidget(QLabel("Return Reasons (أسباب المرتجع)"))
        tables_layout.addWidget(self.returns_table)
        tables_layout.addWidget(QLabel("Top 5 Sold Products (الأكثر مبيعًا)"))
        tables_layout.addWidget(self.top_table)
        tables_layout.addWidget(QLabel("Lowest Sold Products (الأقل مبيعًا)"))
        tables_layout.addWidget(self.low_table)
        tables_layout.addWidget(QLabel("Stock Alerts (تنبيهات المخزون)"))
        tables_layout.addWidget(self.stock_table)
        tables_layout.addLayout(export_layout)
        tables_layout.addStretch()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_section)
        splitter.addWidget(tables_section)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        self._initialize_shift_defaults()
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

    def set_cashier_name(self, name: str) -> None:
        if not self.cashier_input.text().strip():
            self.cashier_input.setText(name)

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
        start_dt = datetime.combine(date_qt.toPyDate(), time.min)
        end_dt = datetime.combine(date_qt.toPyDate(), time.max)
        start_iso = start_dt.isoformat(timespec="seconds")
        end_iso = end_dt.isoformat(timespec="seconds")

        sales = sales_aggregate(start_iso, end_iso)
        payments = payment_breakdown(start_iso, end_iso)
        net_payments = payment_breakdown(start_iso, end_iso, include_returns=True)
        returns = returns_aggregate(start_iso, end_iso)
        top = top_products(start_iso, end_iso, limit=5)
        low = lowest_products(start_iso, end_iso, limit=5)
        out_of_stock, near_out = stock_alerts()

        self._populate_table(self.payment_table, [(k, f"{v:.2f}") for k, v in payments.items()])
        self._populate_table(
            self.returns_table,
            [(reason, str(count), f"{total:.2f}") for reason, count, total in returns.reasons],
        )
        self._populate_table(
            self.top_table,
            [(p.name, p.code, f"{p.qty:.2f}") for p in top],
        )
        self._populate_table(
            self.low_table,
            [(p.name, p.code, f"{p.qty:.2f}") for p in low],
        )
        stock_rows = []
        for name_ar, name_en, sku, qty, min_qty in out_of_stock:
            stock_rows.append((f"{name_en} / {name_ar}", sku, f"{qty:.2f}", f"{min_qty:.2f}", "Out"))
        for name_ar, name_en, sku, qty, min_qty in near_out:
            stock_rows.append((f"{name_en} / {name_ar}", sku, f"{qty:.2f}", f"{min_qty:.2f}", "Near"))
        self._populate_table(self.stock_table, stock_rows)

        expected_cash = self._compute_expected_cash(net_payments)
        self.expected_cash_label.setText(f"Expected: {expected_cash:.2f}")
        diff = float(self.closing_cash_input.value()) - expected_cash
        self.diff_label.setText(f"Over/Short: {diff:.2f}")

        self.summary_label.setText(
            f"Invoices: {sales.invoice_count} | Subtotal: {sales.subtotal:.2f} | "
            f"Discounts: {sales.discounts:.2f} | Net Sales: {sales.net_sales:.2f}"
        )

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
            return_reasons=returns.reasons,
            top_products=[(p.name, p.code, p.qty) for p in top],
            low_products=[(p.name, p.code, p.qty) for p in low],
            out_of_stock=list(out_of_stock),
            near_out=list(near_out),
        )

    def _refresh_cash_diff(self) -> None:
        if not self._last_report:
            return
        diff = float(self.closing_cash_input.value()) - self._last_report.expected_cash
        self.diff_label.setText(f"Over/Short: {diff:.2f}")

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
        QMessageBox.information(self, "Saved", "Shift session saved.")

    def _export_pdf(self) -> None:
        if not self._last_report:
            QMessageBox.warning(self, "Export", "Generate report first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Daily Report PDF",
            f"{self._last_report.report_number}.pdf",
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
        QMessageBox.information(self, "Export", "Daily report PDF exported.")

    def _export_excel(self) -> None:
        if not self._last_report:
            QMessageBox.warning(self, "Export", "Generate report first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Daily Report Excel",
            f"{self._last_report.report_number}.xlsx",
            "Excel Files (*.xlsx)",
        )
        if not path:
            return
        rows: List[List[str]] = [
            ["Daily Report", "تقرير يومي"],
            ["Date", self._last_report.report_date],
            ["Report No", self._last_report.report_number],
            ["Cashier", self._last_report.cashier],
            ["Shift Open", self._last_report.shift_open],
            ["Shift Close", self._last_report.shift_close],
            ["Opening Cash", f"{self._last_report.opening_cash:.2f}"],
            ["Expected Cash", f"{self._last_report.expected_cash:.2f}"],
            ["Actual Cash", f"{self._last_report.closing_cash_actual:.2f}"],
            ["Over/Short", f"{self._last_report.closing_cash_actual - self._last_report.expected_cash:.2f}"],
            ["Notes", self._last_report.notes],
            ["", ""],
            ["Sales Movement", ""],
            ["Invoices", str(self._last_report.sales_summary[0])],
            ["Subtotal", f"{self._last_report.sales_summary[1]:.2f}"],
            ["Discounts", f"{self._last_report.sales_summary[2]:.2f}"],
            ["Net Sales", f"{self._last_report.sales_summary[3]:.2f}"],
            ["", ""],
            ["Payment Breakdown", ""],
        ]
        for method, total in self._last_report.payment_breakdown:
            rows.append([method, f"{total:.2f}"])
        rows.append(["", ""])
        rows.append(["Returns", ""])
        rows.append(["Return Count", str(self._last_report.returns_summary[0])])
        rows.append(["Return Value", f"{self._last_report.returns_summary[1]:.2f}"])
        for reason, count, total in self._last_report.return_reasons:
            rows.append([reason, f"{count} ({total:.2f})"])
        rows.append(["", ""])
        rows.append(["Top Sold Products", ""])
        for name, code, qty in self._last_report.top_products:
            rows.append([f"{name} ({code})", f"{qty:.2f}"])
        rows.append(["Lowest Sold Products", ""])
        for name, code, qty in self._last_report.low_products:
            rows.append([f"{name} ({code})", f"{qty:.2f}"])
        rows.append(["", ""])
        rows.append(["Stock Alerts", ""])
        for name_ar, name_en, sku, qty, min_qty in self._last_report.out_of_stock:
            rows.append([f"{name_en} / {name_ar}", f"{qty:.2f} - Out"])
        for name_ar, name_en, sku, qty, min_qty in self._last_report.near_out:
            rows.append([f"{name_en} / {name_ar}", f"{qty:.2f} - Near"])

        write_protected_workbook(path, ["Field", "Value"], rows, title="Daily Report")
        QMessageBox.information(self, "Export", "Daily report Excel exported.")
