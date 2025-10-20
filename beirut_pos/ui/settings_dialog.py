# beirut_pos/ui/settings_dialog.py
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QFormLayout, QLineEdit, QSpinBox, QPushButton,
    QComboBox, QFileDialog, QTabWidget, QHBoxLayout, QLabel,
    QColorDialog, QListWidget, QAbstractItemView, QMessageBox,
    QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QAction, QKeySequence

from ..core.db import setting_get, setting_set, get_synchronous_mode, set_synchronous_mode
from ..core.simple_voucher import deactivate, is_activated, status as voucher_status
from ..core.bus import bus
from .common.big_dialog import BigDialog
from .common import branding
from ..services.orders import order_manager, get_category_order, set_category_order
from .voucher_dialog import VoucherDialog
import sys
from pathlib import Path

from ..core.paths import DB_PATH, BACKUP_DIR, CONFIG_DIR
from ..services.backup import backup_now, restore_backup


def _list_printers():
    if not sys.platform.startswith("win"):
        return []
    try:
        import win32print
        return [p[2] for p in win32print.EnumPrinters(
            win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    except Exception:
        return []


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
        tabs.addTab(ps, "البلايستيشن")

        # --- Branding tab ---
        br = QWidget()
        br_v = QVBoxLayout(br)
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

        def make_color_row(key: str, label: str, dialog_title: str):
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
            br_f.addRow(label, wrapper)
            return field

        self.accent_color = make_color_row("accent_color", "اللون الرئيسي:", "اختر اللون الرئيسي")
        self.surface_color = make_color_row("surface_color", "لون خلفية الواجهة:", "اختر لون لوحة التحكم")
        self.text_color = make_color_row("text_color", "لون النص:", "اختر لون النص")
        self.muted_text_color = make_color_row("muted_text_color", "لون النص الثانوي:", "اختر لون النص الثانوي")
        self.menu_card_color = make_color_row("menu_card_color", "لون بطاقات الأقسام:", "اختر لون بطاقات الأقسام")
        self.menu_header_color = make_color_row("menu_header_color", "لون عناوين الأقسام:", "اختر لون عنوان القسم")
        self.menu_button_color = make_color_row("menu_button_color", "لون أزرار المنتجات:", "اختر لون أزرار المنتجات")
        self.menu_button_text_color = make_color_row("menu_button_text_color", "لون خط أزرار المنتجات:", "اختر لون خط زر المنتج")
        self.menu_button_hover_color = make_color_row("menu_button_hover_color", "لون الزر عند التحويم:", "اختر لون الزر عند التحويم")
        self.toolbar_color = make_color_row("toolbar_color", "لون شريط الأدوات:", "اختر لون شريط الأدوات")
        self.toolbar_text_color = make_color_row("toolbar_text_color", "لون خط شريط الأدوات:", "اختر لون خط شريط الأدوات")

        reset_colors = QPushButton("استعادة الألوان الافتراضية")
        reset_colors.clicked.connect(self._reset_palette_fields)
        br_v.addWidget(reset_colors, 0, alignment=Qt.AlignmentFlag.AlignLeft)
        tabs.addTab(br, "الهوية")

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
        existing = [cat for cat, _ in order_manager.categories]
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
        toolbar_color = self.toolbar_color.text().strip()
        toolbar_text_color = self.toolbar_text_color.text().strip()

        setting_set("company_name", company)
        setting_set("currency", currency)
        setting_set("service_pct", service_pct)
        set_synchronous_mode(self.sync_mode.currentText().upper())
        setting_set("ps_rate_p2", str(self.ps_p2.value()))
        setting_set("ps_rate_p4", str(self.ps_p4.value()))
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
                "toolbar": toolbar_color,
                "toolbar_text": toolbar_text_color,
            },
        )
        bus.emit("catalog_changed")
        bus.emit("printers_changed", bar, cash)
        bus.emit("settings_saved")
        self.accept()

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
