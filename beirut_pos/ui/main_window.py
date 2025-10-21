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
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QShortcut, QKeySequence
from .components.table_map import TableMap
from .components.category_grid import CategoryGrid
from .components.order_list import OrderList
from .components.payment_panel import PaymentPanel
from .components.ps_controls import PSControls
from ..services.orders import order_manager, StockError, OrderError
from ..services.printer import printer
from ..services import reservations as reservations_service
from ..services.texts import texts
from ..services import settings as settings_service
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

PAGE_TABLES = 0
PAGE_ORDER = 1


class MainWindow(QMainWindow):
    def __init__(self, current_user):
        super().__init__()
        self.user = current_user
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1440, 900)
        self.setWindowState(self.windowState() | Qt.WindowState.WindowMaximized)
        self._apply_window_title()
        self.setStyleSheet(build_main_window_stylesheet())
        icon = get_logo_icon(64)
        if icon:
            self.setWindowIcon(icon)
        self._status = self.statusBar()
        self._status.setSizeGripEnabled(False)
        self._status.showMessage(random_tip(), 12000)
        self._session_started = datetime.now()
        self._session_label = QLabel()
        self._session_label.setObjectName("sessionTimer")
        self._status.addPermanentWidget(self._session_label)
        self._session_timer = QTimer(self)
        self._session_timer.timeout.connect(self._update_session_timer)
        self._session_timer.start(1000)
        self._update_session_timer()
        self._ps_snapshot_timer = QTimer(self)
        self._ps_snapshot_timer.setInterval(5000)
        self._ps_snapshot_timer.timeout.connect(self._on_ps_snapshot)  # wrap to avoid weakref to OrderManager
        self._ps_snapshot_timer.start()

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
        self.act_reservations = QAction(self)
        self.act_reservations.triggered.connect(self._open_reservations)

        # NEW: Settings & Daily Z-Report (admin only)
        self.act_settings = QAction(self)
        self.act_settings.triggered.connect(self._open_settings)
        # self.act_zreport=QAction("تقرير يومي (Z)", self); self.act_zreport.triggered.connect(self._open_zreport)

        self._admin_actions = [
            self.act_manage,
            self.act_users,
            self.act_reports,
            self.act_tables,
            self.act_purchases,
            self.act_settings,
            # self.act_zreport,
        ]
        for action in self._admin_actions:
            action.setVisible(self.user.role == "admin")
            bar.addAction(action)
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
        QShortcut(QKeySequence("Ctrl+/"), self, activated=self._show_hotkeys_help)

        self.pages = QStackedWidget()

        container = QWidget()
        container.setObjectName("MainContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 12, 12, 12)
        container_layout.setSpacing(8)

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

        container_layout.addWidget(self.banner, 0)
        container_layout.addWidget(self.pages, 1)

        self.banner_timer = QTimer(self)
        self.banner_timer.setSingleShot(True)
        self.banner_timer.timeout.connect(self._hide_banner)

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
        tv.addWidget(self.table_map, 1)
        self._refresh_reservation_overlays()

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

        # All action buttons together
        self.btn_print_bar = QPushButton()
        self.btn_print_bar.setToolTip("طباعة تذكرة البار")
        self.btn_print_bar.clicked.connect(self._print_bar)
        head_row.addWidget(self.btn_print_bar, 0)

        self.btn_print_cashier = QPushButton()
        self.btn_print_cashier.setToolTip("طباعة إيصال الكاشير")
        self.btn_print_cashier.clicked.connect(self._print_cashier)
        head_row.addWidget(self.btn_print_cashier, 0)

        self.btn_merge = QPushButton("🔀 دمج")
        self.btn_merge.setToolTip("دمج مع طاولة أخرى")
        self.btn_merge.clicked.connect(self._on_merge_tables)
        self.btn_merge.setEnabled(False)
        head_row.addWidget(self.btn_merge, 0)

        self.back_big = QPushButton()
        self.back_big.clicked.connect(self._go_back)
        head_row.addWidget(self.back_big, 0)

        head_row.addStretch(1)
        ov.addLayout(head_row, 0)

        # Main content: 3 columns (products + PS controls + order details)
        main_row = QHBoxLayout()
        main_row.setSpacing(8)

        # LEFT: Products grid - MAXIMUM space (65% width)
        self.cat_grid = CategoryGrid(order_manager.categories, self._on_pick)
        main_row.addWidget(self.cat_grid, 13)

        # MIDDLE: PS Controls (10% width)
        self.ps_controls = PSControls(
            on_start_p2=lambda: self._ps_start("P2"),
            on_start_p4=lambda: self._ps_start("P4"),
            on_switch_p2=lambda: self._ps_switch("P2"),
            on_switch_p4=lambda: self._ps_switch("P4"),
            on_stop=self._ps_stop
        )
        main_row.addWidget(self.ps_controls, 2)

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
        bus.subscribe("ps_state_changed", self._on_ps_state_changed)  # NEW
        bus.subscribe("inventory_low", self._on_inventory_low)
        bus.subscribe("inventory_recovered", self._on_inventory_recovered)
        bus.subscribe("branding_changed", self._on_branding_changed)
        bus.subscribe("settings_saved", self._on_settings_saved)
        bus.subscribe("tables_changed", self._on_tables_changed)
        bus.subscribe("reservations_changed", self._on_reservations_changed)
        bus.subscribe("ui_texts_changed", self._apply_texts)
        bus.subscribe("client_branding_changed", self._apply_texts)

        self.current_table = None
        self._edit_locked = False
        self._coffee_categories = {"Coffee Corner", "Hot Drinks", "Fresh Drinks"}

        # Initial state for print buttons
        self._refresh_print_buttons()
        self._refresh_branding()
        self._apply_texts()

    # ---------------- helpers: printing ----------------
    def _refresh_print_buttons(self):
        has_items = bool(self.current_table and order_manager.get_items(self.current_table))
        self.btn_print_bar.setEnabled(has_items)
        self.btn_print_cashier.setEnabled(has_items)

    def _refresh_edit_lock_state(self):
        message = texts.get("orders.edit_locked")
        editable = bool(self.current_table) and order_manager.can_edit(self.current_table)
        locked = bool(self.current_table) and not editable
        targets = [self.order_list.edit_btn, self.order_list.remove_btn, self.payment.discount_btn]
        for btn in targets:
            btn.setEnabled(editable)
            btn.setToolTip(message if locked else "")
        if locked and not self._edit_locked:
            self._show_banner(message, "warn", duration=6000)
        if not locked and self._edit_locked:
            for btn in targets:
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

        printer.print_bar_ticket(self.current_table, to_print)
        try:
            # Pass the exact items we printed so printed_qty advances correctly
            order_manager.mark_bar_items_as_printed(self.current_table, to_print)
        except Exception:
            # Older deployments without the method will just skip marking
            pass

        # refresh UI
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
        # طباعة إيصال يدوي بدون تحصيل/إقفال
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
        self._show_banner("تم إرسال إيصال الكاشير للطابعة.", "success")

    # Quick helper for Del key
    def _remove_selected_or_last(self):
        if not self.current_table:
            return
        # Try to use selected index if OrderList exposes it; otherwise remove last
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
        self._refresh_edit_lock_state()
        self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
        self._apply_order_header()
        self._refresh_print_buttons()
        self._status.showMessage(random_tip(), 10000)
        self.btn_merge.setEnabled(False)

    def _switch_user(self):
        dlg = LoginDialog()
        if dlg.exec() == dlg.DialogCode.Accepted:
            self.user = dlg.get_user()
            self._apply_window_title()
            for action in self._admin_actions:
                action.setVisible(self.user.role == "admin")
            self._session_started = datetime.now()
            self._update_session_timer()

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
        AdminReportsDialog().exec()

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

    def _open_reservations(self):
        ReservationsDialog(parent=self).exec()

    # NEW: dialogs
    def _open_settings(self):
        if self.user.role != "admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        SettingsDialog(self).exec()

    # def _open_zreport(self):
    #     if self.user.role!="admin":
    #         self._show_banner("هذه العملية للمدير فقط.", "warn")
    #         return
    #     ZReportDialog(self).exec()

    # POS flow
    def _on_table_select(self, code):
        self.current_table = code
        self.act_back.setVisible(True)
        self._apply_order_header()
        self.order_list.set_items(order_manager.get_items(code))
        self._update_totals(code)
        self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
        self.pages.setCurrentIndex(PAGE_ORDER)
        self._refresh_print_buttons()
        self._status.showMessage(random_tip(), 9000)
        self.btn_merge.setEnabled(True)

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

    def _on_edit_item(self, index: int) -> None:
        if not self.current_table:
            self._show_banner("اختر طاولة لتعديل العناصر.", "warn")
            return
        items = order_manager.get_items(self.current_table)
        if not (0 <= index < len(items)):
            return
        item = items[index]
        editor = OrderItemEditor(item.product, item.qty, item.note, self)
        if editor.exec() != editor.DialogCode.Accepted:
            return
        values = editor.get_values()
        if not values:
            return
        try:
            order_manager.update_item(
                self.current_table,
                index,
                qty=values["qty"],
                note=values["note"],
                username=self.user.username,
            )
        except StockError as exc:
            self._show_banner(str(exc), "error", duration=8000)
            return
        except OrderError as exc:
            self._show_banner(str(exc), "error", duration=8000)
            return
        self.order_list.set_items(order_manager.get_items(self.current_table))
        self._update_totals()
        self._refresh_print_buttons()

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

        # Get the actual totals BEFORE settling
        subtotal, discount, total, label_key = order_manager.get_totals(self.current_table)
        items = order_manager.get_items(self.current_table)

        if order_manager.settle(self.current_table, "cash" if method == "نقدي" else "visa", cashier=self.user.username):
            # Pass the REAL totals, not zeros!
            printer.print_cashier_receipt(
                self.current_table,
                items,
                subtotal,
                discount,
                total,
                method,
                self.user.username,
                discount_label=texts.get(label_key),
            )
            self.order_list.set_items([])
            self._update_totals(None)
            self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
            self._refresh_print_buttons()
            self._show_banner("تم إغلاق الطلب وطباعة الإيصالات.", "success")
    # PS controls
    def _ps_start(self, mode):
        if not self.current_table:
            return
        order_manager.ps_start(self.current_table, mode)
        self.ps_controls.show_running("P2" if mode == "P2" else "P4")

    def _ps_switch(self, mode):
        if not self.current_table:
            return
        order_manager.ps_switch(self.current_table, mode)
        self.ps_controls.show_running(mode)
        self._update_totals()
        self._refresh_print_buttons()

    def _ps_stop(self):
        if not self.current_table:
            return
        order_manager.ps_stop(self.current_table)
        self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
        self.order_list.set_items(order_manager.get_items(self.current_table))
        self._update_totals()
        self._refresh_print_buttons()

    # Bus handlers
    def _on_table_total_changed(self, table_code, _t):
        self.table_map.update_table(table_code, total_cents=_t)
        if self.current_table == table_code and self.pages.currentIndex() == PAGE_ORDER:
            self._update_totals(table_code)
            self._refresh_print_buttons()

    def _apply_window_title(self):
        client_name = settings_service.get_client_name()

        # DIAGNOSTIC - Add these lines
        print(f"texts object: {texts}")
        print(f"texts.get method: {texts.get}")
        import inspect
        print(f"get() signature: {inspect.signature(texts.get)}")
        # END DIAGNOSTIC

        if getattr(self, "user", None):
            title = texts.get(
                "app.window_title",
                client_name=client_name,
                username=self.user.username,
                role=self.user.role,
            )
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
            self.order_header.setText(f"{base} {self.current_table}".strip())
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
        self.act_settings.setText(texts.get("main.toolbar.settings"))
        self.act_reservations.setText(texts.get("main.toolbar.reservations"))
        self.banner_close.setText(texts.get("main.banner.close"))
        self.tables_title.setText(texts.get("main.tables.title"))
        self.btn_print_bar.setText(texts.get("main.order.print_bar"))
        self.btn_print_cashier.setText(texts.get("main.order.print_cashier"))
        self.back_big.setText(texts.get("main.toolbar.back"))
        self._apply_order_header()

    def _on_table_state_changed(self, table_code, state):
        self.table_map.update_table(table_code, state=state)

    def _on_catalog_changed(self):
        self.cat_grid.set_categories(order_manager.categories)

    def _on_ps_state_changed(self, table_code, active):
        self.table_map.update_table(table_code, ps_active=active)

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
        # re-polish banner styling with new palette
        if self.banner.isVisible():
            self.banner.style().unpolish(self.banner)
            self.banner.style().polish(self.banner)

    def _on_branding_changed(self, payload):
        # payload may be dict or legacy path string
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
        self._refresh_reservation_overlays()
        if self.current_table and self.current_table not in cleaned:
            self._show_banner("تمت إزالة الطاولة الحالية من القائمة. تم الرجوع إلى شاشة الطاولات.", "warn",
                              duration=8000)
            self._go_back()

    def _hide_banner(self):
        self.banner_timer.stop()
        self.banner.setVisible(False)

    def _show_banner(self, text: str, kind: str = "info", duration: int | None = 6000):
        self.banner.setProperty("kind", kind)
        self.banner_label.setText(text)
        self.banner.setVisible(True)
        self.banner_timer.stop()
        if duration and duration > 0:
            self.banner_timer.start(duration)
        self.banner.style().unpolish(self.banner)
        self.banner.style().polish(self.banner)

    def _update_session_timer(self):
        elapsed = datetime.now() - self._session_started
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
        if self._session_timer.isActive():
            self._session_timer.stop()
        super().closeEvent(event)

    def _on_ps_snapshot(self):
        # keep this tiny and exception-safe
        try:
            order_manager.snapshot_ps_sessions()
        except Exception:
            pass  # or log to status bar if you prefer

    def _collect_unprinted_items(self, table_code):
        """Return lightweight copies with qty = (qty - printed_qty) for printing."""
        out = []
        for it in order_manager.get_items(table_code):
            printed = float(getattr(it, "printed_qty", 0.0) or 0.0)
            remaining = float(it.qty) - printed
            if remaining > 1e-6:
                # Create a light copy for printing with the remaining qty only
                out.append(type(it)(
                    product=it.product,
                    unit_price_cents=it.unit_price_cents,
                    qty=remaining,
                    note=it.note
                ))
        return out
