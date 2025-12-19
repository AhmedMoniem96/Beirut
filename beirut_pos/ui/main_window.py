# beirut_pos/ui/main_window.py
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QToolBar,
    QStackedWidget,
    QHBoxLayout,
    QPushButton,
    QFrame,
    QMessageBox,
    QLineEdit,
    QToolButton,
    QStyle,
)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QAction, QShortcut, QKeySequence
from .components.table_map import TableMap
from .components.category_grid import CategoryGrid
from .components.order_list import OrderList
from .components.payment_panel import PaymentPanel
from ..services.orders import order_manager, StockError, OrderError
from ..services.printer import printer
from ..services import reservations as reservations_service
from beirut_pos.services.texts import texts
from beirut_pos.services import settings as settings_service
from ..core.bus import bus
from .login_dialog import LoginDialog
from .catalog_manager_dialog import CatalogManagerDialog
from .discount_dialog import DiscountDialog
from .admin_users_dialog import AdminUsersDialog
from .admin_reports_dialog import AdminReportsDialog


# NEW: settings & daily Z-report dialogs
from .settings_dialog import SettingsDialog
# from .zreport_dialog import ZReportDialog
from .coffee_customizer import CoffeeCustomizerDialog
from .product_option_dialog import ProductOptionDialog
from .order_item_editor import OrderItemEditor
from .common.branding import get_logo_pixmap, get_logo_icon, build_main_window_stylesheet
from .common.barista_tips import random_tip
from .admin_tables_dialog import AdminTablesDialog
from .reservations_dialog import ReservationsDialog
from .merge_tables_dialog import MergeTablesDialog
from .purchases_dialog import PurchasesDialog
from .sugar_level_dialog import SugarLevelDialog
from .dialogs.table_history_dialog import TableHistoryDialog
from .recovery_center_dialog import RecoveryCenterDialog
from .shift_summary_dialog import ShiftSummaryDialog
from .inventory_dialog import InventoryDialog
from .style_guide_dialog import StyleGuideDialog
from ..services import staff as staff_service
from .command_palette import CommandPaletteDialog, build_command

PAGE_TABLES = 0
PAGE_ORDER = 1


