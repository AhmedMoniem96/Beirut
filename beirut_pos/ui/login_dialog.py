from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLineEdit,
    QPushButton,
    QLabel,
    QHBoxLayout,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from ..core.auth import authenticate
from .forgot_password_dialog import ForgotPasswordDialog
from .common.branding import get_logo_pixmap, get_logo_icon, build_login_stylesheet

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setObjectName("LoginDialog")
        self.setWindowTitle("تسجيل الدخول — Beirut POS")
        self._user = None
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumSize(720, 520)
        self.resize(960, 600)
        self.setStyleSheet(build_login_stylesheet())

        icon = get_logo_icon(128)
        if icon:
            self.setWindowIcon(icon)

        root = QVBoxLayout(self)
        root.setContentsMargins(60, 60, 60, 60)
        root.setSpacing(32)
        root.addStretch(1)

        card = QFrame()
        card.setObjectName("LoginCard")
        card_v = QVBoxLayout(card)
        card_v.setSpacing(18)
        card_v.setContentsMargins(10, 10, 10, 10)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setMinimumHeight(160)
        self._apply_logo()
        card_v.addWidget(self.logo, alignment=Qt.AlignmentFlag.AlignCenter)

        hero = QLabel("أهلاً بكم في مقهى بيروت — حيث يلتقي الذوق الرفيع بالخدمة السريعة")
        hero.setObjectName("LoginHero")
        hero.setWordWrap(True)
        hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_v.addWidget(hero)

        self.msg = QLabel("من فضلك أدخل بيانات الدخول")
        self.msg.setObjectName("LoginHint")
        self.msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_v.addWidget(self.msg)

        self.u = QLineEdit(); self.u.setPlaceholderText("اسم المستخدم")
        self.p = QLineEdit(); self.p.setPlaceholderText("كلمة المرور")
        self.p.setEchoMode(QLineEdit.EchoMode.Password)
        card_v.addWidget(self.u)
        card_v.addWidget(self.p)

        row = QHBoxLayout()
        row.setSpacing(18)
        self.btn = QPushButton("دخول")
        self.forgot = QPushButton("نسيت كلمة المرور؟")
        self.forgot.setFlat(True)
        self.forgot.setProperty("class", "link")
        row.addWidget(self.btn, 1); row.addWidget(self.forgot, 1)
        card_v.addLayout(row)

        root.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addStretch(2)

        self.btn.clicked.connect(self._do_login)
        self.p.returnPressed.connect(self._do_login)
        self.forgot.clicked.connect(self._open_forgot)

    def _do_login(self):
        user = authenticate(self.u.text().strip(), self.p.text())
        if user:
            self._user = user
            self.msg.setStyleSheet("")
            self.accept()
        else:
            self.msg.setText("بيانات غير صحيحة. حاول مرة أخرى.")
            self.msg.setStyleSheet("color: #FFB4A2; font-weight: 600;")

    def _open_forgot(self):
        dlg = ForgotPasswordDialog()
        dlg.exec()

    def get_user(self): return self._user

    def _apply_logo(self):
        pix = get_logo_pixmap(220)
        if pix:
            scaled = pix.scaledToHeight(220, Qt.TransformationMode.SmoothTransformation)
            self.logo.setPixmap(scaled)
            self.logo.setText("")
            self.logo.setStyleSheet("")
        else:
            self.logo.clear()
            self.logo.setText("Beirut POS")
            self.logo.setStyleSheet("font-size: 26pt; font-weight: 700; letter-spacing: 1px;")
