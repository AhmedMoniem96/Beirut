from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QFrame,
    QLineEdit,
    QSizePolicy,
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
from .theme import (
    DSButton,
    DSFormField,
    DSLinkButton,
    SPACING,
    apply_typography,
)

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
        root.setContentsMargins(SPACING.xl * 2 + SPACING.xs, SPACING.xl + SPACING.sm, SPACING.xl * 2 + SPACING.xs, SPACING.xl + SPACING.sm)
        root.setSpacing(SPACING.lg)
        root.addStretch(1)

        card = QFrame()
        card.setObjectName("LoginCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(SPACING.xl + SPACING.xs, SPACING.lg + SPACING.sm, SPACING.xl + SPACING.xs, SPACING.lg + SPACING.sm)
        card_layout.setSpacing(SPACING.xl)

        # Brand column -----------------------------------------------------
        brand_frame = QFrame()
        brand_frame.setObjectName("BrandColumn")
        brand_layout = QVBoxLayout(brand_frame)
        brand_layout.setSpacing(SPACING.md + SPACING.xs)
        brand_layout.setContentsMargins(SPACING.md, SPACING.lg, SPACING.md, SPACING.lg)

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo.setMinimumHeight(220)
        self.logo.setObjectName("LoginLogo")
        self._apply_logo()
        brand_layout.addWidget(self.logo)

        self.brand_title = QLabel()
        self.brand_title.setObjectName("BrandTitle")
        self.brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_typography(self.brand_title, "display")
        brand_layout.addWidget(self.brand_title)

        self.hero = QLabel()
        self.hero.setObjectName("LoginHero")
        self.hero.setWordWrap(True)
        self.hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero.setMaximumWidth(420)
        apply_typography(self.hero, "title")
        brand_layout.addWidget(self.hero)

        self.hero_hint = QLabel()
        self.hero_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hero_hint.setObjectName("HeroHint")
        self.hero_hint.setWordWrap(True)
        self.hero_hint.setMaximumWidth(420)
        apply_typography(self.hero_hint, "body")
        brand_layout.addWidget(self.hero_hint)

        card_layout.addWidget(brand_frame, 3)

        # Form column ------------------------------------------------------
        form_frame = QFrame()
        form_frame.setObjectName("LoginForm")
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(SPACING.md + SPACING.xs)
        form_layout.setContentsMargins(SPACING.lg, SPACING.lg, SPACING.lg, SPACING.lg)

        self.form_title = QLabel()
        self.form_title.setObjectName("FormTitle")
        self.form_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        apply_typography(self.form_title, "title")
        form_layout.addWidget(self.form_title)

        self.msg = QLabel()
        self.msg.setObjectName("LoginHint")
        self.msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg.setWordWrap(True)
        form_layout.addWidget(self.msg)

        self.u, self.u_field = self._build_login_input(
            "اسم المستخدم",
            helper="أدخل اسم المستخدم الخاص بك.",
            required=True,
        )
        self.u_field.setProperty("data-radius", 18)
        form_layout.addWidget(self.u_field)

        self.p, self.p_field = self._build_login_input(
            "كلمة المرور",
            helper="اكتب كلمة المرور ثم اضغط دخول.",
            required=True,
        )
        self.p.setEchoMode(self.p.EchoMode.Password)
        self.p_field.setProperty("data-radius", 18)
        form_layout.addWidget(self.p_field)

        row = QHBoxLayout()
        row.setSpacing(SPACING.md)
        self.btn = DSButton()
        self.forgot = DSLinkButton()
        row.addWidget(self.btn, 2)
        row.addWidget(self.forgot, 1)
        form_layout.addLayout(row)

        self.create_user = DSLinkButton()
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

    def _build_login_input(self, label: str, *, helper: str, required: bool):
        frame = QFrame()
        frame.setObjectName("fieldFrame")
        frame.setFixedHeight(48)
        frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        line_edit = QLineEdit()
        line_edit.setObjectName("fieldEdit")
        line_edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        line_edit.setClearButtonEnabled(False)
        line_edit.setFixedHeight(48)
        line_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        line_edit.setTextMargins(16, 0, 16, 0)
        line_edit.setStyleSheet("background: red;")

        inner = QHBoxLayout(frame)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.setSpacing(0)
        inner.addWidget(line_edit, alignment=Qt.AlignmentFlag.AlignVCenter)
        print(
            "USER:",
            line_edit.objectName(),
            line_edit.size(),
            line_edit.minimumHeight(),
            line_edit.styleSheet(),
        )

        wrapper = QFrame()
        wrapper.setFocusProxy(line_edit)
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(0)
        wrapper_layout.addWidget(frame)

        field = DSFormField(label, wrapper, helper=helper, required=required)
        return line_edit, field

    def _set_message_state(self, state: str = "info"):
        self.msg.setProperty("state", state)
        self.msg.style().unpolish(self.msg)
        self.msg.style().polish(self.msg)

        if state == "info":
            self.u_field.clear_status()
            self.p_field.clear_status()

    def _do_login(self):
        self.u_field.clear_status()
        self.p_field.clear_status()
        user = authenticate(self.u.text().strip(), self.p.text())
        if user:
            self._user = user
            self._set_message_state("info")
            self.u_field.mark_success()
            self.p_field.mark_success()
            self.accept()
        else:
            self.msg.setText(texts.get("login.error"))
            self._set_message_state("error")
            self.u_field.mark_error(texts.get("login.error"))
            self.p_field.mark_error(texts.get("login.error"))

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
                self._set_message_state("success")

    def get_user(self): return self._user

    def _apply_logo(self):
        pix = get_logo_pixmap(320)
        if pix:
            scaled = pix.scaledToHeight(260, Qt.TransformationMode.SmoothTransformation)
            self.logo.setPixmap(scaled)
            self.logo.setText("")
        else:
            self.logo.clear()
            self.logo.setText(settings_service.get_client_name())
            apply_typography(self.logo, "display")
            self.logo.setProperty("state", "fallback")

    def _apply_texts(self):
        client_name = settings_service.get_client_name()
        self.setWindowTitle(texts.get("login.window_title", client_name=client_name))
        self.brand_title.setText(texts.get("login.brand_title", client_name=client_name))
        self.hero.setText(texts.get("login.hero"))
        self.hero_hint.setText(texts.get("login.hero_hint"))
        self.form_title.setText(texts.get("login.form_title"))
        self.msg.setText(texts.get("login.form_hint"))
        self._set_message_state("info")
        username_label = texts.get("login.username_label", texts.get("login.username_placeholder"))
        password_label = texts.get("login.password_label", texts.get("login.password_placeholder"))
        self.u_field.label.setText(username_label)
        self.p_field.label.setText(password_label)
        self.u.setPlaceholderText(texts.get("login.username_placeholder"))
        self.p.setPlaceholderText(texts.get("login.password_placeholder"))
        self.u_field.set_helper_text(texts.get("login.username_helper", texts.get("login.form_hint")))
        self.p_field.set_helper_text(texts.get("login.password_helper", texts.get("login.form_hint")))
        self.btn.setText(texts.get("login.submit"))
        self.forgot.setText(texts.get("login.forgot"))
        self.create_user.setText(texts.get("login.create_user"))
