"""Dialog that surfaces end-of-shift KPIs for the current operator."""
from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from ..utils.currency import format_pounds


def _format_dt(value: datetime | None) -> str:
    if not isinstance(value, datetime):
        return "—"
    return value.strftime("%Y-%m-%d %H:%M")


def _format_duration(seconds: int) -> str:
    seconds = max(int(seconds or 0), 0)
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class ShiftSummaryDialog(QDialog):
    def __init__(self, username: str, metrics: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ملخص الوردية")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QLabel(f"المستخدم: <b>{username}</b>")
        header.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(header)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)
        layout.addLayout(form)

        form.addRow("بداية الوردية:", QLabel(_format_dt(metrics.get("window_start"))))
        form.addRow("نهاية الوردية:", QLabel(_format_dt(metrics.get("window_end"))))
        form.addRow("المدة:", QLabel(_format_duration(metrics.get("duration_seconds", 0))))
        form.addRow("طلبات تم فتحها:", QLabel(str(metrics.get("orders_opened", 0))))
        form.addRow("طلبات تم إغلاقها:", QLabel(str(metrics.get("orders_closed", 0))))
        form.addRow("طلبات ملغاة:", QLabel(str(metrics.get("voided_orders", 0))))
        form.addRow(
            "عدد المدفوعات:",
            QLabel(str(metrics.get("payments_count", 0))),
        )
        form.addRow(
            "إجمالي التحصيل:",
            QLabel(format_pounds(metrics.get("payments_total_cents", 0))),
        )
        form.addRow(
            "إجمالي الخصومات:",
            QLabel(format_pounds(metrics.get("discount_cents", 0))),
        )

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.resize(420, self.sizeHint().height())
