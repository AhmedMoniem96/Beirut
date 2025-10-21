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
from ..core.bus import bus
from ..services import texts
from ..services import settings as settings_service

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setObjectName("LoginDialog")
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
        brand_layout.setContentsMargins(18, 24, 18, 24)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setMinimumHeight(220)
        self.logo.setObjectName("LoginLogo")
        self._apply_logo()
        brand_layout.addWidget(self.logo)

        self.brand_title = QLabel()
        self.brand_title.setObjectName("BrandTitle")
        self.brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_title.setStyleSheet("font-size: 30px; font-weight: 700;")
        brand_layout.addWidget(self.brand_title)

        self.hero = QLabel()
        self.hero.setObjectName("LoginHero")
        self.hero.setWordWrap(True)
        self.hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero.setMaximumWidth(420)
        self.hero.setStyleSheet("font-size: 17px; line-height: 1.5;")
        brand_layout.addWidget(self.hero)

        self.hero_hint = QLabel()
        self.hero_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_hint.setObjectName("HeroHint")
        self.hero_hint.setWordWrap(True)
        self.hero_hint.setMaximumWidth(420)
        self.hero_hint.setStyleSheet("font-size: 15px; line-height: 1.5; color: #f0ebe2;")
        brand_layout.addWidget(self.hero_hint)

        card_layout.addWidget(brand_frame, 3)

        # Form column ------------------------------------------------------
        form_frame = QFrame()
        form_frame.setObjectName("LoginForm")
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(18)
        form_layout.setContentsMargins(28, 28, 28, 28)

        self.form_title = QLabel()
        self.form_title.setObjectName("FormTitle")
        self.form_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        form_layout.addWidget(self.form_title)

        self.msg = QLabel()
        self.msg.setObjectName("LoginHint")
        self.msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg.setWordWrap(True)
        form_layout.addWidget(self.msg)

        self.u = QLineEdit()
        self.u.setMinimumWidth(360)
        self.u.setFixedHeight(52)
        self.u.setClearButtonEnabled(True)
        self.u.setStyleSheet("padding: 10px 14px; font-size: 16px;")
        form_layout.addWidget(self.u)

        self.p = QLineEdit()
        self.p.setEchoMode(QLineEdit.EchoMode.Password)
        self.p.setFixedHeight(52)
        self.p.setClearButtonEnabled(True)
        self.p.setStyleSheet("padding: 10px 14px; font-size: 16px;")
        form_layout.addWidget(self.p)

        row = QHBoxLayout()
        row.setSpacing(12)
        self.btn = QPushButton()
        self.forgot = QPushButton()
        self.forgot.setProperty("class", "link")
        row.addWidget(self.btn, 2)
        row.addWidget(self.forgot, 1)
        form_layout.addLayout(row)

        self.create_user = QPushButton()
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

        self._apply_texts()
        bus.subscribe("ui_texts_changed", self._apply_texts)
        bus.subscribe("client_branding_changed", self._apply_texts)
        bus.subscribe("client_branding_changed", self._apply_logo)

    def _do_login(self):
        user = authenticate(self.u.text().strip(), self.p.text())
        if user:
            self._user = user
            self.msg.setStyleSheet("")
            self.accept()
        else:
            self.msg.setText(texts.get("login.error"))
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
                self.msg.setText(texts.get("login.create_success"))
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
            self.logo.setText(settings_service.get_client_name())
            self.logo.setStyleSheet("font-size: 32pt; font-weight: 800; letter-spacing: 1px;")

    def _apply_texts(self):
        client_name = settings_service.get_client_name()
        self.setWindowTitle(texts.get("login.window_title", client_name=client_name))
        self.brand_title.setText(texts.get("login.brand_title", client_name=client_name))
        self.hero.setText(texts.get("login.hero"))
        self.hero_hint.setText(texts.get("login.hero_hint"))
        self.form_title.setText(texts.get("login.form_title"))
        self.msg.setText(texts.get("login.form_hint"))
        self.msg.setStyleSheet("")
        self.u.setPlaceholderText(texts.get("login.username_placeholder"))
        self.p.setPlaceholderText(texts.get("login.password_placeholder"))
        self.btn.setText(texts.get("login.submit"))
        self.forgot.setText(texts.get("login.forgot"))
        self.create_user.setText(texts.get("login.create_user"))