class MainWindow(QMainWindow):
    def __init__(self, current_user):
        super().__init__()
        self.user = current_user
        self._active_session_id = None
        try:
            self._active_session_id = staff_service.start_session(self.user.username)
        except Exception:
            self._active_session_id = None
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1440, 900)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        self._apply_window_title()
        self.setStyleSheet(build_main_window_stylesheet())
        icon = get_logo_icon(64)
        if icon:
            self.setWindowIcon(icon)

        # Status bar + session timer
        self._status = self.statusBar()
        self._status.setSizeGripEnabled(False)
        self._status.showMessage(random_tip(), 12000)

        self._session_started = datetime.utcnow()
        self._session_label = QLabel()
        self._session_label.setObjectName("sessionTimer")
        self._status.addPermanentWidget(self._session_label)

        # Track tables where a cashier receipt was printed to lock destructive edits
        self._cashier_printed_tables: set[str] = set()

        self._session_timer = QTimer(self)
        self._session_timer.timeout.connect(self._update_session_timer)
        self._session_timer.start(1000)
        self._update_session_timer()

        # PlayStation snapshot timer (persist sessions periodically)
        self._ps_snapshot_timer = QTimer(self)
        self._ps_snapshot_timer.setInterval(5000)
        self._ps_snapshot_timer.timeout.connect(self._on_ps_snapshot)
        self._ps_snapshot_timer.start()

        # Tool bar
        bar = QToolBar("Main")
        self.addToolBar(bar)
        self.logo_label = QLabel()
        self.logo_label.setObjectName("appLogo")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar.addWidget(self.logo_label)
        bar.addSeparator()

        self.act_back = QAction(self)
        self.act_back.triggered.connect(self._go_back)
        self.act_back.setVisible(False)
        bar.addAction(self.act_back)
        self.act_switch = QAction(self)
        self.act_switch.triggered.connect(self._switch_user)
        bar.addAction(self.act_switch)
        self.act_manage = QAction(self)
        self.act_manage.triggered.connect(self._open_manage_products)
        self.act_users = QAction(self)
        self.act_users.triggered.connect(self._open_users)
        self.act_reports = QAction(self)
        self.act_reports.triggered.connect(self._open_reports)
        self.act_tables = QAction(self)
        self.act_tables.triggered.connect(self._open_tables_admin)
        self.act_purchases = QAction(self)
        self.act_purchases.triggered.connect(self._open_purchases)
        self.act_inventory = QAction(self)
        self.act_inventory.triggered.connect(self._open_inventory)
        self.act_reservations = QAction(self)
        self.act_reservations.triggered.connect(self._open_reservations)
        self.act_style_guide = QAction(self)
        self.act_style_guide.triggered.connect(self._open_style_guide)

        # NEW: Settings & Daily Z-Report (admin only)
        self.act_settings = QAction(self)
        self.act_settings.triggered.connect(self._open_settings)
        self.act_recovery = QAction(self)
        self.act_recovery.triggered.connect(self._open_recovery_center)

        self._admin_actions = [
            self.act_manage,
            self.act_users,
            self.act_reports,
            self.act_tables,
            self.act_purchases,
            self.act_settings,
            self.act_recovery,
            self.act_style_guide,
        ]
        for action in self._admin_actions:
            action.setVisible(self.user.role == "admin")
            bar.addAction(action)
        bar.addAction(self.act_inventory)
        bar.addAction(self.act_reservations)

        # Hotkeys
        QShortcut(QKeySequence("Esc"), self, activated=self._go_back)
        QShortcut(QKeySequence("F2"), self, activated=self._print_bar)
        QShortcut(QKeySequence("F3"), self, activated=self._print_cashier)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self._on_discount)
        QShortcut(QKeySequence("Del"), self, activated=self._remove_selected_or_last)
        QShortcut(QKeySequence("Ctrl+L"), self, activated=self._switch_user)
        QShortcut(QKeySequence("Ctrl+Shift+R"), self, activated=self._open_reports)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, activated=self._open_settings)
        QShortcut(QKeySequence("Ctrl+Shift+T"), self, activated=self._open_tables_admin)
        QShortcut(QKeySequence("Ctrl+Shift+B"), self, activated=self._open_recovery_center)
        QShortcut(QKeySequence("Ctrl+/"), self, activated=self._show_hotkeys_help)
        QShortcut(QKeySequence("Ctrl+K"), self, activated=self._open_command_palette)

        # Primary navigation (side panel)
        self._nav_panel = self._build_nav_panel()
        self._nav_collapsed = False

        # Layouts
        container = QWidget()
        container.setObjectName("MainContainer")
        root_layout = QHBoxLayout(container)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(8)

        root_layout.addWidget(self._nav_panel, 0)

        content_holder = QVBoxLayout()
        content_holder.setContentsMargins(0, 0, 0, 0)
        content_holder.setSpacing(8)

        self._page_header = self._build_page_header()
        self.pages = QStackedWidget()

        self.banner = QFrame()
        self.banner.setObjectName("ToastBanner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(18, 12, 12, 12)
        banner_layout.setSpacing(12)
        self.banner_label = QLabel()
        self.banner_label.setWordWrap(True)
        self.banner_close = QPushButton()
        self.banner_close.setFixedWidth(36)
        self.banner_close.setFlat(True)
        self.banner_close.clicked.connect(self._hide_banner)
        banner_layout.addWidget(self.banner_label, 1)
        banner_layout.addWidget(self.banner_close, 0, alignment=Qt.AlignmentFlag.AlignTop)
        self.banner.setVisible(False)

        content_holder.addWidget(self._page_header)
        content_holder.addWidget(self.banner, 0)
        content_holder.addWidget(self.pages, 1)

        root_layout.addLayout(content_holder, 1)

        self.banner_timer = QTimer(self)
        self.banner_timer.setSingleShot(True)
        self.banner_timer.timeout.connect(self._hide_banner)
        self._banner_durations = {
            "info": 6000,
            "success": 4800,
            "warn": 7000,
            "error": 8200,
        }

        self.setCentralWidget(container)

        # Tables page
        tables_page = QWidget()
        tables_page.setObjectName("TablesPage")
        tv = QVBoxLayout(tables_page)
        self.tables_title = QLabel()
        self.tables_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tv.addWidget(self.tables_title)
        self.table_codes = order_manager.get_table_codes()
        self.table_map = TableMap(self.table_codes, self._on_table_select)
        self.table_map.set_client_names(order_manager.list_client_names())
        tv.addWidget(self.table_map, 1)
        self._refresh_reservation_overlays()

        # Try to restore PS session for currently selected table (if any)
        try:
            if getattr(self, "current_table", None):
                sess = order_manager.load_ps_session_from_db(self.current_table)
                self._update_table_ps_display(self.current_table, sess)
        except Exception:
            # ignore restore errors during startup
            pass

        # Order page - REDESIGNED for maximum products space
        order_page = QWidget()
        order_page.setObjectName("OrderPage")
        ov = QVBoxLayout(order_page)
        ov.setContentsMargins(0, 0, 0, 0)
        ov.setSpacing(8)

        # Compact header with all buttons in ONE row
        head_row = QHBoxLayout()
        head_row.setSpacing(6)
        self.order_header = QLabel()
        self.order_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.order_header.setMinimumWidth(120)
        head_row.addWidget(self.order_header, 0)

        self.client_name_edit = QLineEdit()
        self.client_name_edit.setPlaceholderText("اسم العميل")
        self.client_name_edit.setClearButtonEnabled(True)
        self.client_name_edit.setFixedWidth(200)
        self.client_name_edit.setEnabled(False)
        self.client_name_edit.editingFinished.connect(self._commit_client_name)
        head_row.addWidget(self.client_name_edit, 0)

        # All action buttons together
        self.btn_print_bar = QPushButton()
        self.btn_print_bar.setToolTip("طباعة تذكرة البار")
        self.btn_print_bar.clicked.connect(self._print_bar)
        head_row.addWidget(self.btn_print_bar, 0)

        self.btn_print_cashier = QPushButton()
        self.btn_print_cashier.setToolTip("طباعة إيصال الكاشير")
        self.btn_print_cashier.clicked.connect(self._print_cashier)
        head_row.addWidget(self.btn_print_cashier, 0)

        # PS CONTROLS - RESTORED (only on order page)
        self.btn_ps_p2 = QPushButton("PS P2")
        self.btn_ps_p2.setToolTip("بدء PlayStation 2 ساعات")
        self.btn_ps_p2.clicked.connect(lambda: self._ps_start("P2"))
        self.btn_ps_p2.setEnabled(False)
        head_row.addWidget(self.btn_ps_p2, 0)

        self.btn_ps_p4 = QPushButton("PS P4")
        self.btn_ps_p4.setToolTip("بدء PlayStation 4 ساعات")
        self.btn_ps_p4.clicked.connect(lambda: self._ps_start("P4"))
        self.btn_ps_p4.setEnabled(False)
        head_row.addWidget(self.btn_ps_p4, 0)

        self.btn_ps_stop = QPushButton("إيقاف PS")
        self.btn_ps_stop.setToolTip("إيقاف PlayStation")
        self.btn_ps_stop.clicked.connect(self._ps_stop)
        self.btn_ps_stop.setEnabled(False)
        head_row.addWidget(self.btn_ps_stop, 0)

        self.btn_merge = QPushButton("🔀 دمج")
        self.btn_merge.setToolTip("دمج مع طاولة أخرى")
        self.btn_merge.clicked.connect(self._on_merge_tables)
        self.btn_merge.setEnabled(False)
        head_row.addWidget(self.btn_merge, 0)

        self.btn_table_history = QPushButton()
        self.btn_table_history.clicked.connect(self._open_table_history)
        self.btn_table_history.setEnabled(False)
        head_row.addWidget(self.btn_table_history, 0)

        self.btn_clear_table = QPushButton()
        self.btn_clear_table.clicked.connect(self._on_clear_table)
        self.btn_clear_table.setEnabled(False)
        head_row.addWidget(self.btn_clear_table, 0)

        self.back_big = QPushButton()
        self.back_big.clicked.connect(self._go_back)
        head_row.addWidget(self.back_big, 0)

        head_row.addStretch(1)
        ov.addLayout(head_row, 0)

        # Main content: 2 columns (products + order details)
        main_row = QHBoxLayout()
        main_row.setSpacing(8)

        # LEFT: Products grid - MAXIMUM space (65% width)
        self.cat_grid = CategoryGrid(order_manager.categories, self._on_pick)
        main_row.addWidget(self.cat_grid, 13)

        # RIGHT COLUMN: Order list + Payment (compact - 30% width)
        right_col = QVBoxLayout()
        right_col.setSpacing(6)

        self.order_list = OrderList(self._on_remove, self._on_edit_item)
        self.order_list.list.setMinimumHeight(150)
        right_col.addWidget(self.order_list, 1)

        self.payment = PaymentPanel(self._on_pay, self._on_discount)
        right_col.addWidget(self.payment, 0)

        main_row.addLayout(right_col, 3)

        ov.addLayout(main_row, 1)

        self.pages.addWidget(tables_page)
        self.pages.addWidget(order_page)
        self.pages.setCurrentIndex(PAGE_TABLES)

        # Bus listeners
        bus.subscribe("table_total_changed", self._on_table_total_changed)
        bus.subscribe("table_state_changed", self._on_table_state_changed)
        bus.subscribe("catalog_changed", self._on_catalog_changed)
        bus.subscribe("ps_state_changed", self._on_ps_state_changed)
        bus.subscribe("inventory_low", self._on_inventory_low)
        bus.subscribe("inventory_recovered", self._on_inventory_recovered)
        bus.subscribe("branding_changed", self._on_branding_changed)
        bus.subscribe("settings_saved", self._on_settings_saved)
        bus.subscribe("tables_changed", self._on_tables_changed)
        bus.subscribe("reservations_changed", self._on_reservations_changed)
        bus.subscribe("ui_texts_changed", self._apply_texts)
        bus.subscribe("client_branding_changed", self._apply_texts)
        bus.subscribe("table_client_name_changed", self._on_table_client_name_changed)

        self.current_table = None
        self._edit_locked = False
        self._coffee_categories = {"Coffee Corner", "Hot Drinks", "Fresh Drinks"}

        # Initial state for print buttons
        self._refresh_print_buttons()
        self._refresh_branding()
        self._apply_texts()
        self._refresh_nav_selection("tables")
        self._update_breadcrumbs()
        self._update_nav_collapsed()

    # ---------------- layout helpers ----------------
    def _build_page_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("PageHeader")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        self.page_title_label = QLabel(texts.get("app.window_title_fallback", "Beirut POS"))
        self.page_title_label.setObjectName("PageTitle")
        self.page_title_label.setMinimumWidth(200)

        self.breadcrumbs_label = QLabel()
        self.breadcrumbs_label.setObjectName("Breadcrumbs")
        self.breadcrumbs_label.setStyleSheet("color: #666;")
        self.breadcrumbs_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(self.page_title_label, 0)
        layout.addWidget(self.breadcrumbs_label, 1)

        self.command_palette_btn = QPushButton("بحث سريع (Ctrl+K)")
        self.command_palette_btn.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
        )
        self.command_palette_btn.clicked.connect(self._open_command_palette)
        layout.addWidget(self.command_palette_btn, 0)

        return header

    def _build_nav_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("SideNavigation")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._nav_buttons: dict[str, QToolButton] = {}

        self._nav_toggle = QToolButton(panel)
        self._nav_toggle.setText("≡")
        self._nav_toggle.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarMenuButton)
        )
        self._nav_toggle.setCheckable(True)
        self._nav_toggle.clicked.connect(
            lambda: self._update_nav_collapsed(not self._nav_collapsed)
        )
        layout.addWidget(self._nav_toggle, 0, alignment=Qt.AlignmentFlag.AlignLeft)

        nav_items = [
            {
                "key": "tables",
                "text": texts.get("main.tables.title", "الطاولات"),
                "icon": QStyle.StandardPixmap.SP_FileDialogDetailedView,
                "handler": self._go_back,
                "admin": False,
            },
            {
                "key": "reservations",
                "text": texts.get("main.toolbar.reservations", "الحجوزات"),
                "icon": QStyle.StandardPixmap.SP_DialogYesButton,
                "handler": self._open_reservations,
                "admin": False,
            },
            {
                "key": "inventory",
                "text": texts.get("main.toolbar.inventory", "المخزون"),
                "icon": QStyle.StandardPixmap.SP_DriveHDIcon,
                "handler": self._open_inventory,
                "admin": True,
            },
            {
                "key": "reports",
                "text": texts.get("main.toolbar.reports", "التقارير"),
                "icon": QStyle.StandardPixmap.SP_FileDialogInfoView,
                "handler": self._open_reports,
                "admin": True,
            },
            {
                "key": "purchases",
                "text": texts.get("main.toolbar.purchases", "المشتريات"),
                "icon": QStyle.StandardPixmap.SP_FileDialogListView,
                "handler": self._open_purchases,
                "admin": True,
            },
            {
                "key": "tables_admin",
                "text": texts.get("main.toolbar.tables", "إدارة الطاولات"),
                "icon": QStyle.StandardPixmap.SP_DesktopIcon,
                "handler": self._open_tables_admin,
                "admin": True,
            },
            {
                "key": "settings",
                "text": texts.get("main.toolbar.settings", "الإعدادات"),
                "icon": QStyle.StandardPixmap.SP_FileDialogDetailedView,
                "handler": self._open_settings,
                "admin": True,
            },
            {
                "key": "recovery",
                "text": texts.get("main.toolbar.recovery", "مركز الاستعادة"),
                "icon": QStyle.StandardPixmap.SP_DialogResetButton,
                "handler": self._open_recovery_center,
                "admin": True,
            },
        ]

        for item in nav_items:
            if item.get("admin") and self.user.role != "admin":
                continue
            btn = QToolButton(panel)
            btn.setCheckable(True)
            btn.setIcon(self.style().standardIcon(item["icon"]))
            btn.setIconSize(QSize(20, 20))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setText(item["text"])
            btn.setProperty("navKey", item["key"])
            btn.setProperty("fullText", item["text"])
            btn.clicked.connect(item["handler"])
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._nav_buttons[item["key"]] = btn
            layout.addWidget(btn, 0)

        layout.addStretch(1)
        return panel

    def _apply_navigation_texts(self):
        labels = {
            "tables": texts.get("main.tables.title", "الطاولات"),
            "reservations": texts.get("main.toolbar.reservations", "الحجوزات"),
            "inventory": texts.get("main.toolbar.inventory", "المخزون"),
            "reports": texts.get("main.toolbar.reports", "التقارير"),
            "purchases": texts.get("main.toolbar.purchases", "المشتريات"),
            "tables_admin": texts.get("main.toolbar.tables", "إدارة الطاولات"),
            "settings": texts.get("main.toolbar.settings", "الإعدادات"),
            "recovery": texts.get("main.toolbar.recovery", "مركز الاستعادة"),
        }
        for key, btn in self._nav_buttons.items():
            full_text = labels.get(key, btn.text())
            btn.setProperty("fullText", full_text)
            if not self._nav_collapsed:
                btn.setText(full_text)
        self.command_palette_btn.setText(texts.get("main.toolbar.search", "بحث سريع (Ctrl+K)"))
        self._sync_nav_collapse_state()

    def _sync_nav_collapse_state(self):
        for btn in self._nav_buttons.values():
            full_text = btn.property("fullText") or btn.text()
            if self._nav_collapsed:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                btn.setText("")
            else:
                btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
                btn.setText(full_text)
        self._nav_toggle.setChecked(self._nav_collapsed)

    def _update_nav_collapsed(self, collapse: bool | None = None):
        if collapse is None:
            collapse = self.width() < 1100
        if collapse == self._nav_collapsed:
            self._nav_panel.setFixedWidth(68 if collapse else 220)
            self._sync_nav_collapse_state()
            return
        self._nav_collapsed = collapse
        self._nav_panel.setFixedWidth(68 if collapse else 220)
        self._sync_nav_collapse_state()

    def resizeEvent(self, event):  # noqa: D401 - Qt lifecycle hook
        super().resizeEvent(event)
        self._update_nav_collapsed()

    def _refresh_nav_selection(self, key: str):
        for nav_key, btn in self._nav_buttons.items():
            btn.setChecked(nav_key == key)

    def _update_breadcrumbs(self):
        if not hasattr(self, "breadcrumbs_label"):
            return
        client = settings_service.get_client_name()
        base = texts.get("app.window_title_fallback", client_name=client)
        trail = [base]
        page_title = texts.get("main.tables.title", "الطاولات")

        if self.pages.currentIndex() == PAGE_ORDER:
            page_title = texts.get("main.order.header", "الطلبات")
            trail.append(texts.get("main.tables.title", "الطاولات"))
            if self.current_table:
                client_name = order_manager.get_client_name(self.current_table)
                label = self.current_table
                if client_name:
                    label = f"{label} — {client_name}"
                trail.append(label)
        else:
            trail.append(texts.get("main.tables.title", "الطاولات"))

        self.page_title_label.setText(page_title)
        self.breadcrumbs_label.setText(" › ".join(trail))

    def _build_command_entries(self):
        entries = [
            build_command(
                texts.get("main.tables.title", "الطاولات"),
                self._go_back,
                subtitle="العودة لشاشة الطاولات",
            ),
            build_command(
                texts.get("main.toolbar.reservations", "الحجوزات"),
                self._open_reservations,
                shortcut="Ctrl+Shift+V",
                subtitle="عرض وإدارة الحجوزات",
            ),
        ]

        if self.user.role == "admin":
            entries.extend(
                [
                    build_command(
                        texts.get("main.toolbar.inventory", "المخزون"),
                        self._open_inventory,
                        subtitle="تنبيهات المخزون وإعادة الترتيب",
                    ),
                    build_command(
                        texts.get("main.toolbar.reports", "التقارير"),
                        self._open_reports,
                        shortcut="Ctrl+Shift+R",
                        subtitle="عرض الملخصات اليومية",  
                    ),
                    build_command(
                        texts.get("main.toolbar.purchases", "المشتريات"),
                        self._open_purchases,
                        subtitle="إدارة المشتريات والفواتير",
                    ),
                    build_command(
                        texts.get("main.toolbar.tables", "إدارة الطاولات"),
                        self._open_tables_admin,
                        shortcut="Ctrl+Shift+T",
                        subtitle="إضافة أو تعديل الطاولات",
                    ),
                    build_command(
                        texts.get("main.toolbar.settings", "الإعدادات"),
                        self._open_settings,
                        shortcut="Ctrl+Shift+S",
                        subtitle="تعديل الهوية البصرية والإعدادات العامة",
                    ),
                    build_command(
                        texts.get("main.toolbar.recovery", "مركز الاستعادة"),
                        self._open_recovery_center,
                        shortcut="Ctrl+Shift+B",
                        subtitle="استرجاع النسخ الاحتياطية",
                    ),
                ]
            )
        return entries

    def _open_command_palette(self):
        dlg = CommandPaletteDialog(self._build_command_entries(), parent=self)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        selection = dlg.selected_command()
        if selection and selection.get("handler"):
            handler = selection["handler"]
            try:
                handler()
            except Exception:
                self._show_banner("تعذر تنفيذ الأمر المختار.", "error")

    # ---------------- helpers: printing ----------------
    def _refresh_print_buttons(self):
        has_items = bool(self.current_table and order_manager.get_items(self.current_table))
        self.btn_print_bar.setEnabled(has_items)
        self.btn_print_cashier.setEnabled(has_items)
        self._refresh_history_button()

    def _is_cashier_locked(self, table_code: str | None = None) -> bool:
        """Return True if a cashier receipt was printed for the open order on *table_code*."""

        code = (table_code or self.current_table or "").strip()
        if not code:
            return False

        order = order_manager.orders.get(code)
        if not order or getattr(order, "status", "") != "open":
            self._cashier_printed_tables.discard(code)
            return False

        return code in self._cashier_printed_tables

    def _user_can_edit_orders(self) -> bool:
        """Return True if the current user role is allowed to edit order items here."""
        return self.user.role in {"admin", "cashier"}

    def _update_client_name_field(self):
        if not hasattr(self, "client_name_edit"):
            return
        self.client_name_edit.blockSignals(True)
        if not self.current_table:
            self.client_name_edit.clear()
            self.client_name_edit.setEnabled(False)
            self.order_list.set_table("", None)
        else:
            name = order_manager.get_client_name(self.current_table)
            self.client_name_edit.setText(name)
            self.client_name_edit.setEnabled(True)
            self.order_list.set_table(self.current_table, name)
        self.client_name_edit.blockSignals(False)
        self._apply_order_header()
        self._update_breadcrumbs()

    def _commit_client_name(self):
        if not self.current_table:
            self._update_client_name_field()
            return
        name = (self.client_name_edit.text() or "").strip()
        order_manager.set_client_name(self.current_table, name, actor=self.user.username)
        self._update_client_name_field()

    def _refresh_history_button(self):
        self.btn_table_history.setEnabled(bool(self.current_table))

    def _refresh_edit_lock_state(self):
        message = texts.get("orders.edit_locked")
        table_editable = bool(self.current_table) and order_manager.can_edit(self.current_table)
        locked = bool(self.current_table) and not table_editable
        cashier_locked = self._is_cashier_locked(self.current_table)

        # Edit button: requires both order window availability and user role permission.
        edit_btn = self.order_list.edit_btn
        can_edit_role = self._user_can_edit_orders()
        edit_btn.setEnabled(table_editable and can_edit_role)
        if not can_edit_role and self.current_table:
            edit_btn.setToolTip("التعديل متاح للمدير أو الكاشير فقط.")
        else:
            edit_btn.setToolTip(message if locked else "")

        # Deleting items is blocked once a cashier receipt was printed for the order.
        delete_btn = self.order_list.remove_btn
        cashier_tip = "تم طباعة إيصال الكاشير، لا يمكن الحذف قبل إغلاق الطلب."
        delete_btn.setEnabled(table_editable and not cashier_locked)
        delete_btn.setToolTip(cashier_tip if cashier_locked else (message if locked else ""))

        # Discount button still follows the order window availability only.
        other_targets = [self.payment.discount_btn]
        for btn in other_targets:
            btn.setEnabled(table_editable)
            btn.setToolTip(message if locked else "")

        if locked and not self._edit_locked:
            self._show_banner(message, "warn", duration=6000)
        if not locked and self._edit_locked:
            for btn in [edit_btn, *other_targets]:
                # Clear tips that may have been set because of the lock state.
                if btn.toolTip() == message:
                    btn.setToolTip("")
        self._edit_locked = locked

    def _update_totals(self, table_code: str | None = None):
        """Refresh subtotal/discount/total summaries for the active table."""

        if table_code is None:
            table_code = self.current_table

        if not table_code:
            label_text = texts.get("orders.discount_label_amount")
            self.order_list.set_totals(0, 0, 0, label_text)
            self.payment.set_totals(0, 0, 0, label_text)
            self._refresh_edit_lock_state()
            return 0, 0, 0, "orders.discount_label_amount"

        subtotal, discount, total, label_key = order_manager.get_totals(table_code)
        label_text = texts.get(label_key)
        if table_code == self.current_table:
            self.order_list.set_totals(subtotal, discount, total, label_text)
            self.payment.set_totals(subtotal, discount, total, label_text)
            self._refresh_edit_lock_state()
        return subtotal, discount, total, label_key

    def _print_bar(self):
        if not self.current_table:
            self._show_banner("اختر طاولة أولاً قبل الطباعة.", "warn")
            return

        to_print = self._collect_unprinted_items(self.current_table)
        if not to_print:
            self._show_banner("لا توجد عناصر جديدة للطباعة.", "info")
            return

        try:
            printer.print_bar_ticket(self.current_table, to_print)
        except Exception as exc:
            self._handle_printer_error(exc, context="طلب البار")
            return
        try:
            order_manager.mark_bar_items_as_printed(self.current_table, to_print)
        except Exception:
            pass

        self.order_list.set_items(order_manager.get_items(self.current_table))
        self._refresh_print_buttons()
        self._show_banner("تم إرسال العناصر الجديدة للبار.", "success")

    def _print_cashier(self):
        if not self.current_table:
            self._show_banner("اختر طاولة أولاً قبل الطباعة.", "warn")
            return
        items = order_manager.get_items(self.current_table)
        if not items:
            self._show_banner("لا توجد عناصر في الطلب الحالي.", "warn")
            return
        sub, disc, tot, label_key = self._update_totals(self.current_table)
        try:
            printer.print_cashier_receipt(
                self.current_table,
                items,
                sub,
                disc,
                tot,
                method="manual",
                cashier=self.user.username,
                discount_label=texts.get(label_key),
            )
        except Exception as exc:
            self._handle_printer_error(exc, context="إيصال الكاشير")
            return
        self._cashier_printed_tables.add(self.current_table)
        self._refresh_edit_lock_state()
        self._show_banner("تم إرسال إيصال الكاشير للطابعة.", "success")

    def _remove_selected_or_last(self):
        if not self.current_table:
            return
        if self._is_cashier_locked(self.current_table):
            self._show_banner("تم طباعة إيصال الكاشير، لا يمكن حذف العناصر قبل إنهاء الطلب.", "warn")
            return
        idx = -1
        if hasattr(self.order_list, "current_index"):
            try:
                idx = int(self.order_list.current_index())
            except Exception:
                idx = -1
        if idx < 0:
            items = order_manager.get_items(self.current_table)
            idx = len(items) - 1
        if idx >= 0:
            self._on_remove(idx)

    # Navigation/Admin
    def _go_back(self):
        self.pages.setCurrentIndex(PAGE_TABLES)
        self.act_back.setVisible(False)
        self.table_map.clear_selection()
        self.current_table = None
        self._update_client_name_field()
        self._refresh_edit_lock_state()
        self._apply_order_header()
        self._refresh_print_buttons()
        self._update_ps_buttons_state()
        self._status.showMessage(random_tip(), 10000)
        self.btn_merge.setEnabled(False)
        self.btn_clear_table.setEnabled(False)
        self._refresh_nav_selection("tables")
        self._update_breadcrumbs()

    def _open_table_history(self):
        if not self.current_table:
            return
        dlg = TableHistoryDialog(self.current_table, parent=self)
        dlg.exec()

    def _switch_user(self):
        self._show_shift_summary()
        dlg = LoginDialog()
        if dlg.exec() == dlg.DialogCode.Accepted:
            try:
                staff_service.end_session(self._active_session_id)
            except Exception:
                pass
            self.user = dlg.get_user()
            try:
                self._active_session_id = staff_service.start_session(self.user.username)
            except Exception:
                self._active_session_id = None
            self._apply_window_title()
            for action in self._admin_actions:
                action.setVisible(self.user.role == "admin")
            self._session_started = datetime.utcnow()
            self._update_session_timer()
            if self.current_table:
                try:
                    order_manager.reload_table_items(self.current_table)
                except Exception:
                    pass
                self.order_list.set_items(order_manager.get_items(self.current_table))
                self._update_totals(self.current_table)
            self._update_client_name_field()
            self._refresh_print_buttons()
            self._apply_order_header()
            if self.current_table:
                self._update_ps_buttons_state()
            self._refresh_edit_lock_state()
            self.btn_clear_table.setEnabled(bool(self.current_table))

    def _open_manage_products(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        CatalogManagerDialog(actor=self.user.username, parent=self).exec()

    def _open_users(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        from .admin_users_dialog import AdminUsersDialog
        AdminUsersDialog(self.user.username).exec()

    def _open_reports(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        from .admin_reports_dialog import AdminReportsDialog
        AdminReportsDialog(actor_username=self.user.username).exec()

    def _open_tables_admin(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        AdminTablesDialog(actor=self.user.username, parent=self).exec()

    def _open_purchases(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        PurchasesDialog(actor=self.user.username, parent=self).exec()

    def _open_inventory(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        InventoryDialog(actor=self.user.username, parent=self).exec()

    def _open_reservations(self):
        ReservationsDialog(parent=self).exec()

    def _open_recovery_center(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        dialog = RecoveryCenterDialog(parent=self)
        dialog.exec()
        if dialog.restored_path:
            self.close()

    def _show_shift_summary(self):
        if not getattr(self, "user", None):
            return
        if not isinstance(self._session_started, datetime):
            return
        username = getattr(self.user, "username", "")
        metrics = staff_service.summarize_shift_activity(
            username,
            self._session_started,
            datetime.utcnow(),
        )
        if metrics.get("duration_seconds", 0) <= 0 and metrics.get("orders_opened", 0) <= 0:
            return
        ShiftSummaryDialog(username, metrics, parent=self).exec()

    def _open_settings(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        SettingsDialog(self).exec()

    def _open_style_guide(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        StyleGuideDialog(self).exec()

    # POS flow
    def _on_table_select(self, code):
        self.current_table = code
        self._update_client_name_field()
        self.act_back.setVisible(True)
        self.order_list.set_items(order_manager.get_items(code))
        self._update_totals(code)
        self._update_table_ps_display(code)
        self._update_ps_buttons_state()
        self.pages.setCurrentIndex(PAGE_ORDER)
        self._refresh_print_buttons()
        self._status.showMessage(random_tip(), 9000)
        self.btn_merge.setEnabled(True)
        self.btn_clear_table.setEnabled(True)
        self._refresh_nav_selection("tables")
        self._update_breadcrumbs()

    def _on_pick(self, label, price_cents):
        if not self.current_table:
            self._show_banner("اختر طاولة لإضافة الطلب.", "warn")
            return
        prod = order_manager.catalog.get_product_with_options(label)
        final_label = label
        final_price = price_cents
        notes: list[str] = []

        if prod and prod.get("product_type"):
            notes.append(f"نوع: {prod['product_type']}")

        if prod and prod.get("customizable") and prod.get("options"):
            dlg = ProductOptionDialog(label, price_cents, prod["options"], self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                return
            selection = dlg.get_selection()
            if not selection:
                return
            final_price = price_cents + selection["price_delta_cents"]
            if selection["note"]:
                notes.append(selection["note"])

        sugar_levels = prod.get("sugar_levels") if prod else []
        if sugar_levels:
            dlg = SugarLevelDialog(final_label, sugar_levels, self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                return
            level = dlg.selected_level()
            if level:
                notes.append(f"سكر: {level}")

        if prod and prod.get("category") in self._coffee_categories:
            dlg = CoffeeCustomizerDialog(final_label, final_price, self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                return
            selection = dlg.get_result()
            if not selection:
                return
            final_label = selection.label
            final_price = final_price + selection.price_delta
            if selection.note:
                notes.append(selection.note)

        note = "؛ ".join(n for n in notes if n)
        try:
            order_manager.add_item(
                self.current_table,
                final_label,
                final_price,
                cashier=self.user.username,
                note=note,
            )
        except StockError as e:
            self._show_banner(str(e), "error", duration=8000)
            return
        except OrderError as exc:
            self._show_banner(str(exc), "error", duration=8000)
            return
        self.order_list.set_items(order_manager.get_items(self.current_table))
        self._update_totals()
        self._refresh_print_buttons()

    def _on_remove(self, index):
        if not self.current_table:
            self._show_banner("اختر طاولة لإزالة العناصر.", "warn")
            return
        if self._is_cashier_locked(self.current_table):
            self._show_banner("تم طباعة إيصال الكاشير، لا يمكن حذف العناصر قبل إنهاء الطلب.", "warn")
            return
        try:
            order_manager.remove_item(self.current_table, index, username=self.user.username)
        except OrderError as exc:
            self._show_banner(str(exc), "error", duration=8000)
            return
        self.order_list.set_items(order_manager.get_items(self.current_table))
        self._update_totals()
        self._refresh_print_buttons()

    def _on_merge_tables(self):
        if not self.current_table:
            self._show_banner("اختر طاولة أولاً لإجراء الدمج.", "warn")
            return
        candidates = order_manager.list_open_tables_with_totals(self.current_table)
        if not candidates:
            self._show_banner("لا توجد طاولات أخرى مشغولة لدمجها.", "info")
            return
        open_tables = set(order_manager.list_open_tables(exclude=self.current_table))
        free_tables = [
            code
            for code in order_manager.get_table_codes()
            if code != self.current_table and code not in open_tables
        ]
        dlg = MergeTablesDialog(self.current_table, candidates, self, free_tables=free_tables)
        if dlg.exec() != dlg.DialogCode.Accepted:
            return
        action = dlg.selected_action()
        if not action:
            return
        mode, target = action
        if mode == "merge":
            if not order_manager.merge_tables(self.current_table, target, username=self.user.username):
                self._show_banner("تعذر دمج الطاولتين. تأكد أن كلاهما يحتويان على طلبات مفتوحة.", "error",
                                  duration=8000)
                return
            self.table_map.update_table(target, state="free", total_cents=0)
            self.order_list.set_items(order_manager.get_items(self.current_table))
            self._update_totals()
            self._refresh_print_buttons()
            self._show_banner(f"تم دمج الطاولة {target} مع {self.current_table} بنجاح.", "success")
        else:
            if not order_manager.move_table(self.current_table, target, username=self.user.username):
                self._show_banner("تعذر نقل الطلب إلى الطاولة الجديدة.", "error", duration=8000)
                return
            if self.current_table in self.table_map.tiles:
                self.table_map.tiles[self.current_table].set_checked(False)
            self.table_map.update_table(self.current_table, state="free", total_cents=0)
            self._on_table_select(target)
            if target in self.table_map.tiles:
                self.table_map.tiles[target].set_checked(True)
            self._show_banner(f"تم نقل الطلب إلى الطاولة {target} بنجاح.", "success")

    def _on_clear_table(self) -> None:
        if not self.current_table:
            self._show_banner(texts.get("main.order.clear_table_warn", "اختر طاولة لتفريغها."), "warn")
            return

        confirm = QMessageBox.question(
            self,
            texts.get("main.order.clear_table", "تفريغ الطاولة"),
            texts.get(
                "main.order.clear_table_confirm",
                "سيتم حذف الطلب الحالي وإعادة الطاولة للوضع الحر. هل تريد المتابعة؟",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        cleared_table = self.current_table
        try:
            order_manager.empty_table(cleared_table, username=self.user.username)
        except OrderError as exc:
            self._show_banner(str(exc), "error", duration=8000)
            return

        self._cashier_printed_tables.discard(cleared_table)
        self._go_back()
        self._show_banner(texts.get("main.order.clear_table_success"), "success")

    def _on_edit_item(self, index: int) -> None:
        if not self.current_table:
            self._show_banner("اختر طاولة لتعديل العناصر.", "warn")
            return

        if not self._user_can_edit_orders():
            self._show_banner("التعديل متاح للمدير أو الكاشير فقط.", "warn", duration=6000)
            return

        if not order_manager.can_edit(self.current_table):
            locked_msg = texts.get("orders.edit_locked", "انتهت مدة التعديل") if texts else "انتهت مدة التعديل"
            self._show_banner(locked_msg, "warn")
            return

        items = order_manager.get_items(self.current_table)
        if not (0 <= index < len(items)):
            return

        item = items[index]
        order = order_manager.orders.get(self.current_table)
        editable_until = order.editable_until if order else None

        editor = OrderItemEditor(
            item.product,
            item.qty,
            item.note or "",
            editable_until=editable_until,
            is_admin=self.user.role == "admin",
            parent=self,
        )
        if editor.exec() != editor.DialogCode.Accepted:
            return

        values = editor.get_values() or {}

        try:
            order_manager.update_item(
                self.current_table,
                index,
                qty=values.get("qty"),
                note=values.get("note"),
                username=self.user.username,
            )
        except (OrderError, StockError) as exc:
            self._show_banner(str(exc), "error", duration=8000)
            return

        self.order_list.set_items(order_manager.get_items(self.current_table))
        self._update_totals()
        self._refresh_print_buttons()
        self._refresh_edit_lock_state()

    def _on_discount(self):
        if not self.current_table:
            self._show_banner("اختر طاولة لتطبيق الخصم.", "warn")
            return
        dlg = DiscountDialog(self)
        if dlg.exec() == dlg.DialogCode.Accepted:
            try:
                order_manager.apply_discount(
                    self.current_table,
                    dlg.value,
                    dlg.discount_type,
                    reason=dlg.reason,
                    username=self.user.username,
                )
            except OrderError as exc:
                self._show_banner(str(exc), "error", duration=8000)
                return
            self._update_totals()
            self._refresh_print_buttons()

    def _on_pay(self, method):
        if not self.current_table:
            self._show_banner("اختر طاولة أولاً.", "warn")
            return

        if not printer.ensure_printer_ready():
            proceed = QMessageBox.question(
                self,
                "الطابعة غير متصلة",
                "يبدو أن الطابعة غير متاحة. هل تريد إتمام الإيصال بدون طباعة؟",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if proceed != QMessageBox.StandardButton.Yes:
                self._show_banner("قم بتوصيل الطابعة ثم أعد المحاولة.", "warn", duration=8000)
                return

        settled, receipt = order_manager.settle(
            self.current_table,
            "cash" if method == "نقدي" else "visa",
            cashier=self.user.username,
        )
        if settled and receipt:
            try:
                printer.print_cashier_receipt(
                    self.current_table,
                    receipt.get("items", []),
                    receipt.get("subtotal", 0),
                    receipt.get("discount", 0),
                    receipt.get("total", 0),
                    method,
                    self.user.username,
                    discount_label=texts.get(receipt.get("label_key")),
                )
            except Exception as exc:
                self._handle_printer_error(exc, context="إيصال الدفع")
                return
            self._cashier_printed_tables.discard(self.current_table)
            self.order_list.set_items([])
            self._update_totals(None)
            if self.current_table:
                self._update_table_ps_display(self.current_table)
                self._update_ps_buttons_state()
            self._refresh_print_buttons()
            self._show_banner("تم إغلاق الطلب وطباعة الإيصالات.", "success")

    # PS controls - RESTORED (only on order page)
    def _ps_start(self, mode):
        if not self.current_table:
            return
        order_manager.ps_start(self.current_table, mode, cashier=self.user.username)
        self._update_table_ps_display(self.current_table)
        self._update_ps_buttons_state()
        self._update_totals()
        self._refresh_print_buttons()

    def _ps_stop(self):
        if not self.current_table:
            return
        order_manager.ps_stop(self.current_table, cashier=self.user.username)
        self._update_table_ps_display(self.current_table)
        self._update_ps_buttons_state()
        self.order_list.set_items(order_manager.get_items(self.current_table))
        self._update_totals()
        self._refresh_print_buttons()

    def _update_ps_buttons_state(self):
        """Update PS buttons based on current table state"""
        if not self.current_table:
            self.btn_ps_p2.setEnabled(False)
            self.btn_ps_p4.setEnabled(False)
            self.btn_ps_stop.setEnabled(False)
            return

        try:
            sess = order_manager.load_ps_session_from_db(self.current_table)
            ps_active = sess is not None
        except Exception:
            ps_active = False

        self.btn_ps_p2.setEnabled(not ps_active)
        self.btn_ps_p4.setEnabled(not ps_active)
        self.btn_ps_stop.setEnabled(ps_active)

    # Bus handlers
    def _on_table_total_changed(self, table_code, _t):
        self.table_map.update_table(table_code, total_cents=_t)
        if self.current_table == table_code and self.pages.currentIndex() == PAGE_ORDER:
            self._update_totals(table_code)
            self._refresh_print_buttons()

    def _on_table_client_name_changed(self, table_code, name):
        self.table_map.set_client_name(table_code, name or "")
        if self.current_table and self.current_table == table_code:
            self._update_client_name_field()

    def _apply_window_title(self):
        client_name = settings_service.get_client_name()
        if getattr(self, "user", None):
            title = texts.get(
                "app.window_title",
                client_name=client_name,
                username=self.user.username,
                role=self.user.role,
            )
        else:
            title = texts.get("app.window_title_fallback", client_name=client_name)
        self.setWindowTitle(title)

    def _apply_order_header(self):
        base = texts.get("main.order.header")
        if self.current_table:
            client_name = order_manager.get_client_name(self.current_table)
            label = self.current_table
            if client_name:
                label = f"{self.current_table} — {client_name}"
            self.order_header.setText(f"{base} {label}".strip())
        else:
            self.order_header.setText(base)

    def _apply_texts(self, *_args):
        self._apply_window_title()
        self.act_back.setText(texts.get("main.toolbar.back"))
        self.act_switch.setText(texts.get("main.toolbar.switch"))
        self.act_manage.setText(texts.get("main.toolbar.manage_products"))
        self.act_users.setText(texts.get("main.toolbar.users"))
        self.act_reports.setText(texts.get("main.toolbar.reports"))
        self.act_tables.setText(texts.get("main.toolbar.tables"))
        self.act_purchases.setText(texts.get("main.toolbar.purchases"))
        self.act_inventory.setText(texts.get("main.toolbar.inventory"))
        self.act_settings.setText(texts.get("main.toolbar.settings"))
        self.act_reservations.setText(texts.get("main.toolbar.reservations"))
        self.act_style_guide.setText(texts.get("main.toolbar.style_guide", "دليل النمط"))
        self.banner_close.setText(texts.get("main.banner.close"))
        self.tables_title.setText(texts.get("main.tables.title"))
        self.btn_print_bar.setText(texts.get("main.order.print_bar"))
        self.btn_print_cashier.setText(texts.get("main.order.print_cashier"))
        self.btn_table_history.setText(texts.get("tables.history.button"))
        self.btn_table_history.setToolTip(texts.get("tables.history.button"))
        self.btn_clear_table.setText(texts.get("main.order.clear_table"))
        self.btn_clear_table.setToolTip(texts.get("main.order.clear_table_tooltip"))
        self.back_big.setText(texts.get("main.toolbar.back"))
        self._apply_order_header()
        self._apply_navigation_texts()
        self._update_breadcrumbs()

    def _on_table_state_changed(self, table_code, state):
        self.table_map.update_table(table_code, state=state)

    def _on_catalog_changed(self):
        self.cat_grid.set_categories(order_manager.categories)

    def _on_ps_state_changed(self, table_code: str, running: bool):
        """
        Called whenever backend emits ps_state_changed(table_code, running).
        Update the table tile so it can show a timer indicator.
        Also refresh order list if this is the current table.
        """
        try:
            sess = order_manager.load_ps_session_from_db(table_code) if running else None
        except Exception:
            sess = None
        self._update_table_ps_display(table_code, sess)

        # Refresh order list if this is the current table (to show PS billing items)
        if self.current_table == table_code:
            self.order_list.set_items(order_manager.get_items(self.current_table))
            self._update_totals()
            self._refresh_print_buttons()
            self._update_ps_buttons_state()

    def _on_table_selected(self, table_code: str):
        self.current_table = table_code
        sess = order_manager.load_ps_session_from_db(table_code)
        self._update_table_ps_display(table_code, sess)
        self.order_list.set_items(order_manager.get_items(table_code))
        self._update_totals(table_code)

    def _on_inventory_low(self, product, prev_stock, new_stock, min_stock):
        if new_stock is None:
            return
        prev_val = 0 if prev_stock is None else prev_stock
        min_val = 0 if min_stock is None else min_stock
        msg = f"تنبيه المخزون: {product} {prev_val:g} ➜ {new_stock:g} (حد أدنى {min_val:g})"
        self._status.showMessage(msg, 10000)
        if self.user.role == "admin" and new_stock <= 0:
            self._show_banner(msg, "warn", duration=10000)

    def _on_inventory_recovered(self, product, prev_stock, new_stock, min_stock):
        if new_stock is None:
            return
        prev_val = 0 if prev_stock is None else prev_stock
        min_val = 0 if min_stock is None else min_stock
        msg = f"تمت إعادة توافر {product}: {prev_val:g} ➜ {new_stock:g} (حد أدنى {min_val:g})"
        self._status.showMessage(msg, 7000)
        if self.user.role == "admin":
            self._show_banner(msg, "success", duration=6000)

    def _on_reservations_changed(self, *_payload):
        self._refresh_reservation_overlays()

    def _refresh_reservation_overlays(self):
        try:
            mapping = reservations_service.get_active_reservations_map()
        except Exception:
            mapping = {}
        self.table_map.set_reservations(mapping)

    def _refresh_branding(self):
        self.setStyleSheet(build_main_window_stylesheet())
        pix = get_logo_pixmap(64)
        if pix:
            scaled = pix.scaledToHeight(56, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(scaled)
            self.logo_label.setText("")
        else:
            self.logo_label.clear()
            self.logo_label.setText("Beirut POS")
        icon = get_logo_icon(64)
        if icon:
            self.setWindowIcon(icon)
        if self.banner.isVisible():
            self.banner.style().unpolish(self.banner)
            self.banner.style().polish(self.banner)

    def _on_branding_changed(self, payload):
        self._refresh_branding()
        self._show_banner("تم تحديث الهوية البصرية للتطبيق.", "success", duration=6000)

    def _on_settings_saved(self, _payload=None):
        self._status.showMessage("تم حفظ الإعدادات بنجاح.", 6000)
        self._show_banner("تم حفظ الإعدادات وتحديث التطبيق فوراً.", "success", duration=6000)

    def _on_tables_changed(self, codes):
        if not isinstance(codes, (list, tuple)):
            return
        cleaned = [str(code).strip().upper() for code in codes if str(code).strip()]
        if not cleaned:
            cleaned = order_manager.get_table_codes()
        self.table_codes = cleaned
        self.table_map.set_table_codes(cleaned)
        self.table_map.set_client_names(order_manager.list_client_names())
        self._refresh_reservation_overlays()
        if self.current_table and self.current_table not in cleaned:
            self._show_banner("تمت إزالة الطاولة الحالية من القائمة. تم الرجوع إلى شاشة الطاولات.", "warn",
                              duration=8000)
            self._go_back()
        else:
            self._update_client_name_field()

    def _hide_banner(self):
        self.banner_timer.stop()
        self.banner.setVisible(False)

    def _show_banner(self, text: str, kind: str = "info", duration: int | None = None):
        self.banner.setProperty("kind", kind)
        self.banner_label.setText(text)
        self.banner.setVisible(True)
        self.banner_timer.stop()

        target_duration = duration if duration is not None else self._banner_durations.get(kind, 6000)
        if target_duration and target_duration > 0:
            self.banner_timer.start(target_duration)

        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)

    def _handle_printer_error(self, exc: Exception, *, context: str) -> None:
        detail = str(exc).strip()
        msg = (
            f"تعذر طباعة {context}. إذا كنت لا تحتاج للطباعة الآن فيمكنك تجاهل هذا الخطأ "
            "من نافذة الطابعة أو تعطيل الطابعة مؤقتًا من الإعدادات."
        )
        if detail:
            msg += f"\nالتفاصيل: {detail}"
        self._show_banner(msg, "error", duration=12000)

    def _update_session_timer(self):
        elapsed = datetime.utcnow() - self._session_started
        seconds = int(elapsed.total_seconds())
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        self._session_label.setText(f"⏱ {hours:02d}:{minutes:02d}:{secs:02d}")

    def _show_hotkeys_help(self):
        help_text = (
            "F2 طباعة البار · F3 طباعة الكاشير · Ctrl+D خصم · Ctrl+L تبديل المستخدم · "
            "Ctrl+Shift+R التقارير · Ctrl+Shift+S الإعدادات · Ctrl+Shift+T إدارة الطاولات"
        )
        self._show_banner(help_text, "info", duration=10000)

    def closeEvent(self, event):
        try:
            self._show_shift_summary()
        except Exception:
            pass
        if self._session_timer.isActive():
            self._session_timer.stop()
        if self._ps_snapshot_timer.isActive():
            self._ps_snapshot_timer.stop()
        try:
            staff_service.end_session(self._active_session_id)
        except Exception:
            pass
        super().closeEvent(event)

    def _on_ps_snapshot(self):
        try:
            order_manager.snapshot_ps_sessions()
        except Exception:
            pass

    def _collect_unprinted_items(self, table_code):
        out = []
        for it in order_manager.get_items(table_code):
            printed = float(getattr(it, "printed_qty", 0.0) or 0.0)
            remaining = float(it.qty) - printed
            if remaining > 1e-6:
                out.append(type(it)(
                    product=it.product,
                    unit_price_cents=it.unit_price_cents,
                    qty=remaining,
                    note=it.note
                ))
        return out

    def _update_table_ps_display(self, table_code: str, sess=None):
        """
        Update table tile PS display - only show timer, no controls
        """
        try:
            if sess is None:
                try:
                    sess = order_manager.load_ps_session_from_db(table_code)
                except Exception:
                    sess = None

            if not sess:
                # clear PS timer on tile
                try:
                    self.table_map.update_table(table_code, ps_active=False)
                except Exception:
                    try:
                        self.table_map.update_table(table_code)
                    except Exception:
                        pass
                return

            # Calculate elapsed seconds for the timer display
            from datetime import timezone
            now = datetime.now(timezone.utc)
            started_at = sess.started_at

            # Handle both string and datetime objects
            if isinstance(started_at, str):
                try:
                    started_at = datetime.fromisoformat(started_at)
                except Exception:
                    started_at = now

            # Ensure timezone awareness
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)

            # Calculate total elapsed seconds
            elapsed_seconds = int(sess.total_seconds or 0) + int((now - started_at).total_seconds())

            # Update tile with active PS session and elapsed time
            try:
                self.table_map.update_table(table_code, ps_active=True, ps_elapsed_seconds=elapsed_seconds)
            except Exception as e:
                print(f"Error updating table {table_code} PS display: {e}")
                pass

        except Exception as e:
            print(f"Error in _update_table_ps_display for {table_code}: {e}")
            pass
