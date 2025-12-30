from __future__ import annotations

from PyQt6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
    QScrollArea,
)
from PyQt6.QtCore import Qt

from .theme import (
    COLORS,
    DSAlert,
    DSButton,
    DSLinkButton,
    DSModal,
    DSSelect,
    DSTabWidget,
    DSTable,
    DSTextField,
    SPACING,
    TokenDocBlock,
    apply_typography,
)


class StyleGuideDialog(DSModal):
    """Showcase page for the design tokens and reusable components."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("دليل النمط")
        self.resize(1100, 820)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(SPACING.xl, SPACING.lg, SPACING.xl, SPACING.lg)
        outer.setSpacing(SPACING.lg)

        header = QLabel("مكتبة الواجهات")
        apply_typography(header, "display")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        scroll.setWidget(body)
        outer.addWidget(scroll)

        root = QVBoxLayout(body)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING.xl)

        self._build_tokens_section(root)
        self._build_buttons_section(root)
        self._build_inputs_section(root)
        self._build_alerts_section(root)
        self._build_tabs_section(root)
        self._build_table_section(root)

    def _build_tokens_section(self, root: QVBoxLayout):
        apply_typography(self._add_title(root, "الرموز الأساسية"), "title")

        wrapper = QHBoxLayout()
        wrapper.setSpacing(SPACING.md)

        colors_doc = TokenDocBlock(
            "الألوان",
            "استخدم primary لتأكيد الإجراءات، surface لواجهات الخلفية، وtext للألوان الرئيسية. على الحالات التحذيرية اختر warning، النجاح success، والخطر danger.",
        )
        colors_doc.setStyleSheet(f"QLabel {{ color: {COLORS.text}; }}")
        wrapper.addWidget(colors_doc)

        spacing_doc = TokenDocBlock(
            "التباعد والزوايا",
            "المسافات: sm للهوامش الصغيرة، md للكتل، lg للأقسام. نصف القطر md للعناصر الصغيرة، lg للأزرار والبطاقات.",
        )
        wrapper.addWidget(spacing_doc)

        type_doc = TokenDocBlock(
            "التدرج الطباعي",
            "display للعناوين الكبيرة، title لأقسام البطاقات، body للنصوص الأساسية، و caption للملاحظات.",
        )
        wrapper.addWidget(type_doc)

        root.addLayout(wrapper)

    def _build_buttons_section(self, root: QVBoxLayout):
        apply_typography(self._add_title(root, "الأزرار"), "title")
        row = QHBoxLayout()
        row.setSpacing(SPACING.md)

        row.addWidget(DSButton("أساسي"))
        row.addWidget(DSButton("ثانوي", variant="secondary"))
        disabled = DSButton("مُعطل")
        disabled.setEnabled(False)
        row.addWidget(disabled)
        row.addWidget(DSLinkButton("رابط نصي"))

        root.addLayout(row)

    def _build_inputs_section(self, root: QVBoxLayout):
        apply_typography(self._add_title(root, "الحقول"), "title")
        row = QHBoxLayout()
        row.setSpacing(SPACING.md)

        username = DSTextField("اسم المستخدم")
        password = DSTextField("كلمة المرور")
        password.setEchoMode(password.EchoMode.Password)
        select = DSSelect()
        select.addItems(["اختيار سريع", "حقل خيارات", "قيمة أخرى"])

        row.addWidget(username)
        row.addWidget(password)
        row.addWidget(select)
        root.addLayout(row)

    def _build_alerts_section(self, root: QVBoxLayout):
        apply_typography(self._add_title(root, "التنبيهات"), "title")
        row = QHBoxLayout()
        row.setSpacing(SPACING.md)

        row.addWidget(DSAlert("نجاح: تمت العملية بنجاح", severity="success"))
        row.addWidget(DSAlert("تحذير: تحقق من المدخلات", severity="warning"))
        row.addWidget(DSAlert("خطأ: حدثت مشكلة غير متوقعة", severity="danger"))
        root.addLayout(row)

    def _build_tabs_section(self, root: QVBoxLayout):
        apply_typography(self._add_title(root, "التبويبات"), "title")
        tabs = DSTabWidget()
        tabs.addTab(self._tab_content("معلومات"), "معلومات")
        tabs.addTab(self._tab_content("حالة"), "حالة")
        tabs.addTab(self._tab_content("إعدادات"), "إعدادات")
        root.addWidget(tabs)

    def _build_table_section(self, root: QVBoxLayout):
        apply_typography(self._add_title(root, "الجداول"), "title")
        table = DSTable(0, 3)
        table.set_headers(["العنصر", "الحالة", "السعر"])
        table.add_row(["اسبريسو", "جاهز", "$3.50"])
        table.add_row(["موكا", "قيد التحضير", "$4.25"])
        table.add_row(["لاتيه", "جاهز للتسليم", "$4.00"])
        root.addWidget(table)

    # helpers ---------------------------------------------------------------
    def _tab_content(self, text: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(SPACING.md, SPACING.md, SPACING.md, SPACING.md)
        layout.setSpacing(SPACING.sm)
        label = QLabel(f"مثال لمحتوى تبويب: {text}")
        apply_typography(label, "body")
        layout.addWidget(label)
        return widget

    def _add_title(self, layout: QVBoxLayout, text: str) -> QLabel:
        title = QLabel(text)
        title.setProperty("data-typo", "title")
        layout.addWidget(title)
        return title
