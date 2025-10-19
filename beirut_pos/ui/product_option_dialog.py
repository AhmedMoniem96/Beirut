from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QHBoxLayout,
)
from ..utils.currency import format_pounds


class ProductOptionDialog(QDialog):
    """Modern selector for per-product customization options (Arabic UI)."""

    def __init__(self, product_name: str, base_price_cents: int, options: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"اختيار خيار — {product_name}")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self.setMinimumWidth(420)
        self._selection: dict | None = None

        # ----------- Layout styling -----------
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)

        # ----------- Intro label -----------
        intro = QLabel("اختر خيارًا ليتم إضافته على المنتج (إن وجد):")
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignmentFlag.AlignRight)
        intro.setStyleSheet("""
            QLabel {
                font-size: 15px;
                color: #2e2d2b;
                margin-bottom: 4px;
            }
        """)
        layout.addWidget(intro)

        # ----------- List widget -----------
        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        self.list.setStyleSheet("""
            QListWidget {
                border: 2px solid #d0b58b;
                border-radius: 8px;
                font-size: 14px;
                background-color: #fffdf9;
                selection-background-color: #c89a44;
                selection-color: white;
            }
        """)
        layout.addWidget(self.list, 1)

        # Base item
        base_label = f"بدون خيار إضافي — السعر الأساسي {format_pounds(base_price_cents)}"
        base_item = QListWidgetItem(base_label)
        base_item.setData(Qt.ItemDataRole.UserRole, {"note": "", "price_delta_cents": 0})
        self.list.addItem(base_item)

        # Add all option items
        for opt in options:
            delta = int(opt.get("price_delta_cents", 0))
            sign = "+" if delta >= 0 else "-"
            amount_text = format_pounds(abs(delta))
            text = f"{opt['label']} ({sign}{amount_text})"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, {
                "note": opt["label"],
                "price_delta_cents": delta
            })
            self.list.addItem(item)

        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())

        # ----------- Buttons (OK / Cancel) -----------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        ok_button.setText("موافق")
        cancel_button.setText("إلغاء")

        ok_button.setStyleSheet("""
            QPushButton {
                background-color: #3a8a3a;
                color: white;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #4caf50; }
        """)
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #a33a3a;
                color: white;
                border-radius: 8px;
                padding: 6px 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #c34c4c; }
        """)

        layout.addWidget(buttons)

        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

    # ----------- Logic stays identical -----------
    def accept(self) -> None:
        current = self.list.currentItem()
        if current is None:
            return
        data = current.data(Qt.ItemDataRole.UserRole) or {"note": "", "price_delta_cents": 0}
        self._selection = {
            "note": data.get("note", ""),
            "price_delta_cents": int(data.get("price_delta_cents", 0)),
        }
        super().accept()

    def get_selection(self) -> dict | None:
        return self._selection
