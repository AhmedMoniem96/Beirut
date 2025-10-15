from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from PyQt6.QtCore import Qt
from ..core.db import get_conn
from ..core.auth import set_secret_key
from .create_user_dialog import CreateUserDialog
from .common.branding import get_accent_color, get_text_color

class AdminUsersDialog(QDialog):
    def __init__(self, admin_user: str):
        super().__init__()
        self.setWindowTitle("إدارة حسابات الطاقم")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.admin_user = admin_user

        accent = get_accent_color()
        text = get_text_color()
        self.setMinimumWidth(520)
        self.setStyleSheet(
            "\n".join(
                [
                    "QDialog { background-color: rgba(19,12,8,0.92); color: %s; border-radius: 28px; }" % text,
                    "QFrame#Card { background-color: rgba(12,7,4,0.78); border-radius: 24px; border: 1px solid rgba(255,255,255,0.08); padding: 24px 28px; }",
                    "QLabel#Title { font-size: 16pt; font-weight: 800; margin-bottom: 8px; text-align: center; }",
                    "QLabel#Feedback { border-radius: 14px; padding: 10px 14px; background-color: rgba(0,0,0,0.18); font-weight: 600; }",
                    "QLabel#Feedback[kind=error] { background-color: rgba(178, 70, 70, 0.85); color: #FFEDEA; }",
                    "QLabel#Feedback[kind=success] { background-color: rgba(72,160,132,0.85); color: #F1FFF9; }",
                    "QComboBox, QLineEdit { background-color: rgba(255,255,255,0.95); color: #2A170C; border-radius: 14px; padding: 10px 14px; font-size: 11.5pt; }",
                    "QComboBox:focus, QLineEdit:focus { border: 2px solid %s; }" % accent,
                    "QPushButton { background-color: %s; color: #1B0F08; border-radius: 18px; padding: 12px 26px; font-weight: 700; letter-spacing: 0.4px; }"
                    % accent,
                    "QPushButton[class=\"link\"] { background-color: transparent; color: %s; border: none; text-decoration: underline; font-weight: 600; }"
                    % accent,
                    "QPushButton[class=\"flat\"] { background-color: transparent; color: %s; border: 1px solid %s; }"
                    % (accent, accent),
                    "QPushButton[class=\"flat\"]:hover { background-color: rgba(255,255,255,0.1); }",
                ]
            )
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(16)

        title = QLabel("تحكم بصلاحيات ومفاتيح الطاقم")
        title.setObjectName("Title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(title)

        self.feedback = QLabel()
        self.feedback.setObjectName("Feedback")
        self.feedback.setVisible(False)
        self.feedback.setWordWrap(True)
        root.addWidget(self.feedback)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(16)

        self.users = QComboBox()
        self.users.setMinimumWidth(320)
        form.addRow("الموظف", self.users)

        self.key = QLineEdit()
        self.key.setPlaceholderText("المفتاح السري الجديد")
        form.addRow("المفتاح السري", self.key)

        card_layout.addLayout(form)

        links = QHBoxLayout()
        links.addStretch(1)
        self.btn_create = QPushButton("إضافة مستخدم جديد")
        self.btn_create.setProperty("class", "link")
        links.addWidget(self.btn_create)
        card_layout.addLayout(links)

        root.addWidget(card)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.btn_save = QPushButton("حفظ المفتاح")
        self.btn_close = QPushButton("إغلاق")
        self.btn_close.setProperty("class", "flat")
        actions.addWidget(self.btn_save, 2)
        actions.addWidget(self.btn_close, 1)
        root.addLayout(actions)

        self.btn_save.clicked.connect(self._save)
        self.btn_close.clicked.connect(self.accept)
        self.btn_create.clicked.connect(self._create_user)

        self._refresh_users()

    def _cashiers(self):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE role='cashier' ORDER BY username")
        names = [r["username"] for r in cur.fetchall()]
        conn.close()
        return names

    def _save(self):
        user = self.users.currentText().strip()
        key = self.key.text().strip()
        if not user or not key:
            self._show_feedback("اختر المستخدم وأدخل المفتاح السري لتحديثه.", kind="error")
            return
        set_secret_key(self.admin_user, user, key)
        self._show_feedback("تم تحديث المفتاح السري بنجاح.", kind="success")
        self.key.clear()

    def _refresh_users(self, select: str | None = None):
        names = self._cashiers()
        current = select or (self.users.currentText() if self.users.count() else "")
        self.users.blockSignals(True)
        self.users.clear()
        for name in names:
            self.users.addItem(name)
        if current:
            idx = self.users.findText(current)
            if idx >= 0:
                self.users.setCurrentIndex(idx)
        self.users.blockSignals(False)

    def _show_feedback(self, text: str, kind: str = "info"):
        self.feedback.setText(text)
        self.feedback.setProperty("kind", kind)
        self.feedback.setVisible(True)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)

    def _create_user(self):
        dlg = CreateUserDialog(self, admin_hint=self.admin_user)
        if dlg.exec() == dlg.DialogCode.Accepted:
            created = dlg.get_created_username()
            if created:
                self._refresh_users(select=created)
                self._show_feedback("تم إنشاء المستخدم الجديد ويمكنك تعيين مفتاحه الآن.", kind="success")
