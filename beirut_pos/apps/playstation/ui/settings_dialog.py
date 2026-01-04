# beirut_pos/ui/settings_dialog.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox, QPushButton,
    QComboBox, QFileDialog, QTabWidget, QHBoxLayout, QLabel,
    QColorDialog, QListWidget, QListWidgetItem, QAbstractItemView, QMessageBox,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView, QDoubleSpinBox,
    QDialog, QScrollArea, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction, QKeySequence
import json

from beirut_pos.core.db import setting_get, setting_set, get_synchronous_mode, set_synchronous_mode
from beirut_pos.core.simple_voucher import deactivate, is_activated, status as voucher_status
from beirut_pos.core.bus import bus
from .common.big_dialog import BigDialog
from .common.async_utils import Debouncer
from .common import branding
from ..services.orders import order_manager, get_category_order, set_category_order
from ..services import texts
from ..services import staff as staff_service
from .voucher_dialog import VoucherDialog
import sys
from pathlib import Path

from beirut_pos.core.paths import DB_PATH, BACKUP_DIR, CONFIG_DIR
from ..services.backup import backup_now, restore_backup
from .settings_branding import BrandingTextsPage


def _list_printers():
    if not sys.platform.startswith("win"):
        return []
    try:
        import win32print
        return [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    except Exception:
        return []


class VipTablesPickerDialog(BigDialog):
    """Modal dialog that lets admins mark PS VIP tables via checkboxes."""

    def __init__(self, selected: set[str] | list[str], parent=None):
        super().__init__("طاولات VIP للبلايستيشن", remember_key="vip_tables_picker", parent=parent)
        self._selected = {str(code).strip().upper() for code in selected if str(code).strip()}

        layout = QVBoxLayout(self)

        intro = QLabel("اختر الطاولات التي تحصل على تسعيرة VIP عند تشغيل البلايستيشن.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        controls = QHBoxLayout()
        self.vip_filter = QLineEdit()
        self.vip_filter.setPlaceholderText("ابحث عن طاولة…")
        controls.addWidget(self.vip_filter, 1)
        self._filter_debouncer = Debouncer(self._apply_filter, parent=self, delay_ms=200)
        self.vip_filter.textChanged.connect(self._filter_debouncer.trigger)

        btn_select_all = QPushButton("تحديد الكل")
        btn_select_all.clicked.connect(lambda: self._set_all(True))
        controls.addWidget(btn_select_all)

        btn_clear = QPushButton("مسح التحديد")
        btn_clear.clicked.connect(lambda: self._set_all(False))
        controls.addWidget(btn_clear)

        layout.addLayout(controls)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        for code in order_manager.get_table_codes():
            item = QListWidgetItem(code)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            state = Qt.CheckState.Checked if code in self._selected else Qt.CheckState.Unchecked
            item.setCheckState(state)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget, 1)

        buttons = QHBoxLayout()
        btn_cancel = QPushButton("إلغاء")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("حفظ")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_save)
        layout.addLayout(buttons)

    # ----------------------------------------------------------------- utils
    def _set_all(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if item:
                item.setCheckState(state)

    def _apply_filter(self, text: str):
        needle = (text or "").strip().upper()
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if not item:
                continue
            code = item.text().strip().upper()
            hidden = bool(needle) and needle not in code
            item.setHidden(hidden)

    def selected_codes(self) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if not item or item.checkState() != Qt.CheckState.Checked:
                continue
            code = item.text().strip().upper()
            if not code or code in seen:
                continue
            seen.add(code)
            cleaned.append(code)
        return cleaned


class ManualStaffDialog(BigDialog):
    """Dialog used to collect basic info for manual payroll entries."""

    def __init__(self, parent=None):
        super().__init__("إضافة موظف خارجي", remember_key="manual_staff", parent=parent)
        layout = QVBoxLayout(self)

        intro = QLabel("اكتب اسم الموظف والدور الوظيفي ليظهر في صفحة المحاسبة.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        form.setSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("اسم الموظف")
        self.role_input = QLineEdit()
        self.role_input.setPlaceholderText("المسمى الوظيفي")
        form.addRow("الاسم:", self.name_input)
        form.addRow("الدور:", self.role_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btn_cancel = QPushButton("إلغاء")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("إضافة")
        btn_save.setDefault(True)
        btn_save.clicked.connect(self._handle_accept)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_save)
        layout.addLayout(buttons)

    def _handle_accept(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(self, "بيانات ناقصة", "يجب إدخال اسم الموظف.")
            return
        self.accept()

    def data(self) -> dict[str, str]:
        return {
            "name": self.name_input.text().strip(),
            "role": self.role_input.text().strip(),
        }


class SettingsDialog(BigDialog):
    def __init__(self, parent=None):
        super().__init__("الإعدادات", remember_key="settings", parent=parent)

        # Make sure the dialog is comfortably sized and resizable
        self.setMinimumSize(720, 520)
        self.resize(960, 700)
        self.setSizeGripEnabled(True)

        self._default_palette = branding.default_palette()

        # ===== Tabs ============================================================
        tabs = QTabWidget()
        tabs.setTabPosition(QTabWidget.TabPosition.North)

        # --- General tab ---
        gen = QWidget()
        gen_v = QVBoxLayout(gen)
        gen_v.setContentsMargins(24, 24, 24, 24)
        gen_v.setSpacing(18)
        gen_f = QFormLayout()
        gen_f.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        gen_f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        gen_f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        gen_f.setSpacing(12)
        gen_v.addLayout(gen_f)

        def _configure_field(widget):
            widget.setMinimumWidth(260)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            if hasattr(widget, "setMinimumHeight"):
                widget.setMinimumHeight(34)
            if isinstance(widget, (QLineEdit, QComboBox)):
                widget.setStyleSheet("padding: 6px 10px;")

        self.company = QLineEdit(setting_get("company_name", "Beirut Coffee"))
        self.currency = QLineEdit(setting_get("currency", "EGP"))
        self.service = QSpinBox(); self.service.setRange(0, 50); self.service.setValue(int(setting_get("service_pct", "0")))
        _configure_field(self.company)
        _configure_field(self.currency)
        _configure_field(self.service)
        gen_f.addRow("الاسم التجاري:", self.company)
        gen_f.addRow("العملة:", self.currency)
        gen_f.addRow("نسبة الخدمة %:", self.service)

        self.sync_mode = QComboBox()
        self.sync_mode.addItems(["FULL", "NORMAL"])
        self.sync_mode.setCurrentText(get_synchronous_mode())
        _configure_field(self.sync_mode)
        gen_f.addRow("قوة مزامنة قاعدة البيانات:", self.sync_mode)

        data_label = QLabel(str(DB_PATH))
        data_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        gen_f.addRow("مسار قاعدة البيانات:", data_label)
        cfg_label = QLabel(str(CONFIG_DIR))
        cfg_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        gen_f.addRow("مسار الإعدادات:", cfg_label)

        backup_row = QHBoxLayout()
        self.btn_backup_now = QPushButton("نسخ احتياطي الآن")
        self.btn_backup_now.clicked.connect(self._on_backup_now)
        self.btn_restore = QPushButton("استرجاع نسخة…")
        self.btn_restore.clicked.connect(self._on_restore_backup)
        backup_row.addWidget(self.btn_backup_now)
        backup_row.addWidget(self.btn_restore)
        backup_widget = QWidget(); backup_widget.setLayout(backup_row)
        gen_f.addRow("النسخ الاحتياطي:", backup_widget)

        voucher_row = QHBoxLayout(); voucher_row.setSpacing(12)
        self.voucher_status = QLabel(); self.voucher_status.setWordWrap(True)
        voucher_row.addWidget(self.voucher_status, 1)
        self.btn_voucher_activate = QPushButton("إدخال رمز…")
        self.btn_voucher_activate.clicked.connect(self._open_voucher_dialog)
        voucher_row.addWidget(self.btn_voucher_activate, 0)
        self.btn_voucher_deactivate = QPushButton("تعطيل")
        self.btn_voucher_deactivate.clicked.connect(self._deactivate_voucher)
        voucher_row.addWidget(self.btn_voucher_deactivate, 0)
        voucher_widget = QWidget(); voucher_widget.setLayout(voucher_row)
        gen_f.addRow("حالة التفعيل:", voucher_widget)

        self._refresh_voucher_status()
        tabs.addTab(gen, "عام")

        # --- Printers tab ---
        prn = QWidget()
        prn_v = QVBoxLayout(prn)
        prn_v.setContentsMargins(24, 24, 24, 24)
        prn_v.setSpacing(18)
        prn_f = QFormLayout()
        prn_f.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        prn_f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        prn_f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        prn_f.setSpacing(12)
        prn_v.addLayout(prn_f)

        names = _list_printers()
        self.bar_prn = QComboBox(); self.bar_prn.setEditable(True); self.bar_prn.addItems(names)
        self.cash_prn = QComboBox(); self.cash_prn.setEditable(True); self.cash_prn.addItems(names)
        self.bar_prn.setCurrentText(setting_get("bar_printer", ""))
        self.cash_prn.setCurrentText(setting_get("cashier_printer", ""))
        _configure_field(self.bar_prn)
        _configure_field(self.cash_prn)
        prn_f.addRow("طابعة البار:", self.bar_prn)
        prn_f.addRow("طابعة الكاشير:", self.cash_prn)

        hint = QLabel("ملاحظة: على ويندوز، تأكد أن أسماء الطابعات هنا مطابقة تماماً لاسم الجهاز في \"Devices and Printers\".")
        hint.setWordWrap(True)
        prn_v.addWidget(hint)

        tabs.addTab(prn, "الطابعات")

        # --- PlayStation tab ---
        ps = QWidget()
        ps_v = QVBoxLayout(ps)
        ps_v.setContentsMargins(24, 24, 24, 24)
        ps_v.setSpacing(18)
        ps_f = QFormLayout()
        ps_f.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        ps_f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        ps_f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        ps_f.setSpacing(12)
        ps_v.addLayout(ps_f)

        def _read_ps_rate(key: str, default: int) -> int:
            raw = setting_get(key, str(default))
            try:
                value = int(float(raw))
            except (TypeError, ValueError):
                value = default
            if value > 1000:
                value = value // 100
            return max(value, 0)

        self.ps_p2 = QSpinBox(); self.ps_p2.setRange(0, 1_000_000); self.ps_p2.setSingleStep(1); self.ps_p2.setSuffix(" ج.م"); self.ps_p2.setValue(_read_ps_rate("ps_rate_p2", 50))
        self.ps_p4 = QSpinBox(); self.ps_p4.setRange(0, 1_000_000); self.ps_p4.setSingleStep(1); self.ps_p4.setSuffix(" ج.م"); self.ps_p4.setValue(_read_ps_rate("ps_rate_p4", 80))
        _configure_field(self.ps_p2)
        _configure_field(self.ps_p4)
        ps_f.addRow("سعر PS لاعبين/ساعة (ج.م):", self.ps_p2)
        ps_f.addRow("سعر PS أربعة/ساعة (ج.م):", self.ps_p4)

        vip_default_raw = setting_get("ps_vip_tables", "[]")
        try:
            vip_saved = json.loads(vip_default_raw)
            if not isinstance(vip_saved, list):
                vip_saved = []
        except Exception:
            vip_saved = []
        vip_selected = {str(code).strip().upper() for code in vip_saved if isinstance(code, str)}

        vip_hint = QLabel("اختر الطاولات التي تستخدم تسعيرة VIP مختلفة عن باقي الطاولات.")
        vip_hint.setWordWrap(True)

        self._vip_tables: list[str] = self._normalize_vip_codes(vip_selected)
        self.vip_summary = QLabel()
        self.vip_summary.setWordWrap(True)
        self._refresh_vip_summary()

        vip_actions = QHBoxLayout()
        vip_actions.addWidget(self.vip_summary, 1)
        btn_edit_vip = QPushButton("تحديد الطاولات…")
        btn_edit_vip.clicked.connect(self._edit_vip_tables)
        vip_actions.addWidget(btn_edit_vip, 0)
        vip_actions_widget = QWidget(); vip_actions_widget.setLayout(vip_actions)

        vip_wrapper = QVBoxLayout(); vip_wrapper.setSpacing(6)
        vip_wrapper.addWidget(vip_hint)
        vip_wrapper.addWidget(vip_actions_widget)
        vip_widget = QWidget(); vip_widget.setLayout(vip_wrapper)
        ps_f.addRow("طاولات VIP:", vip_widget)

        self.ps_vip_p2 = QSpinBox(); self.ps_vip_p2.setRange(0, 1_000_000); self.ps_vip_p2.setSingleStep(1); self.ps_vip_p2.setSuffix(" ج.م")
        self.ps_vip_p2.setValue(_read_ps_rate("ps_vip_rate_p2", self.ps_p2.value()))
        self.ps_vip_p4 = QSpinBox(); self.ps_vip_p4.setRange(0, 1_000_000); self.ps_vip_p4.setSingleStep(1); self.ps_vip_p4.setSuffix(" ج.م")
        self.ps_vip_p4.setValue(_read_ps_rate("ps_vip_rate_p4", self.ps_p4.value()))
        _configure_field(self.ps_vip_p2)
        _configure_field(self.ps_vip_p4)
        ps_f.addRow("سعر VIP PS لاعبين/ساعة (ج.م):", self.ps_vip_p2)
        ps_f.addRow("سعر VIP PS أربعة/ساعة (ج.م):", self.ps_vip_p4)
        tabs.addTab(ps, "البلايستيشن")

        # --- Branding tab ---
        br = QWidget()
        br_outer = QVBoxLayout(br)
        br_outer.setContentsMargins(0, 0, 0, 0)
        br_outer.setSpacing(0)

        br_scroll = QScrollArea()
        br_scroll.setWidgetResizable(True)
        br_outer.addWidget(br_scroll)

        br_body = QWidget()
        br_scroll.setWidget(br_body)

        br_v = QVBoxLayout(br_body)
        br_v.setContentsMargins(24, 24, 24, 24)
        br_v.setSpacing(18)

        br_f = QFormLayout()
        br_f.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        br_f.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        br_f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        br_f.setSpacing(12)
        br_v.addLayout(br_f)

        self.logo_path = QLineEdit(setting_get("logo_path", ""))
        _configure_field(self.logo_path)
        btn_browse = QPushButton("اختيار…")
        def pick_logo():
            p, _ = QFileDialog.getOpenFileName(self, "اختيار الشعار", "", "Images (*.png *.jpg *.jpeg)")
            if p: self.logo_path.setText(p)
        btn_browse.clicked.connect(pick_logo)
        row = QHBoxLayout(); row.addWidget(self.logo_path, 1); row.addWidget(btn_browse, 0)
        row_w = QWidget(); row_w.setLayout(row)
        br_f.addRow("الشعار:", row_w)

        self.background_path = QLineEdit(setting_get("background_path", ""))
        _configure_field(self.background_path)
        btn_bg = QPushButton("اختيار…")
        def pick_bg():
            p, _ = QFileDialog.getOpenFileName(self, "اختيار الخلفية", "", "Images (*.png *.jpg *.jpeg)")
            if p: self.background_path.setText(p)
        btn_bg.clicked.connect(pick_bg)
        bg_row = QHBoxLayout(); bg_row.addWidget(self.background_path, 1); bg_row.addWidget(btn_bg, 0)
        bg_widget = QWidget(); bg_widget.setLayout(bg_row)
        br_f.addRow("الخلفية:", bg_widget)

        palette = self._default_palette

        def make_color_row(target_layout: QFormLayout, key: str, label: str, dialog_title: str):
            field = QLineEdit(setting_get(key, palette[key]))
            _configure_field(field)
            field.setMaxLength(7)
            button = QPushButton("لون…")

            def pick():
                current = QColor(field.text() or palette[key])
                col = QColorDialog.getColor(current, self, dialog_title)
                if col.isValid():
                    field.setText(col.name())

            button.clicked.connect(pick)
            row = QHBoxLayout()
            row.addWidget(field, 1)
            row.addWidget(button, 0)
            wrapper = QWidget(); wrapper.setLayout(row)
            target_layout.addRow(label, wrapper)
            return field

        color_columns = QHBoxLayout()
        color_columns.setSpacing(24)

        left_colors = QFormLayout()
        left_colors.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        left_colors.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        left_colors.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        left_colors.setSpacing(12)

        right_colors = QFormLayout()
        right_colors.setFormAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
        right_colors.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        right_colors.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        right_colors.setSpacing(12)

        self.accent_color = make_color_row(left_colors, "accent_color", "اللون الرئيسي:", "اختر اللون الرئيسي")
        self.surface_color = make_color_row(left_colors, "surface_color", "لون خلفية الواجهة:", "اختر لون لوحة التحكم")
        self.text_color = make_color_row(left_colors, "text_color", "لون النص:", "اختر لون النص")
        self.muted_text_color = make_color_row(left_colors, "muted_text_color", "لون النص الثانوي:", "اختر لون النص الثانوي")
        self.toolbar_color = make_color_row(left_colors, "toolbar_color", "لون شريط الأدوات:", "اختر لون شريط الأدوات")
        self.toolbar_text_color = make_color_row(left_colors, "toolbar_text_color", "لون خط شريط الأدوات:", "اختر لون خط شريط الأدوات")

        self.menu_card_color = make_color_row(right_colors, "menu_card_color", "لون بطاقات الأقسام:", "اختر لون بطاقات الأقسام")
        self.menu_header_color = make_color_row(right_colors, "menu_header_color", "لون عناوين الأقسام:", "اختر لون عنوان القسم")
        self.menu_button_color = make_color_row(right_colors, "menu_button_color", "لون أزرار المنتجات:", "اختر لون أزرار المنتجات")
        self.menu_button_text_color = make_color_row(right_colors, "menu_button_text_color", "لون خط أزرار المنتجات:", "اختر لون خط زر المنتج")
        self.menu_button_hover_color = make_color_row(right_colors, "menu_button_hover_color", "لون الزر عند التحويم:", "اختر لون الزر عند التحويم")

        color_columns.addLayout(left_colors, 1)
        color_columns.addLayout(right_colors, 1)
        br_v.addLayout(color_columns)

        button_grid = QGridLayout()
        button_grid.setHorizontalSpacing(18)
        button_grid.setVerticalSpacing(10)

        self.menu_button_height = QSpinBox()
        _configure_field(self.menu_button_height)
        self.menu_button_height.setRange(40, 200)
        self.menu_button_height.setSuffix(" px")
        self.menu_button_height.setValue(branding.get_menu_button_height())
        button_grid.addWidget(QLabel("ارتفاع زر المنتج"), 0, 0, alignment=Qt.AlignmentFlag.AlignRight)
        button_grid.addWidget(self.menu_button_height, 0, 1)

        self.menu_button_font_size = QSpinBox()
        _configure_field(self.menu_button_font_size)
        self.menu_button_font_size.setRange(10, 32)
        self.menu_button_font_size.setSuffix(" px")
        self.menu_button_font_size.setValue(branding.get_menu_button_font_size())
        button_grid.addWidget(QLabel("حجم خط الزر"), 1, 0, alignment=Qt.AlignmentFlag.AlignRight)
        button_grid.addWidget(self.menu_button_font_size, 1, 1)

        self.menu_button_padding = QSpinBox()
        _configure_field(self.menu_button_padding)
        self.menu_button_padding.setRange(4, 36)
        self.menu_button_padding.setSuffix(" px")
        self.menu_button_padding.setValue(branding.get_menu_button_padding())
        button_grid.addWidget(QLabel("الحشو الداخلي"), 2, 0, alignment=Qt.AlignmentFlag.AlignRight)
        button_grid.addWidget(self.menu_button_padding, 2, 1)

        self.menu_columns = QSpinBox()
        _configure_field(self.menu_columns)
        self.menu_columns.setRange(1, 6)
        self.menu_columns.setSuffix(" عمود")
        self.menu_columns.setValue(branding.get_menu_columns())
        button_grid.addWidget(QLabel("عدد الأعمدة في الشبكة"), 3, 0, alignment=Qt.AlignmentFlag.AlignRight)
        button_grid.addWidget(self.menu_columns, 3, 1)

        br_v.addLayout(button_grid)

        reset_colors = QPushButton("استعادة الألوان الافتراضية")
        reset_colors.clicked.connect(self._reset_palette_fields)
        br_v.addWidget(reset_colors, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(br, "الهوية")

        self.branding_texts = BrandingTextsPage(self)
        tabs.addTab(self.branding_texts, texts.get("settings.branding.tab"))

        # --- Accounting tab ---
        acc = QWidget()
        acc_v = QVBoxLayout(acc)
        acc_v.setContentsMargins(24, 24, 24, 24)
        acc_v.setSpacing(16)

        headers = [
            "الموظف",
            "الدور",
            "نوع الأجر",
            "قيمة الراتب (ج.م)",
            "الخصومات (ج.م)",
            "السلف (ج.م)",
            "الصافي المستحق (ج.م)",
        ]
        self.payroll_table = QTableWidget(0, len(headers))
        self.payroll_table.setHorizontalHeaderLabels(headers)
        self.payroll_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.payroll_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.payroll_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.payroll_table.setAlternatingRowColors(True)
        header = self.payroll_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for col in range(3, len(headers)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        acc_v.addWidget(self.payroll_table, 1)

        controls = QHBoxLayout()
        btn_refresh_payroll = QPushButton("تحديث")
        btn_refresh_payroll.clicked.connect(self._load_payroll_rows)
        controls.addWidget(btn_refresh_payroll)
        btn_add_manual = QPushButton("إضافة موظف خارجي")
        btn_add_manual.clicked.connect(self._add_manual_staff)
        controls.addWidget(btn_add_manual)
        btn_save_payroll = QPushButton("حفظ الرواتب")
        btn_save_payroll.clicked.connect(self._save_payroll_rows)
        controls.addWidget(btn_save_payroll)

        btn_mark_paid = QPushButton("تسجيل دفع الراتب")
        btn_mark_paid.clicked.connect(self._mark_salary_paid)
        controls.addWidget(btn_mark_paid)
        controls.addStretch(1)
        acc_v.addLayout(controls)

        self.payroll_summary = QLabel("")
        self.payroll_summary.setAlignment(Qt.AlignmentFlag.AlignRight)
        acc_v.addWidget(self.payroll_summary)

        tabs.addTab(acc, "المحاسبة")
        self._payroll_inputs: list[dict[str, object]] = []

        # --- Category order tab ---
        cat_tab = QWidget(); cat_v = QVBoxLayout(cat_tab)
        cat_hint = QLabel("رتّب الأقسام بالسحب والإفلات لتظهر بالترتيب نفسه في شاشة الطلبات.")
        cat_hint.setWordWrap(True)
        cat_v.addWidget(cat_hint)

        self.category_list = QListWidget()
        self.category_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.category_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.category_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.category_list.setAlternatingRowColors(True)
        cat_v.addWidget(self.category_list, 1)

        ordered = get_category_order()
        existing = [cat[0] for cat in order_manager.categories]
        seen = set()
        for name in ordered + [n for n in existing if n not in ordered]:
            if name in seen:
                continue
            seen.add(name)
            self.category_list.addItem(name)

        tabs.addTab(cat_tab, "ترتيب الأقسام")

        # ===== TOP action bar (sticky) + root layout ==========================
        root = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel("الإعدادات")
        title_lbl.setStyleSheet("font-weight: 700; font-size: 16px; margin: 6px 0;")

        btn_save_top = QPushButton("حفظ")
        btn_save_top.setDefault(True)
        btn_save_top.clicked.connect(self._save)

        btn_close_top = QPushButton("إغلاق")
        btn_close_top.clicked.connect(self.reject)

        top_bar.addWidget(title_lbl, 1, alignment=Qt.AlignmentFlag.AlignRight)
        top_bar.addWidget(btn_close_top, 0)
        top_bar.addWidget(btn_save_top, 0)

        top_bar_w = QWidget(); top_bar_w.setLayout(top_bar)

        root.addWidget(top_bar_w, 0)
        root.addWidget(tabs, 1)

        self._load_payroll_rows()

        # ===== Shortcuts ======================================================
        act_save = QAction(self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self._save)
        self.addAction(act_save)

        act_close = QAction(self)
        act_close.setShortcut(QKeySequence("Ctrl+W"))
        act_close.triggered.connect(self.reject)
        self.addAction(act_close)

        act_escape = QAction(self)
        act_escape.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        act_escape.triggered.connect(self.reject)
        self.addAction(act_escape)

    # ==================== Handlers ===========================================
    def _load_payroll_rows(self):
        try:
            rows = staff_service.list_payroll_rows()
        except Exception as exc:
            QMessageBox.warning(self, "المحاسبة", f"تعذر تحميل بيانات الرواتب:\n{exc}")
            rows = []

        self.payroll_table.setRowCount(len(rows))
        self._payroll_inputs = []

        for row_idx, entry in enumerate(rows):
            username = str(entry.get("username", "")).strip()
            display_name = str(entry.get("display_name", username)).strip() or username
            role = str(entry.get("role", "")).strip()
            salary = float(entry.get("salary_cents", 0) or 0)
            deductions = float(entry.get("deductions_cents", 0) or 0)
            loan = float(entry.get("loan_cents", 0) or 0)
            salary_period = str(entry.get("salary_period", "monthly") or "monthly")
            source = entry.get("source", "system")
            manual_id = entry.get("manual_id")

            user_item = QTableWidgetItem(display_name)
            user_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            user_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if source == "manual":
                font = user_item.font()
                font.setItalic(True)
                user_item.setFont(font)
            self.payroll_table.setItem(row_idx, 0, user_item)

            role_item = QTableWidgetItem(role)
            role_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            role_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.payroll_table.setItem(row_idx, 1, role_item)

            period_combo = QComboBox()
            period_combo.addItem("شهري", "monthly")
            period_combo.addItem("يومي", "daily")
            idx = 0 if salary_period == "monthly" else 1
            period_combo.setCurrentIndex(idx)
            period_combo.currentIndexChanged.connect(
                lambda _=0, index=row_idx: self._update_payroll_summary()
            )
            self.payroll_table.setCellWidget(row_idx, 2, period_combo)

            def _make_spin(value: float) -> QDoubleSpinBox:
                spin = QDoubleSpinBox()
                spin.setRange(0, 1_000_000)
                spin.setDecimals(2)
                spin.setSingleStep(10.0)
                spin.setValue(max(value, 0.0))
                spin.setAlignment(Qt.AlignmentFlag.AlignRight)
                spin.setKeyboardTracking(False)
                return spin

            salary_spin = _make_spin(salary)
            deduction_spin = _make_spin(deductions)
            loan_spin = _make_spin(loan)

            self.payroll_table.setCellWidget(row_idx, 3, salary_spin)
            self.payroll_table.setCellWidget(row_idx, 4, deduction_spin)
            self.payroll_table.setCellWidget(row_idx, 5, loan_spin)

            self._payroll_inputs.append(
                {
                    "salary": salary_spin,
                    "deduction": deduction_spin,
                    "loan": loan_spin,
                    "period": period_combo,
                    "meta": {
                        "username": username,
                        "display_name": display_name,
                        "role": role,
                        "source": source,
                        "manual_id": manual_id,
                    },
                }
            )

            for spin in (salary_spin, deduction_spin, loan_spin):
                spin.valueChanged.connect(lambda _=0.0, idx=row_idx: self._recalculate_payroll_row(idx))

            self._recalculate_payroll_row(row_idx)

        self._update_payroll_summary()

    def _recalculate_payroll_row(self, row: int) -> None:
        if row < 0 or row >= len(self._payroll_inputs):
            return
        widgets = self._payroll_inputs[row]
        salary = widgets["salary"].value()
        deduction = widgets["deduction"].value()
        loan = widgets["loan"].value()
        net = salary - deduction - loan
        net_item = QTableWidgetItem(f"{net:.2f}")
        net_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        net_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.payroll_table.setItem(row, 6, net_item)
        self._update_payroll_summary()

    def _update_payroll_summary(self) -> None:
        totals = {
            "monthly": {"salary": 0.0, "deduction": 0.0, "loan": 0.0, "net": 0.0},
            "daily": {"salary": 0.0, "deduction": 0.0, "loan": 0.0, "net": 0.0},
        }
        for widgets in self._payroll_inputs:
            period_widget = widgets.get("period")
            if isinstance(period_widget, QComboBox):
                period = period_widget.currentData() or "monthly"
            else:
                period = "monthly"
            bucket = totals["daily" if period == "daily" else "monthly"]
            salary = widgets["salary"].value()
            deduction = widgets["deduction"].value()
            loan = widgets["loan"].value()
            net = salary - deduction - loan
            bucket["salary"] += salary
            bucket["deduction"] += deduction
            bucket["loan"] += loan
            bucket["net"] += net

        total_salary = totals["monthly"]["salary"] + totals["daily"]["salary"]
        total_deduction = totals["monthly"]["deduction"] + totals["daily"]["deduction"]
        total_loans = totals["monthly"]["loan"] + totals["daily"]["loan"]
        total_net = totals["monthly"]["net"] + totals["daily"]["net"]
        summary = (
            f"الرواتب الشهرية: {totals['monthly']['salary']:.2f} ج.م | "
            f"الصافي الشهري: {totals['monthly']['net']:.2f} ج.م | "
            f"الأجور اليومية: {totals['daily']['salary']:.2f} ج.م | "
            f"الصافي اليومي: {totals['daily']['net']:.2f} ج.م | "
            f"إجمالي الخصومات: {total_deduction:.2f} ج.م | "
            f"السلف: {total_loans:.2f} ج.م | "
            f"الصافي الكلي: {total_net:.2f} ج.م"
        )
        self.payroll_summary.setText(summary)

    def _save_payroll_rows(self) -> None:
        entries = []
        for row_idx, widgets in enumerate(self._payroll_inputs):
            meta = widgets.get("meta", {}) if isinstance(widgets, dict) else {}
            user_item = self.payroll_table.item(row_idx, 0)
            role_item = self.payroll_table.item(row_idx, 1)
            display_name = meta.get("display_name") if isinstance(meta, dict) else ""
            if user_item and not display_name:
                display_name = user_item.text().strip()
            role_text = role_item.text().strip() if role_item else str(meta.get("role", ""))
            salary = int(round(widgets["salary"].value()))
            deduction = int(round(widgets["deduction"].value()))
            loan = int(round(widgets["loan"].value()))
            period_widget = widgets.get("period")
            period_value = "monthly"
            if isinstance(period_widget, QComboBox):
                period_value = period_widget.currentData() or "monthly"
            entries.append(
                {
                    "username": (meta.get("username") or "") if isinstance(meta, dict) else "",
                    "manual_id": meta.get("manual_id") if isinstance(meta, dict) else None,
                    "display_name": display_name,
                    "role": role_text,
                    "salary_cents": salary,
                    "deductions_cents": deduction,
                    "loan_cents": loan,
                    "salary_period": period_value,
                    "source": meta.get("source") if isinstance(meta, dict) else "system",
                }
            )
        try:
            staff_service.save_payroll_rows(entries)
        except Exception as exc:
            QMessageBox.critical(self, "المحاسبة", f"تعذر حفظ بيانات الرواتب:\n{exc}")
            return
        QMessageBox.information(self, "المحاسبة", "تم حفظ بيانات الرواتب بنجاح.")
        self._load_payroll_rows()

    def _mark_salary_paid(self) -> None:
        if not self._payroll_inputs:
            QMessageBox.information(self, "الرواتب", "لا توجد بيانات رواتب لعرضها.")
            return

        row = self.payroll_table.currentRow()
        if row < 0 or row >= len(self._payroll_inputs):
            QMessageBox.warning(self, "الرواتب", "يرجى اختيار موظف من الجدول أولاً.")
            return

        widgets = self._payroll_inputs[row]
        period_widget = widgets.get("period")
        period_value = "monthly"
        if isinstance(period_widget, QComboBox):
            period_value = period_widget.currentData() or "monthly"
        if period_value != "monthly":
            QMessageBox.information(self, "الرواتب", "يمكن تسجيل دفع الرواتب الشهرية فقط من هنا.")
            return

        salary = int(round(widgets["salary"].value()))
        deduction = int(round(widgets["deduction"].value()))
        loan = int(round(widgets["loan"].value()))
        net = salary - deduction - loan
        if net <= 0:
            QMessageBox.warning(self, "الرواتب", "لا يوجد مبلغ مستحق بعد الخصومات والسلف.")
            return

        meta = widgets.get("meta") if isinstance(widgets, dict) else {}
        user_item = self.payroll_table.item(row, 0)
        role_item = self.payroll_table.item(row, 1)
        display_name = ""
        if isinstance(meta, dict):
            display_name = (meta.get("display_name") or meta.get("username") or "").strip()
        if not display_name and user_item:
            display_name = user_item.text().strip()
        role = role_item.text().strip() if role_item else str(meta.get("role", ""))
        username = meta.get("username") if isinstance(meta, dict) else ""
        manual_id = meta.get("manual_id") if isinstance(meta, dict) else None

        if not display_name:
            QMessageBox.warning(self, "الرواتب", "لا يمكن تسجيل الدفع بدون اسم موظف صحيح.")
            return

        confirm = QMessageBox.question(
            self,
            "تسجيل دفع راتب",
            f"هل تريد تسجيل دفع راتب {display_name} بمبلغ {net:.0f} ج.م؟",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            staff_service.record_salary_payment(
                {
                    "source": "payout",
                    "username": username,
                    "manual_id": manual_id,
                    "display_name": display_name,
                    "role": role,
                    "salary_cents": salary,
                    "deductions_cents": deduction,
                    "loan_cents": loan,
                    "salary_period": period_value,
                }
            )
        except Exception as exc:
            QMessageBox.critical(self, "الرواتب", f"تعذر تسجيل عملية الدفع:\n{exc}")
            return

        QMessageBox.information(self, "الرواتب", "تم تسجيل صرف الراتب بنجاح.")
        self._load_payroll_rows()

    def _add_manual_staff(self) -> None:
        dialog = ManualStaffDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        data = dialog.data()
        try:
            staff_service.create_manual_staff(data.get("name", ""), data.get("role", ""))
        except ValueError:
            QMessageBox.warning(self, "المحاسبة", "يجب إدخال اسم صالح.")
            return
        except Exception as exc:
            QMessageBox.critical(self, "المحاسبة", f"تعذر إضافة الموظف الجديد:\n{exc}")
            return
        self._load_payroll_rows()

    def _on_backup_now(self):
        try:
            path = backup_now()
        except Exception as exc:
            QMessageBox.critical(self, "خطأ في النسخ الاحتياطي", f"تعذر إنشاء النسخة الاحتياطية:\n{exc}")
            return
        QMessageBox.information(self, "تم إنشاء نسخة احتياطية", f"تم حفظ نسخة من قاعدة البيانات في:\n{path}")

    def _on_restore_backup(self):
        start_dir = str(BACKUP_DIR if BACKUP_DIR.exists() else Path.home())
        file_path, _ = QFileDialog.getOpenFileName(
            self, "اختيار نسخة احتياطية", start_dir, "SQLite Database (*.db)"
        )
        if not file_path:
            return
        try:
            restore_backup(Path(file_path))
        except Exception as exc:
            QMessageBox.critical(self, "فشل الاستعادة", f"تعذر استعادة النسخة الاحتياطية:\n{exc}")
            return
        QMessageBox.information(
            self, "اكتملت الاستعادة",
            "تم استرجاع قاعدة البيانات من النسخة المحددة. يرجى إعادة تشغيل البرنامج لتطبيق التغييرات."
        )

    def _save(self):
        try:
            self.branding_texts.apply_changes()
        except ValueError as exc:
            QMessageBox.warning(self, texts.get("settings.branding.tab"), str(exc))
            return

        company = self.company.text().strip()
        currency = self.currency.text().strip()
        service_pct = str(self.service.value())
        bar = self.bar_prn.currentText().strip()
        cash = self.cash_prn.currentText().strip()
        logo = self.logo_path.text().strip()
        background = self.background_path.text().strip()
        accent = self.accent_color.text().strip()
        surface_color = self.surface_color.text().strip()
        text_color = self.text_color.text().strip()
        muted_text = self.muted_text_color.text().strip()
        menu_card_color = self.menu_card_color.text().strip()
        menu_header_color = self.menu_header_color.text().strip()
        menu_button_color = self.menu_button_color.text().strip()
        menu_button_text = self.menu_button_text_color.text().strip()
        menu_button_hover = self.menu_button_hover_color.text().strip()
        menu_button_height = self.menu_button_height.value()
        menu_button_font_size = self.menu_button_font_size.value()
        menu_button_padding = self.menu_button_padding.value()
        menu_columns = self.menu_columns.value()
        toolbar_color = self.toolbar_color.text().strip()
        toolbar_text_color = self.toolbar_text_color.text().strip()

        setting_set("company_name", company)
        setting_set("currency", currency)
        setting_set("service_pct", service_pct)
        set_synchronous_mode(self.sync_mode.currentText().upper())
        setting_set("ps_rate_p2", str(self.ps_p2.value()))
        setting_set("ps_rate_p4", str(self.ps_p4.value()))
        setting_set("ps_vip_rate_p2", str(self.ps_vip_p2.value()))
        setting_set("ps_vip_rate_p4", str(self.ps_vip_p4.value()))
        setting_set("ps_vip_tables", json.dumps(self._vip_tables, ensure_ascii=False))
        setting_set("bar_printer", bar)
        setting_set("cashier_printer", cash)
        setting_set("logo_path", logo)
        setting_set("background_path", background)
        setting_set("accent_color", accent)
        setting_set("surface_color", surface_color)
        setting_set("text_color", text_color)
        setting_set("muted_text_color", muted_text)
        setting_set("menu_card_color", menu_card_color)
        setting_set("menu_header_color", menu_header_color)
        setting_set("menu_button_color", menu_button_color)
        setting_set("menu_button_text_color", menu_button_text)
        setting_set("menu_button_hover_color", menu_button_hover)
        setting_set("menu_button_height", str(menu_button_height))
        setting_set("menu_button_font_size", str(menu_button_font_size))
        setting_set("menu_button_padding", str(menu_button_padding))
        setting_set("menu_columns", str(menu_columns))
        setting_set("toolbar_color", toolbar_color)
        setting_set("toolbar_text_color", toolbar_text_color)

        order = [self.category_list.item(i).text() for i in range(self.category_list.count())]
        set_category_order(order)

        branding.clear_branding_cache()
        bus.emit(
            "branding_changed",
            {
                "logo": logo,
                "background": background,
                "accent": accent,
                "surface": surface_color,
                "text": text_color,
                "muted": muted_text,
                "menu_card": menu_card_color,
                "menu_header": menu_header_color,
                "menu_button": menu_button_color,
                "menu_button_text": menu_button_text,
                "menu_button_hover": menu_button_hover,
                "menu_button_height": menu_button_height,
                "menu_button_font_size": menu_button_font_size,
                "menu_button_padding": menu_button_padding,
                "menu_columns": menu_columns,
                "toolbar": toolbar_color,
                "toolbar_text": toolbar_text_color,
            },
        )
        bus.emit("catalog_changed")
        bus.emit("printers_changed", bar, cash)
        bus.emit("settings_saved")
        self.accept()

    def _normalize_vip_codes(self, codes) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for code in codes:
            try:
                text = str(code)
            except Exception:
                continue
            normalized = text.strip().upper()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(normalized)
        return cleaned

    def _refresh_vip_summary(self):
        count = len(self._vip_tables)
        if not count:
            text = "لا توجد طاولات VIP محددة حاليًا."
        else:
            preview_count = 6
            preview = "، ".join(self._vip_tables[:preview_count])
            remaining = count - preview_count
            if remaining > 0:
                preview += f" … (+{remaining} أخرى)"
            text = f"عدد الطاولات المميزة: {count}\n{preview}"
        self.vip_summary.setText(text)

    def _edit_vip_tables(self):
        dlg = VipTablesPickerDialog(self._vip_tables, parent=self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            self._vip_tables = dlg.selected_codes()
            self._refresh_vip_summary()

    def _reset_palette_fields(self):
        palette = self._default_palette
        self.accent_color.setText(palette["accent_color"])
        self.surface_color.setText(palette["surface_color"])
        self.text_color.setText(palette["text_color"])
        self.muted_text_color.setText(palette["muted_text_color"])
        self.menu_card_color.setText(palette["menu_card_color"])
        self.menu_header_color.setText(palette["menu_header_color"])
        self.menu_button_color.setText(palette["menu_button_color"])
        self.menu_button_text_color.setText(palette["menu_button_text_color"])
        self.menu_button_hover_color.setText(palette["menu_button_hover_color"])
        self.menu_button_height.setValue(palette["menu_button_height"])
        self.menu_button_font_size.setValue(palette["menu_button_font_size"])
        self.menu_button_padding.setValue(palette["menu_button_padding"])
        self.menu_columns.setValue(palette["menu_columns"])
        self.toolbar_color.setText(palette["toolbar_color"])
        self.toolbar_text_color.setText(palette["toolbar_text_color"])

    def _refresh_voucher_status(self):
        status = voucher_status()
        if status.get("activated"):
            suffix = status.get("voucher_suffix")
            activated_at = status.get("activated_at")
            text = "✅ البرنامج مفعل."
            if suffix:
                text += f"\nرمز مفعل منتهي بـ {suffix}."
            if activated_at:
                text += f"\nآخر تفعيل: {activated_at}"
            self.voucher_status.setStyleSheet("color: #A7F3D0; font-weight: 700;")
            self.btn_voucher_activate.setEnabled(False)
            self.btn_voucher_deactivate.setEnabled(True)
        else:
            text = "❌ لم يتم تفعيل النسخة بعد."
            self.voucher_status.setStyleSheet("color: #FFB4A2; font-weight: 700;")
            self.btn_voucher_activate.setEnabled(True)
            self.btn_voucher_deactivate.setEnabled(False)
        self.voucher_status.setText(text)

    def _open_voucher_dialog(self):
        dlg = VoucherDialog(status=voucher_status(), fatal=False, parent=self)
        dlg.exec()
        self._refresh_voucher_status()

    def _deactivate_voucher(self):
        if not is_activated():
            return
        confirm = QMessageBox.question(
            self,
            "تعطيل التفعيل",
            "سيتم تعطيل القسيمة الحالية، وستحتاج إلى إدخال رمز صالح قبل استخدام النظام مرة أخرى.\nهل أنت متأكد؟",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        deactivate()
        QMessageBox.information(self, "تم", "تم تعطيل التفعيل الحالي.")
        self._refresh_voucher_status()
