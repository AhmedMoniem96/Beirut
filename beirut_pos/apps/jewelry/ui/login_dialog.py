"""Login dialog for Jewelry app."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..services.auth import authenticate_user
from ..services.i18n import get_ui_language, t
from ..services.session import get_bootstrap_warning, set_current_user
from ..services.settings import load_gallery_settings
from .create_user_dialog import CreateUserDialog
from .forgot_password_dialog import ForgotPasswordDialog
from .styles import login_stylesheet


class LoginDialog(QDialog):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("LoginDialog")
        self._language = get_ui_language()
        self.setWindowTitle(t("login.window_title", language=self._language))
        self.setModal(True)
        self.setMinimumWidth(720)

        background_image = self._resolve_background_image()
        self.setStyleSheet(login_stylesheet(background_image))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(0)

        brand_panel = self._build_brand_panel()
        form_panel = self._build_form_panel()

        layout.addWidget(brand_panel, stretch=5)
        layout.addWidget(form_panel, stretch=4)

        self.forgot_btn.clicked.connect(self._open_forgot_password)
        self.new_user_btn.clicked.connect(self._open_create_user)
        self.apply_language(self._language)

    def _build_link_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFlat(True)
        button.setObjectName("LinkButton")
        return button

    def _build_brand_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("BrandPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(32, 32, 32, 32)
        panel_layout.setSpacing(18)

        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        logo_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        logo = self._load_logo_pixmap()
        if logo:
            logo_label.setPixmap(logo)
        panel_layout.addWidget(logo_label)

        hero = QLabel()
        hero.setObjectName("BrandHero")
        hero.setWordWrap(True)
        panel_layout.addWidget(hero)
        self.hero_label = hero

        tagline = QLabel()
        tagline.setObjectName("BrandTagline")
        tagline.setWordWrap(True)
        panel_layout.addWidget(tagline)
        self.tagline_label = tagline

        panel_layout.addStretch()
        return panel

    def _build_form_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("FormPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(32, 32, 32, 32)
        panel_layout.setSpacing(16)

        title = QLabel()
        title.setObjectName("FormTitle")
        panel_layout.addWidget(title)
        self.title_label = title

        self.warning_label = QLabel()
        self.warning_label.setWordWrap(True)
        self.warning_label.setObjectName("MutedLabel")
        warning_text = get_bootstrap_warning()
        if warning_text:
            self.warning_label.setText(warning_text)
            self.warning_label.setStyleSheet("color: #b22b2b; font-weight: 600;")
            panel_layout.addWidget(self.warning_label)

        form_frame = QWidget()
        form_layout = QFormLayout(form_frame)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        form_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form_layout.setHorizontalSpacing(12)
        form_layout.setVerticalSpacing(12)
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.returnPressed.connect(self._attempt_login)
        self.username_label = QLabel()
        self.password_label = QLabel()
        form_layout.addRow(self.username_label, self.username_input)
        form_layout.addRow(self.password_label, self.password_input)
        panel_layout.addWidget(form_frame)

        self.message_label = QLabel()
        self.message_label.setObjectName("MutedLabel")
        panel_layout.addWidget(self.message_label)

        actions = QHBoxLayout()
        actions.addStretch()
        self.login_btn = QPushButton()
        self.login_btn.setObjectName("PrimaryButton")
        self.login_btn.clicked.connect(self._attempt_login)
        actions.addWidget(self.login_btn)
        panel_layout.addLayout(actions)

        links = QHBoxLayout()
        self.forgot_btn = self._build_link_button("")
        self.new_user_btn = self._build_link_button("")
        links.addStretch()
        links.addWidget(self.forgot_btn)
        links.addWidget(self.new_user_btn)
        links.addStretch()
        panel_layout.addLayout(links)

        panel_layout.addStretch()
        return panel

    def apply_language(self, language: str) -> None:
        self._language = language
        self.setWindowTitle(t("login.window_title", language=language))
        self.hero_label.setText(t("login.hero", language=language))
        self.tagline_label.setText(t("login.tagline", language=language))
        self.title_label.setText(t("login.title", language=language))
        self.username_label.setText(t("login.username", language=language))
        self.password_label.setText(t("login.password", language=language))
        self.login_btn.setText(t("login.login_button", language=language))
        self.forgot_btn.setText(t("login.forgot_password", language=language))
        self.new_user_btn.setText(t("login.new_user", language=language))

    def _resolve_background_image(self) -> Path | None:
        root = Path(__file__).resolve().parents[4]
        assets_dir = root / "assets"
        for name in (
            "login_background.jpg",
            "login_background.jpeg",
            "login_background.png",
            "background.jpg",
            "background.jpeg",
            "background.png",
        ):
            candidate = assets_dir / name
            if candidate.exists():
                return candidate
        return None

    def _load_logo_pixmap(self) -> QPixmap | None:
        def _scaled_pixmap(path: Path) -> QPixmap | None:
            if not path.exists():
                return None
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                return None
            return pixmap.scaledToHeight(
                120,
                Qt.TransformationMode.SmoothTransformation,
            )

        settings = load_gallery_settings()
        if settings.logo_path:
            custom_path = Path(settings.logo_path).expanduser()
            custom_pixmap = _scaled_pixmap(custom_path)
            if custom_pixmap:
                return custom_pixmap

        root = Path(__file__).resolve().parents[4]
        logo_path = root / "assets" / "logo.jpeg"
        return _scaled_pixmap(logo_path)

    def _set_message(self, message: str, *, kind: str = "info") -> None:
        palette = {
            "info": "#6e6a64",
            "error": "#b22b2b",
            "success": "#2e7d32",
        }
        self.message_label.setStyleSheet(f"color: {palette.get(kind, '#6e6a64')};")
        self.message_label.setText(message)

    def _attempt_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        result = authenticate_user(username, password)
        if result.user:
            set_current_user(result.user)
            if get_bootstrap_warning():
                QMessageBox.warning(
                    self,
                    t("login.default_admin_title", language=self._language),
                    get_bootstrap_warning(),
                )
            self.accept()
            return
        self._set_message(result.message, kind="error")

    def _open_forgot_password(self) -> None:
        dialog = ForgotPasswordDialog(self)
        dialog.exec()
        if dialog.result_message:
            kind = "success" if dialog.success else "error"
            self._set_message(dialog.result_message, kind=kind)
            self.password_input.clear()

    def _open_create_user(self) -> None:
        dialog = CreateUserDialog(self)
        dialog.exec()
        if dialog.result_message:
            kind = "success" if dialog.success else "error"
            self._set_message(dialog.result_message, kind=kind)
            self.password_input.clear()
        if dialog.created_username:
            self.username_input.setText(dialog.created_username)
