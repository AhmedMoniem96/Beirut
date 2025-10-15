from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QHBoxLayout,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

from ..core.license import LicenseStatus, activate_license, license_status, machine_fingerprint
from .common.branding import (
    get_accent_color,
    get_surface_color,
    get_text_color,
    get_muted_text_color,
)


class LicenseDialog(QDialog):
    """Collect and validate the activation key required to run the POS."""

    def __init__(self, status: LicenseStatus | None = None, fatal: bool = True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تفعيل الترخيص")
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumWidth(640)
        self._fatal = fatal

        accent = get_accent_color()
        text = get_text_color()
        muted = get_muted_text_color()
        surface = get_surface_color()

        self.setStyleSheet(
            "\n".join(
                [
                    "QDialog { background-color: %s; color: %s; border-radius: 28px; }" % (surface, text),
                    "QPlainTextEdit { background-color: rgba(255,255,255,0.94); color: #2B1A12; border-radius: 18px; padding: 14px; font-size: 11.5pt; }",
                    "QPlainTextEdit:focus { border: 2px solid %s; }" % accent,
                    "QPushButton { background-color: %s; color: #1B0F08; border-radius: 20px; padding: 12px 28px; font-weight: 700; letter-spacing: 0.4px; }"
                    % accent,
                    "QPushButton[class=\"outline\"] { background-color: transparent; color: %s; border: 1px solid %s; }"
                    % (accent, accent),
                    "QPushButton[class=\"outline\"]:hover { background-color: rgba(255,255,255,0.08); }",
                    "QLabel#Status[kind=error] { background-color: rgba(178,70,70,0.85); color: #FFEDEA; border-radius: 18px; padding: 14px 18px; font-weight: 700; }",
                    "QLabel#Status[kind=ok] { background-color: rgba(56,148,117,0.85); color: #F2FFF7; border-radius: 18px; padding: 14px 18px; font-weight: 700; }",
                    "QLabel#Status { background-color: rgba(0,0,0,0.18); border-radius: 18px; padding: 14px 18px; font-weight: 600; }",
                    "#FingerprintFrame { background-color: rgba(0,0,0,0.18); border-radius: 18px; padding: 12px 16px; }",
                    "#FingerprintValue { font-family: 'Courier New', 'Cascadia Code', monospace; font-size: 12.5pt; letter-spacing: 1.6px; }",
                    "QLabel#Hint { color: %s; font-size: 10.5pt; }" % muted,
                ]
            )
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(18)

        title = QLabel("فعّل نسختك من Beirut POS")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18pt; font-weight: 800;")
        root.addWidget(title)

        subtitle = QLabel("احصل على مفتاح الترخيص من الدعم، ثم ألصقه هنا لتأمين نسخة المقهى.")
        subtitle.setObjectName("Hint")
        subtitle.setWordWrap(True)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(subtitle)

        self.status_label = QLabel()
        self.status_label.setObjectName("Status")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        fp_frame = QFrame()
        fp_frame.setObjectName("FingerprintFrame")
        fp_layout = QVBoxLayout(fp_frame)
        fp_layout.setContentsMargins(12, 12, 12, 12)
        fp_layout.setSpacing(8)

        fp_title = QLabel("معرّف الجهاز")
        fp_title.setStyleSheet("font-size: 11pt; font-weight: 700;")
        fp_layout.addWidget(fp_title)

        fp_row = QHBoxLayout()
        fp_row.setSpacing(12)

        self.fingerprint_value = QLabel()
        self.fingerprint_value.setObjectName("FingerprintValue")
        fp_row.addWidget(self.fingerprint_value, 1)

        copy_btn = QPushButton("نسخ")
        copy_btn.setProperty("class", "outline")
        copy_btn.clicked.connect(self._copy_fingerprint)
        fp_row.addWidget(copy_btn, 0)

        fp_layout.addLayout(fp_row)

        fp_hint = QLabel("أرسل هذا المعرّف لفريق الدعم ليُنشئ مفتاحًا خاصًا بجهازك.")
        fp_hint.setObjectName("Hint")
        fp_hint.setWordWrap(True)
        fp_layout.addWidget(fp_hint)

        root.addWidget(fp_frame)

        self.license_edit = QPlainTextEdit()
        self.license_edit.setPlaceholderText("ألصق مفتاح الترخيص هنا…")
        self.license_edit.setFixedHeight(140)
        root.addWidget(self.license_edit)

        button_row = QHBoxLayout()
        button_row.setSpacing(12)
        button_row.addStretch(1)

        self.activate_btn = QPushButton("تفعيل")
        self.activate_btn.clicked.connect(self._activate)
        button_row.addWidget(self.activate_btn, 0)

        self.close_btn = QPushButton("خروج" if fatal else "إغلاق")
        self.close_btn.setProperty("class", "outline")
        self.close_btn.clicked.connect(self.reject)
        button_row.addWidget(self.close_btn, 0)

        root.addLayout(button_row)

        self._update_status(status or license_status())

    def _copy_fingerprint(self):
        finger = self.fingerprint_value.text().strip()
        if not finger:
            finger = machine_fingerprint()
            self.fingerprint_value.setText(finger)
        app = QGuiApplication.instance()
        if app:
            app.clipboard().setText(finger)

    def _update_status(self, status: LicenseStatus):
        holder = status.holder.strip()
        if holder:
            holder_text = f" — {holder}"
        else:
            holder_text = ""

        message = status.message
        if status.valid and status.expires_at:
            message = f"{message} (صالح حتى {status.expires_at})."

        self.status_label.setText(message + holder_text)
        self.status_label.setProperty("kind", "ok" if status.valid else "error")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        fingerprint = status.fingerprint or machine_fingerprint()
        self.fingerprint_value.setText(fingerprint.upper())

        if status.valid:
            self.license_edit.setPlaceholderText("الترخيص مفعل. يمكنك إغلاق النافذة.")
        else:
            self.license_edit.setPlaceholderText("ألصق مفتاح الترخيص هنا…")

        if status.valid and self._fatal:
            # When the dialog is mandatory we close automatically after success.
            self.accept()

    def _activate(self):
        key = self.license_edit.toPlainText().strip()
        status = activate_license(key)
        self._update_status(status)
        if not status.valid:
            self.license_edit.selectAll()
            self.license_edit.setFocus()
        elif not self._fatal:
            self.accept()
