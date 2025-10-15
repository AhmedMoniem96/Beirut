from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class ProductOptionDialog(QDialog):
    """Simple selector for per-product customization options."""

    def __init__(self, product_name: str, base_price_cents: int, options: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"اختيار خيار — {product_name}")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self._selection: dict | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        intro = QLabel("اختر خيارًا ليتم إضافته على المنتج (إن وجد).")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list = QListWidget()
        self.list.setAlternatingRowColors(True)
        layout.addWidget(self.list, 1)

        base_label = f"بدون خيار إضافي — السعر الأساسي ج.م {base_price_cents / 100:.2f}"
        base_item = QListWidgetItem(base_label)
        base_item.setData(Qt.ItemDataRole.UserRole, {"note": "", "price_delta_cents": 0})
        self.list.addItem(base_item)

        for opt in options:
            delta = int(opt.get("price_delta_cents", 0))
            sign = "+" if delta >= 0 else "-"
            amount = abs(delta) / 100
            text = f"{opt['label']} ({sign}ج.م {amount:.2f})"
            item = QListWidgetItem(text)
            item.setData(
                Qt.ItemDataRole.UserRole,
                {"note": opt["label"], "price_delta_cents": delta},
            )
            self.list.addItem(item)

        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _: self.accept())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
