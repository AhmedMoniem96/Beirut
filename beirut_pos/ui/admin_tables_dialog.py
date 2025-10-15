# beirut_pos/ui/admin_tables_dialog.py
from PyQt6.QtWidgets import (
    QListWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QLabel,
    QWidget,
)
from PyQt6.QtCore import Qt

from .common.big_dialog import BigDialog
from ..services.orders import (
    order_manager,
    default_table_codes,
)


class AdminTablesDialog(BigDialog):
    """Interactive table manager for admins (add/remove/reorder codes)."""

    def __init__(self, actor: str = "admin", parent=None):
        super().__init__("إدارة الطاولات", remember_key="tables_admin", parent=parent)
        self._actor = actor or "admin"

        root = QVBoxLayout(self)
        intro = QLabel(
            "عدّل أسماء الطاولات وترتيبها. سيتم تحديث شاشة الطاولات فور الحفظ،"
            " ولا يمكن حذف طاولة يوجد عليها طلب مفتوح."
        )
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.feedback = QLabel("")
        self.feedback.setObjectName("feedbackLabel")
        self.feedback.setWordWrap(True)
        self.feedback.hide()
        root.addWidget(self.feedback)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.list_widget.itemSelectionChanged.connect(self._sync_entry_with_selection)
        root.addWidget(self.list_widget, 1)

        entry_row = QHBoxLayout()
        self.code_entry = QLineEdit()
        self.code_entry.setPlaceholderText("مثال: T01 أو VIP")
        entry_row.addWidget(self.code_entry, 1)
        add_btn = QPushButton("إضافة")
        add_btn.clicked.connect(self._add_code)
        rename_btn = QPushButton("تعديل الاسم")
        rename_btn.clicked.connect(self._rename_selected)
        entry_row.addWidget(add_btn)
        entry_row.addWidget(rename_btn)
        entry_widget = QWidget()
        entry_widget.setLayout(entry_row)
        root.addWidget(entry_widget)

        actions = QHBoxLayout()
        up_btn = QPushButton("⬆ للأعلى")
        up_btn.clicked.connect(lambda: self._move_selected(-1))
        down_btn = QPushButton("⬇ للأسفل")
        down_btn.clicked.connect(lambda: self._move_selected(1))
        remove_btn = QPushButton("حذف")
        remove_btn.clicked.connect(self._remove_selected)
        reset_btn = QPushButton("استعادة الترتيب الافتراضي")
        reset_btn.clicked.connect(self._reset_defaults)
        actions.addWidget(up_btn)
        actions.addWidget(down_btn)
        actions.addWidget(remove_btn)
        actions.addStretch(1)
        actions.addWidget(reset_btn)
        actions_widget = QWidget()
        actions_widget.setLayout(actions)
        root.addWidget(actions_widget)

        save = QPushButton("حفظ")
        save.setDefault(True)
        save.clicked.connect(self._save)
        root.addWidget(save, 0, alignment=Qt.AlignmentFlag.AlignLeft)

        self._reload()

    # ------------------------------------------------------------------ UI --
    def _reload(self):
        self.list_widget.clear()
        for code in order_manager.get_table_codes():
            self.list_widget.addItem(code)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _set_feedback(self, text: str, kind: str = "info"):
        palette = {
            "info": "color:#F1C58F;",
            "warn": "color:#F5B300;",
            "error": "color:#F46A6A;",
            "success": "color:#7CD992;",
        }
        self.feedback.setStyleSheet(palette.get(kind, ""))
        self.feedback.setText(text)
        self.feedback.setVisible(bool(text))

    def _current_code(self) -> str | None:
        item = self.list_widget.currentItem()
        if not item:
            return None
        code = item.text().strip().upper()
        return code or None

    def _sync_entry_with_selection(self):
        code = self._current_code()
        if code:
            self.code_entry.setText(code)

    # ------------------------------------------------------------- actions --
    def _add_code(self):
        code = self.code_entry.text().strip().upper()
        if not code:
            self._set_feedback("أدخل رمز الطاولة أولاً.", "warn")
            return
        existing = {self.list_widget.item(i).text().strip().upper() for i in range(self.list_widget.count())}
        if code in existing:
            self._set_feedback("الرمز موجود مسبقاً.", "warn")
            return
        self.list_widget.addItem(code)
        self.list_widget.setCurrentRow(self.list_widget.count() - 1)
        self._set_feedback("تمت إضافة الطاولة.", "success")

    def _rename_selected(self):
        idx = self.list_widget.currentRow()
        if idx < 0:
            self._set_feedback("اختر طاولة لتعديل الاسم.", "warn")
            return
        new_code = self.code_entry.text().strip().upper()
        if not new_code:
            self._set_feedback("أدخل الاسم الجديد للطاولة.", "warn")
            return
        for i in range(self.list_widget.count()):
            if i == idx:
                continue
            if self.list_widget.item(i).text().strip().upper() == new_code:
                self._set_feedback("يوجد طاولة بنفس الرمز.", "warn")
                return
        self.list_widget.item(idx).setText(new_code)
        self._set_feedback("تم تحديث الاسم.", "success")

    def _remove_selected(self):
        idx = self.list_widget.currentRow()
        if idx < 0:
            self._set_feedback("اختر طاولة للحذف.", "warn")
            return
        code = self.list_widget.item(idx).text().strip().upper()
        if code in order_manager.orders:
            self._set_feedback("لا يمكن حذف طاولة عليها طلب مفتوح.", "error")
            return
        self.list_widget.takeItem(idx)
        self._set_feedback("تمت إزالة الطاولة.", "success")

    def _move_selected(self, delta: int):
        idx = self.list_widget.currentRow()
        if idx < 0:
            self._set_feedback("اختر طاولة لتحريكها.", "warn")
            return
        new_index = idx + delta
        if not (0 <= new_index < self.list_widget.count()):
            return
        item = self.list_widget.takeItem(idx)
        self.list_widget.insertItem(new_index, item)
        self.list_widget.setCurrentRow(new_index)

    def _reset_defaults(self):
        self.list_widget.clear()
        for code in default_table_codes():
            self.list_widget.addItem(code)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        self._set_feedback("تمت استعادة الإعداد الافتراضي.", "info")

    def _save(self):
        codes = []
        seen = set()
        for i in range(self.list_widget.count()):
            code = self.list_widget.item(i).text().strip().upper()
            if not code or code in seen:
                continue
            seen.add(code)
            codes.append(code)
        order_manager.set_table_codes(codes, actor=self._actor)
        self.accept()
