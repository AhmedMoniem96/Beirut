from PyQt6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QFrame,
)
from PyQt6.QtCore import Qt

from ..core.auth import authenticate, create_user, UsernameExistsError
from .common.branding import get_accent_color
from .theme import (
    DSAlert,
    DSButton,
    DSModal,
    DSSelect,
    DSTextField,
    SPACING,
    apply_typography,
    design_system_stylesheet,
)


class CreateUserDialog(DSModal):
    """Dialog that allows managers to create a new POS user on the fly."""

    def __init__(self, parent=None, admin_hint: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("إنشاء مستخدم جديد")
        self.setMinimumWidth(560)
        self.setStyleSheet(design_system_stylesheet(get_accent_color()))

        root = QVBoxLayout(self)
        root.setSpacing(SPACING.lg)
        root.setContentsMargins(SPACING.lg, SPACING.lg, SPACING.lg, SPACING.lg)

        title = QLabel("أضف موظفًا جديدًا للنظام بخطوات بسيطة")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        apply_typography(title, "title")
        root.addWidget(title)

        self.feedback = DSAlert("", severity="info")
        self.feedback.setVisible(False)
        root.addWidget(self.feedback)

        admin_frame = self._build_admin_section(admin_hint)
        root.addWidget(admin_frame)

        user_frame = self._build_user_section()
        root.addWidget(user_frame)

        actions = QHBoxLayout()
        actions.setSpacing(SPACING.md)
        self.btn_create = DSButton("إنشاء المستخدم")
        cancel = DSButton("إغلاق", variant="secondary")
        cancel.clicked.connect(self.reject)
        self.btn_create.clicked.connect(self._on_create)
        actions.addWidget(self.btn_create, 1)
        actions.addWidget(cancel, 1)
        root.addLayout(actions)

        self._created_username: str | None = None

    def _build_admin_section(self, admin_hint: str | None):
        frame = QFrame()
        frame.setObjectName("SectionCard")
        layout = QVBoxLayout(frame)
        layout.setSpacing(SPACING.sm)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)

        label = QLabel("تحقق المدير")
        apply_typography(label, "title")
        layout.addWidget(label)

        form = QFormLayout()
        form.setFormAlignment(Qt.AlignmentFlag.AlignRight)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(SPACING.md)

        self.admin_username = DSTextField("اسم المدير")
        if admin_hint:
            self.admin_username.setText(admin_hint)
            self.admin_username.setReadOnly(True)
        form.addRow("اسم المدير", self.admin_username)

        self.admin_password = DSTextField("كلمة مرور المدير")
        self.admin_password.setEchoMode(self.admin_password.EchoMode.Password)
        form.addRow("كلمة المرور", self.admin_password)

        layout.addLayout(form)
        return frame

    def _build_user_section(self):
        frame = QFrame()
        frame.setObjectName("SectionCard")
        layout = QVBoxLayout(frame)
        layout.setSpacing(SPACING.sm)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)

        label = QLabel("بيانات الموظف")
        apply_typography(label, "title")
        layout.addWidget(label)

        form = QFormLayout()
        form.setSpacing(SPACING.md)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.username = DSTextField("اسم المستخدم الجديد")
        form.addRow("اسم المستخدم", self.username)

        self.password = DSTextField("كلمة المرور")
        self.password.setEchoMode(self.password.EchoMode.Password)
        form.addRow("كلمة المرور", self.password)

        self.password_confirm = DSTextField("تأكيد كلمة المرور")
        self.password_confirm.setEchoMode(self.password_confirm.EchoMode.Password)
        form.addRow("تأكيد", self.password_confirm)

        self.role = DSSelect()
        self.role.addItem("كاشير", "cashier")
        self.role.addItem("مدير", "admin")
        form.addRow("الصلاحيات", self.role)

        self.secret_key = DSTextField("المفتاح السري (اختياري)")
        form.addRow("مفتاح سري", self.secret_key)

        layout.addLayout(form)
        return frame

    # Helpers ---------------------------------------------------------------
    def _set_feedback(self, text: str, kind: str = "info"):
        self.feedback.setVisible(True)
        self.feedback.setText(text)
        self.feedback.set_severity(kind if kind in {"success", "warning", "danger"} else "info")

    def _clear_feedback(self):
        self.feedback.setVisible(False)
        self.feedback.setText("")

    def _on_create(self):
        self._clear_feedback()

        admin_username = self.admin_username.text().strip()
        admin_password = self.admin_password.text()
        if not admin_username or not admin_password:
            self._set_feedback("أدخل بيانات المدير للموافقة على الإضافة.", "danger")
            return

        admin = authenticate(admin_username, admin_password)
        if not admin or admin.role != "admin":
            self._set_feedback("بيانات المدير غير صحيحة أو لا يملك صلاحيات كافية.", "danger")
            return

        username = self.username.text().strip()
        password = self.password.text()
        confirm = self.password_confirm.text()
        if not username or not password:
            self._set_feedback("أدخل اسم المستخدم وكلمة المرور للموظف الجديد.", "warning")
            return
        if password != confirm:
            self._set_feedback("تأكد أن كلمتي المرور متطابقتان.", "warning")
            return

        role = self.role.currentData()
        secret = self.secret_key.text().strip()

        try:
            user = create_user(username, password, role=role, secret_key=secret)
        except UsernameExistsError as exc:
            self._set_feedback(str(exc), "danger")
            return
        except ValueError as exc:
            self._set_feedback(str(exc), "danger")
            return

        self._created_username = user.username
        self._set_feedback("تم إنشاء الحساب الجديد بنجاح!", "success")
        self.btn_create.setEnabled(False)
        self.accept()

    # API ------------------------------------------------------------------
    def get_created_username(self) -> str | None:
        return self._created_username
