from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QFrame,
    QStackedWidget,
)
from PyQt6.QtCore import Qt, QTimer

from ..core.auth import authenticate, create_user, UsernameExistsError
from .common.branding import get_accent_color
from .theme import (
    DSAlert,
    DSButton,
    DSDivider,
    DSFormField,
    DSModal,
    DSSelect,
    DSTextField,
    ProgressStepper,
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

        self.toast = DSAlert("", severity="info", animated=True)
        self.toast.setObjectName("InlineToast")
        self.toast.setVisible(False)
        root.addWidget(self.toast)

        root.addWidget(DSDivider())

        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.toast.animate_out)
        self._toast_durations = {
            "info": 4200,
            "success": 3600,
            "warning": 5200,
            "danger": 6600,
        }

        self.stepper = ProgressStepper(["التحقق من المدير", "بيانات الحساب"])
        root.addWidget(self.stepper)

        self.steps = QStackedWidget()
        self.admin_page = self._build_admin_section(admin_hint)
        self.user_page = self._build_user_section()
        self.steps.addWidget(self.admin_page)
        self.steps.addWidget(self.user_page)
        root.addWidget(self.steps)

        actions = QHBoxLayout()
        actions.setSpacing(SPACING.md)
        self.back_btn = DSButton("رجوع", variant="secondary")
        self.back_btn.clicked.connect(lambda: self._set_step(0))
        self.primary_btn = DSButton("متابعة")
        cancel = DSButton("إغلاق", variant="secondary")
        cancel.clicked.connect(self.reject)
        self.primary_btn.clicked.connect(self._on_primary_action)
        actions.addWidget(self.back_btn, 1)
        actions.addWidget(self.primary_btn, 1)
        actions.addWidget(cancel, 1)
        root.addLayout(actions)

        self._set_step(0)

        self._created_username: str | None = None

    def _build_admin_section(self, admin_hint: str | None):
        frame = QFrame()
        frame.setObjectName("SectionCard")
        layout = QVBoxLayout(frame)
        layout.setSpacing(SPACING.md)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)

        label = QLabel("تحقق المدير")
        apply_typography(label, "title")
        layout.addWidget(label)

        self.admin_username = DSTextField("اسم المدير")
        if admin_hint:
            self.admin_username.setText(admin_hint)
            self.admin_username.setReadOnly(True)
        self.admin_username_field = DSFormField(
            "اسم المدير",
            self.admin_username,
            helper="يتطلب الإذن من مدير النظام قبل إنشاء مستخدم جديد.",
            required=True,
        )

        self.admin_password = DSTextField("كلمة مرور المدير")
        self.admin_password.setEchoMode(self.admin_password.EchoMode.Password)
        self.admin_password_field = DSFormField(
            "كلمة المرور",
            self.admin_password,
            helper="لن يتم حفظ بيانات الاعتماد، تستخدم للتحقق فقط.",
            required=True,
        )

        layout.addWidget(self.admin_username_field)
        layout.addWidget(self.admin_password_field)
        return frame

    def _build_user_section(self):
        frame = QFrame()
        frame.setObjectName("SectionCard")
        layout = QVBoxLayout(frame)
        layout.setSpacing(SPACING.md)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)

        label = QLabel("بيانات الموظف")
        apply_typography(label, "title")
        layout.addWidget(label)

        self.username = DSTextField("اسم المستخدم الجديد")
        self.username_field = DSFormField(
            "اسم المستخدم",
            self.username,
            helper="استخدم اسماً فريداً لسهولة تتبع الصلاحيات.",
            required=True,
        )

        self.password = DSTextField("كلمة المرور")
        self.password.setEchoMode(self.password.EchoMode.Password)
        self.password_field = DSFormField(
            "كلمة المرور",
            self.password,
            helper="اختر كلمة مرور قوية لحماية الحساب.",
            required=True,
        )

        self.password_confirm = DSTextField("تأكيد كلمة المرور")
        self.password_confirm.setEchoMode(self.password_confirm.EchoMode.Password)
        self.password_confirm_field = DSFormField(
            "تأكيد كلمة المرور",
            self.password_confirm,
            helper="أعد كتابة كلمة المرور للتأكد من التطابق.",
            required=True,
        )

        self.role = DSSelect()
        self.role.addItem("كاشير", "cashier")
        self.role.addItem("مدير", "admin")
        self.role_field = DSFormField(
            "الصلاحيات",
            self.role,
            helper="حدد مستوى الوصول المناسب للحساب.",
            required=True,
        )

        self.secret_key = DSTextField("المفتاح السري (اختياري)")
        self.secret_key_field = DSFormField(
            "مفتاح سري",
            self.secret_key,
            helper="يمكن ترك الحقل فارغًا إذا لم يتم استخدام مفتاح سري.",
        )

        layout.addWidget(self.username_field)
        layout.addWidget(self.password_field)
        layout.addWidget(self.password_confirm_field)
        layout.addWidget(self.role_field)
        layout.addWidget(self.secret_key_field)
        return frame

    # Helpers ---------------------------------------------------------------
    def _set_step(self, index: int) -> None:
        self.steps.setCurrentIndex(index)
        self.stepper.set_active_step(index)
        self.back_btn.setVisible(index > 0)
        self.primary_btn.setText("إنشاء المستخدم" if index else "متابعة")
        self._clear_step_feedback(index)

    def _clear_step_feedback(self, step: int) -> None:
        for field in self._fields_for_step(step):
            field.clear_status()

    def _fields_for_step(self, step: int):
        if step == 0:
            return [self.admin_username_field, self.admin_password_field]
        return [
            self.username_field,
            self.password_field,
            self.password_confirm_field,
            self.role_field,
            self.secret_key_field,
        ]

    def _show_toast(self, text: str, severity: str = "info") -> None:
        self.toast.setVisible(True)
        self.toast.setText(text)
        self.toast.set_severity(severity if severity in {"success", "warning", "danger"} else "info")
        duration = self._toast_durations.get(severity, 4200)
        self._toast_timer.stop()
        self._toast_timer.start(duration)
        self.toast.animate_in()

    def _on_primary_action(self) -> None:
        if self.steps.currentIndex() == 0:
            if self._validate_admin_step(show_success=True):
                self._set_step(1)
        else:
            self._on_create_user()

    def _validate_admin_step(self, *, show_success: bool = False) -> bool:
        self._clear_step_feedback(0)
        has_error = False
        admin_username = self.admin_username.text().strip()
        admin_password = self.admin_password.text()
        if not admin_username:
            self.admin_username_field.mark_error("الرجاء إدخال اسم المدير.")
            has_error = True
        if not admin_password:
            self.admin_password_field.mark_error("أدخل كلمة مرور المدير للمصادقة.")
            has_error = True
        if has_error:
            self._show_toast("أكمل بيانات المدير للمتابعة.", "warning")
            return False

        admin = authenticate(admin_username, admin_password)
        if not admin or admin.role != "admin":
            self.admin_password_field.mark_error("بيانات المدير غير صحيحة أو الصلاحيات غير كافية.")
            self._show_toast("تعذر التحقق من بيانات المدير.", "danger")
            return False

        if show_success:
            self.admin_username_field.mark_success("تم التحقق من بيانات المدير.")
            self.admin_password_field.mark_success("تم قبول الاعتماد.")
            self._show_toast("تم تأكيد هوية المدير، تابع لإدخال بيانات الحساب.", "success")
        return True

    def _on_create_user(self):
        # re-validate admin silently for safety
        if not self._validate_admin_step(show_success=False):
            self._set_step(0)
            return

        self._clear_step_feedback(1)
        has_error = False

        username = self.username.text().strip()
        password = self.password.text()
        confirm = self.password_confirm.text()

        if not username:
            self.username_field.mark_error("اسم المستخدم مطلوب لإنشاء الحساب.")
            has_error = True
        if not password:
            self.password_field.mark_error("أدخل كلمة مرور للحساب الجديد.")
            has_error = True
        if not confirm:
            self.password_confirm_field.mark_error("أعد إدخال كلمة المرور للتأكد.")
            has_error = True
        if password and confirm and password != confirm:
            self.password_confirm_field.mark_error("كلمتا المرور غير متطابقتين.")
            has_error = True

        if has_error:
            self._show_toast("راجع الحقول المظللة وأكملها بشكل صحيح.", "warning")
            return

        role = self.role.currentData()
        secret = self.secret_key.text().strip()

        try:
            user = create_user(username, password, role=role, secret_key=secret)
        except UsernameExistsError as exc:
            self.username_field.mark_error(str(exc))
            self._show_toast(str(exc), "danger")
            return
        except ValueError as exc:
            self.password_field.mark_error(str(exc))
            self._show_toast(str(exc), "danger")
            return

        self._created_username = user.username
        self.username_field.mark_success("تم إنشاء الحساب الجديد.")
        self.password_field.mark_success()
        self.password_confirm_field.mark_success()
        self._show_toast("تم إنشاء الحساب الجديد بنجاح!", "success")
        QTimer.singleShot(400, self.accept)

    # API ------------------------------------------------------------------
    def get_created_username(self) -> str | None:
        return self._created_username
