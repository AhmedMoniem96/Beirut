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
from .create_user_dialog import CreateUserDialog
from .common.branding import get_logo_pixmap, get_logo_icon, build_login_stylesheet

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setObjectName("LoginDialog")
        self.setWindowTitle("تسجيل الدخول — Beirut POS")
        self._user = None
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumSize(820, 560)
        self.resize(1080, 640)
        self.setStyleSheet(build_login_stylesheet())

        icon = get_logo_icon(128)
        if icon:
            self.setWindowIcon(icon)

        root = QVBoxLayout(self)
        root.setContentsMargins(72, 64, 72, 64)
        root.setSpacing(24)
        root.addStretch(1)

        card = QFrame()
        card.setObjectName("LoginCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(40, 36, 40, 36)
        card_layout.setSpacing(48)

        # Brand column -----------------------------------------------------
        brand_frame = QFrame()
        brand_frame.setObjectName("BrandColumn")
        brand_layout = QVBoxLayout(brand_frame)
        brand_layout.setSpacing(18)
        brand_layout.setContentsMargins(12, 12, 12, 12)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setMinimumHeight(220)
        self.logo.setObjectName("LoginLogo")
        self._apply_logo()
        brand_layout.addWidget(self.logo)

        brand_title = QLabel("مقهى بيروت")
        brand_title.setObjectName("BrandTitle")
        brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(brand_title)

        hero = QLabel("مرحباً بكم في نظام نقاط البيع الخاص بنا — ترتيب الطلبات أصبح أسهل")
        hero.setObjectName("LoginHero")
        hero.setWordWrap(True)
        hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(hero)

        hero_hint = QLabel("جهز فريقك، تابع الطاولات، وراقب الأداء في نظرة واحدة.")
        hero_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_hint.setObjectName("HeroHint")
        hero_hint.setWordWrap(True)
        brand_layout.addWidget(hero_hint)

        card_layout.addWidget(brand_frame, 3)

        # Form column ------------------------------------------------------
        form_frame = QFrame()
        form_frame.setObjectName("LoginForm")
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(18)
        form_layout.setContentsMargins(28, 28, 28, 28)

        form_title = QLabel("تسجيل الدخول")
        form_title.setObjectName("FormTitle")
        form_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(form_title)

        self.msg = QLabel("أدخل بياناتك للمتابعة")
        self.msg.setObjectName("LoginHint")
        self.msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg.setWordWrap(True)
        form_layout.addWidget(self.msg)

        self.u = QLineEdit()
        self.u.setPlaceholderText("اسم المستخدم")
        self.u.setMinimumWidth(360)
        self.u.setFixedHeight(52)
        self.u.setClearButtonEnabled(True)
        form_layout.addWidget(self.u)

        self.p = QLineEdit()
        self.p.setPlaceholderText("كلمة المرور")
        self.p.setEchoMode(QLineEdit.EchoMode.Password)
        self.p.setFixedHeight(52)
        self.p.setClearButtonEnabled(True)
        form_layout.addWidget(self.p)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.btn = QPushButton("تسجيل الدخول")
        self.forgot = QPushButton("هل نسيت كلمة المرور؟")
        self.forgot.setProperty("class", "link")
        row.addWidget(self.btn, 2)
        row.addWidget(self.forgot, 1)
        form_layout.addLayout(row)

        self.create_user = QPushButton("إنشاء حساب موظف جديد")
        self.create_user.setProperty("class", "link")
        self.create_user.setCursor(Qt.CursorShape.PointingHandCursor)
        form_layout.addWidget(self.create_user, alignment=Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(form_frame, 4)

        root.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        root.addStretch(1)

        self.btn.clicked.connect(self._do_login)
        self.p.returnPressed.connect(self._do_login)
        self.forgot.clicked.connect(self._open_forgot)
        self.create_user.clicked.connect(self._open_create_user)

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

    def _open_create_user(self):
        dlg = CreateUserDialog(self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            new_user = dlg.get_created_username()
            if new_user:
                self.u.setText(new_user)
                self.p.clear()
                self.msg.setText("تم إنشاء الحساب. أدخل كلمة المرور وسجل الدخول.")
                self.msg.setStyleSheet("color: #A7F3D0; font-weight: 600;")

    def get_user(self): return self._user

    def _apply_logo(self):
        pix = get_logo_pixmap(320)
        if pix:
            scaled = pix.scaledToHeight(260, Qt.TransformationMode.SmoothTransformation)
            self.logo.setPixmap(scaled)
            self.logo.setText("")
            self.logo.setStyleSheet("")
        else:
            self.logo.clear()
            self.logo.setText("Beirut POS")
            self.logo.setStyleSheet("font-size: 32pt; font-weight: 800; letter-spacing: 1px;")
