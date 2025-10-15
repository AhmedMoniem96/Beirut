from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt

from ..core.auth import authenticate, create_user, UsernameExistsError
from .common.branding import get_accent_color, get_text_color


class CreateUserDialog(QDialog):
    """Dialog that allows managers to create a new POS user on the fly."""

    def __init__(self, parent=None, admin_hint: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("إنشاء مستخدم جديد")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumWidth(520)

        accent = get_accent_color()
        text = get_text_color()
        self.setStyleSheet(
            "\n".join(
                [
                    "QDialog { background-color: rgba(22,13,8,0.94); color: %s; border-radius: 24px; }" % text,
                    "QGroupBox { border: none; margin-top: 12px; }",
                    "QLineEdit, QComboBox { background-color: rgba(255,255,255,0.95); border-radius: 14px; padding: 10px 14px; font-size: 11pt; color: #2A170C; }",
                    "QLineEdit:focus, QComboBox:focus { border: 2px solid %s; }" % accent,
                    "QPushButton { background-color: %s; color: #1B0F08; border-radius: 18px; padding: 12px 28px; font-weight: 700; letter-spacing: 0.4px; }" % accent,
                    "QPushButton[class=\"outline\"] { background-color: transparent; color: %s; border: 1px solid %s; }"
                    % (accent, accent),
                    "QPushButton[class=\"outline\"]:hover { background-color: rgba(0,0,0,0.1); }",
                    "QPushButton#Link { background-color: transparent; color: %s; border: none; text-decoration: underline; font-weight: 600; }"
                    % accent,
                    "QLabel#Feedback { border-radius: 14px; padding: 10px 14px; background-color: rgba(0,0,0,0.25); color: %s; }"
                    % text,
                    "QLabel#Feedback[kind=error] { background-color: rgba(178,70,70,0.85); color: #FFEDEA; font-weight: 700; }",
                    "QLabel#Feedback[kind=success] { background-color: rgba(72,160,132,0.85); color: #F1FFF9; font-weight: 700; }",
                    "QFrame#Section { background-color: rgba(255,255,255,0.04); border-radius: 20px; padding: 18px 22px; border: 1px solid rgba(255,255,255,0.08); }",
                ]
            )
        )

        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(28, 28, 28, 28)

        title = QLabel("أضف موظفًا جديدًا للنظام بخطوات بسيطة")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 15pt; font-weight: 800;")
        root.addWidget(title)

        self.feedback = QLabel()
        self.feedback.setObjectName("Feedback")
        self.feedback.setVisible(False)
        self.feedback.setWordWrap(True)
        root.addWidget(self.feedback)

        admin_frame = self._build_admin_section(admin_hint)
        root.addWidget(admin_frame)

        user_frame = self._build_user_section()
        root.addWidget(user_frame)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.btn_create = QPushButton("إنشاء المستخدم")
        cancel = QPushButton("إغلاق")
        cancel.setProperty("class", "outline")
        cancel.clicked.connect(self.reject)
        self.btn_create.clicked.connect(self._on_create)
        actions.addWidget(self.btn_create, 1)
        actions.addWidget(cancel, 1)
        root.addLayout(actions)

        self._created_username: str | None = None

    def _build_admin_section(self, admin_hint: str | None):
        from PyQt6.QtWidgets import QFrame

        frame = QFrame()
        frame.setObjectName("Section")
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)

        label = QLabel("تحقق المدير")
        label.setStyleSheet("font-size: 12pt; font-weight: 700;")
        layout.addWidget(label)

        form = QFormLayout()
        form.setFormAlignment(Qt.AlignmentFlag.AlignRight)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(12)

        self.admin_username = QLineEdit()
        self.admin_username.setPlaceholderText("اسم المدير")
        if admin_hint:
            self.admin_username.setText(admin_hint)
            self.admin_username.setReadOnly(True)
        form.addRow("اسم المدير", self.admin_username)

        self.admin_password = QLineEdit()
        self.admin_password.setPlaceholderText("كلمة مرور المدير")
        self.admin_password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("كلمة المرور", self.admin_password)

        layout.addLayout(form)
        return frame

    def _build_user_section(self):
        from PyQt6.QtWidgets import QFrame

        frame = QFrame()
        frame.setObjectName("Section")
        layout = QVBoxLayout(frame)
        layout.setSpacing(12)
        layout.setContentsMargins(8, 8, 8, 8)

        label = QLabel("بيانات الموظف")
        label.setStyleSheet("font-size: 12pt; font-weight: 700;")
        layout.addWidget(label)

        form = QFormLayout()
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.username = QLineEdit()
        self.username.setPlaceholderText("اسم المستخدم الجديد")
        form.addRow("اسم المستخدم", self.username)

        self.password = QLineEdit()
        self.password.setPlaceholderText("كلمة المرور")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("كلمة المرور", self.password)

        self.password_confirm = QLineEdit()
        self.password_confirm.setPlaceholderText("تأكيد كلمة المرور")
        self.password_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("تأكيد", self.password_confirm)

        self.role = QComboBox()
        self.role.addItem("كاشير", "cashier")
        self.role.addItem("مدير", "admin")
        form.addRow("الصلاحيات", self.role)

        self.secret_key = QLineEdit()
        self.secret_key.setPlaceholderText("المفتاح السري (اختياري)")
        form.addRow("مفتاح سري", self.secret_key)

        layout.addLayout(form)
        return frame

    # Helpers ---------------------------------------------------------------
    def _set_feedback(self, text: str, kind: str = "info"):
        self.feedback.setText(text)
        self.feedback.setProperty("kind", kind)
        self.feedback.setVisible(True)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

    def _clear_feedback(self):
        self.feedback.setVisible(False)
        self.feedback.setText("")

    def _on_create(self):
        self._clear_feedback()

        admin_username = self.admin_username.text().strip()
        admin_password = self.admin_password.text()
        if not admin_username or not admin_password:
            self._set_feedback("أدخل بيانات المدير للموافقة على الإضافة.", "error")
            return

        admin = authenticate(admin_username, admin_password)
        if not admin or admin.role != "admin":
            self._set_feedback("بيانات المدير غير صحيحة أو لا يملك صلاحيات كافية.", "error")
            return

        username = self.username.text().strip()
        password = self.password.text()
        confirm = self.password_confirm.text()
        if not username or not password:
            self._set_feedback("أدخل اسم المستخدم وكلمة المرور للموظف الجديد.", "error")
            return
        if password != confirm:
            self._set_feedback("تأكد أن كلمتي المرور متطابقتان.", "error")
            return

        role = self.role.currentData()
        secret = self.secret_key.text().strip()

        try:
            user = create_user(username, password, role=role, secret_key=secret)
        except UsernameExistsError as exc:
            self._set_feedback(str(exc), "error")
            return
        except ValueError as exc:
            self._set_feedback(str(exc), "error")
            return

        self._created_username = user.username
        self._set_feedback("تم إنشاء الحساب الجديد بنجاح!", "success")
        self.btn_create.setEnabled(False)
        self.accept()

    # API ------------------------------------------------------------------
    def get_created_username(self) -> str | None:
        return self._created_username
