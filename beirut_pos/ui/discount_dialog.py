from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QDialogButtonBox,
    QMessageBox,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from ..core.auth import authenticate

class DiscountDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("تطبيق خصم (موافقة مدير)")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setModal(True)
        self.amount = 0
        self.reason = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setSpacing(12)
        layout.addLayout(form)

        def _configure_line(widget):
            widget.setMinimumWidth(260)
            widget.setMinimumHeight(34)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if isinstance(widget, QLineEdit):
                widget.setStyleSheet("padding: 6px 10px;")

        self.sp = QSpinBox()
        self.sp.setRange(0, 10_000_000)
        self.sp.setSingleStep(1)
        self.sp.setSuffix(" ج.م")
        _configure_line(self.sp)
        form.addRow("مبلغ الخصم (بالجنيه):", self.sp)

        self.rea = QLineEdit()
        self.rea.setPlaceholderText("مثال: موافقة المدير على خصم خاص")
        _configure_line(self.rea)
        form.addRow("السبب:", self.rea)

        self.u = QLineEdit()
        self.u.setPlaceholderText("admin")
        _configure_line(self.u)
        form.addRow("اسم مستخدم المدير:", self.u)

        self.p = QLineEdit()
        self.p.setEchoMode(QLineEdit.EchoMode.Password)
        _configure_line(self.p)
        form.addRow("كلمة المرور:", self.p)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        cancel = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        ok.setText("تطبيق")
        cancel.setText("إلغاء")
        layout.addWidget(buttons)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)

    def _apply(self):
        user = authenticate(self.u.text().strip(), self.p.text())
        if not user or user.role != "admin":
            QMessageBox.warning(self, "مرفوض", "بيانات المدير غير صحيحة."); return
        self.amount = int(self.sp.value()); self.reason = self.rea.text().strip()
        self.accept()
