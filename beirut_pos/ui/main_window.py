# beirut_pos/ui/main_window.py
from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QLabel,
    QToolBar,
    QMessageBox,
    QStackedWidget,
    QHBoxLayout,
    QPushButton,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QShortcut, QKeySequence
from .components.table_map import TableMap
from .components.category_grid import CategoryGrid
from .components.order_list import OrderList
from .components.payment_panel import PaymentPanel
from .components.ps_controls import PSControls
from ..services.orders import order_manager, StockError
from ..services.printer import printer
from ..core.bus import bus
from .login_dialog import LoginDialog
from .admin_products_dialog import AdminProductsDialog
from .discount_dialog import DiscountDialog
from .admin_users_dialog import AdminUsersDialog
from .admin_reports_dialog import AdminReportsDialog

# NEW: settings & daily Z-report dialogs
from .settings_dialog import SettingsDialog
from .zreport_dialog import ZReportDialog
from .coffee_customizer import CoffeeCustomizerDialog
from .common.branding import get_logo_pixmap, get_logo_icon
from .common.barista_tips import random_tip

PAGE_TABLES=0; PAGE_ORDER=1

class MainWindow(QMainWindow):
    def __init__(self, current_user):
        super().__init__()
        self.user=current_user
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1440,900)
        self.setWindowTitle(f"Beirut POS — {self.user.username} ({self.user.role})")  # cashier name on top
        icon = get_logo_icon(64)
        if icon:
            self.setWindowIcon(icon)
        self._status = self.statusBar()
        self._status.setSizeGripEnabled(False)
        self._status.showMessage(random_tip(), 12000)

        bar=QToolBar("Main"); self.addToolBar(bar)
        self.logo_label = QLabel()
        self.logo_label.setObjectName("appLogo")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bar.addWidget(self.logo_label)
        bar.addSeparator()
        self.act_back=QAction("رجوع", self); self.act_back.triggered.connect(self._go_back); self.act_back.setVisible(False); bar.addAction(self.act_back)
        act_switch=QAction("تبديل المستخدم", self); act_switch.triggered.connect(self._switch_user); bar.addAction(act_switch)
        self.act_manage=QAction("إدارة الأصناف (مدير)", self); self.act_manage.triggered.connect(self._open_manage_products)
        self.act_users=QAction("إدارة المستخدمين", self); self.act_users.triggered.connect(self._open_users)
        self.act_reports=QAction("التقارير", self); self.act_reports.triggered.connect(self._open_reports)

        # NEW: Settings & Daily Z-Report (admin only)
        self.act_settings=QAction("الإعدادات", self); self.act_settings.triggered.connect(self._open_settings)
        self.act_zreport=QAction("تقرير يومي (Z)", self); self.act_zreport.triggered.connect(self._open_zreport)

        for a in (self.act_manage,self.act_users,self.act_reports,self.act_settings,self.act_zreport):
            a.setVisible(self.user.role=="admin"); bar.addAction(a)

        # Hotkeys
        QShortcut(QKeySequence("Esc"), self, activated=self._go_back)
        QShortcut(QKeySequence("F2"), self, activated=self._print_bar)
        QShortcut(QKeySequence("F3"), self, activated=self._print_cashier)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self._on_discount)
        QShortcut(QKeySequence("Del"), self, activated=self._remove_selected_or_last)

        self.pages=QStackedWidget()

        container = QWidget()
        container.setObjectName("MainContainer")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(32, 28, 32, 28)
        container_layout.setSpacing(18)

        self.banner = QFrame()
        self.banner.setObjectName("ToastBanner")
        banner_layout = QHBoxLayout(self.banner)
        banner_layout.setContentsMargins(18, 12, 12, 12)
        banner_layout.setSpacing(12)
        self.banner_label = QLabel()
        self.banner_label.setWordWrap(True)
        self.banner_close = QPushButton("✕")
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
        tables_page=QWidget(); tables_page.setObjectName("TablesPage"); tv=QVBoxLayout(tables_page)
        title=QLabel("الطاولات — اختر طاولة"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); tv.addWidget(title)
        self.table_codes=[f"T{i:02d}" for i in range(1,31)]
        self.table_map=TableMap(self.table_codes, self._on_table_select)
        tv.addWidget(self.table_map,1)

        # Order page
        order_page=QWidget(); order_page.setObjectName("OrderPage"); ov=QVBoxLayout(order_page)
        head_row=QHBoxLayout()
        self.order_header=QLabel("طلب:")
        self.order_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head_row.addWidget(self.order_header,1)

        # Two print buttons (Bar & Cashier)
        self.btn_print_bar = QPushButton("🧾 طباعة البار")
        self.btn_print_bar.setToolTip("طباعة تذكرة البار للطلبات الجاهزة في المشروبات")
        self.btn_print_bar.clicked.connect(self._print_bar)
        head_row.addWidget(self.btn_print_bar, 0)

        self.btn_print_cashier = QPushButton("🧾 طباعة الكاشير")
        self.btn_print_cashier.setToolTip("طباعة إيصال الكاشير للعميل بدون تحصيل")
        self.btn_print_cashier.clicked.connect(self._print_cashier)
        head_row.addWidget(self.btn_print_cashier, 0)

        self.back_big=QPushButton("⬅ رجوع"); self.back_big.clicked.connect(self._go_back); head_row.addWidget(self.back_big,0)
        ov.addLayout(head_row,0)

        row=QHBoxLayout()
        self.cat_grid=CategoryGrid(order_manager.categories, self._on_pick); row.addWidget(self.cat_grid,3)
        self.ps_controls=PSControls(on_start_p2=lambda: self._ps_start("P2"),
                                    on_start_p4=lambda: self._ps_start("P4"),
                                    on_switch_p2=lambda: self._ps_switch("P2"),
                                    on_switch_p4=lambda: self._ps_switch("P4"),
                                    on_stop=self._ps_stop)
        row.addWidget(self.ps_controls,1); ov.addLayout(row,3)
        self.order_list=OrderList(self._on_remove); ov.addWidget(self.order_list,2)
        self.payment=PaymentPanel(self._on_pay, self._on_discount); ov.addWidget(self.payment,0)

        self.pages.addWidget(tables_page); self.pages.addWidget(order_page); self.pages.setCurrentIndex(PAGE_TABLES)

        # Bus listeners
        bus.subscribe("table_total_changed", self._on_table_total_changed)
        bus.subscribe("table_state_changed", self._on_table_state_changed)
        bus.subscribe("catalog_changed", self._on_catalog_changed)
        bus.subscribe("ps_state_changed", self._on_ps_state_changed)   # NEW
        bus.subscribe("inventory_low", self._on_inventory_low)
        bus.subscribe("inventory_recovered", self._on_inventory_recovered)
        bus.subscribe("branding_changed", self._on_branding_changed)

        self.current_table=None
        self._coffee_categories = {"Coffee Corner", "Hot Drinks", "Fresh Drinks"}

        # Initial state for print buttons
        self._refresh_print_buttons()
        self._refresh_branding()

    # ---------------- helpers: printing ----------------
    def _refresh_print_buttons(self):
        has_items = bool(self.current_table and order_manager.get_items(self.current_table))
        self.btn_print_bar.setEnabled(has_items)
        self.btn_print_cashier.setEnabled(has_items)

    def _print_bar(self):
        if not self.current_table:
            self._show_banner("اختر طاولة أولاً قبل الطباعة.", "warn")
            return
        items = order_manager.get_items(self.current_table)
        if not items:
            self._show_banner("لا توجد عناصر في الطلب الحالي.", "warn")
            return
        printer.print_bar_ticket(self.current_table, items)
        self._show_banner("تم إرسال تذكرة البار للطابعة.", "success")

    def _print_cashier(self):
        if not self.current_table:
            self._show_banner("اختر طاولة أولاً قبل الطباعة.", "warn")
            return
        items = order_manager.get_items(self.current_table)
        if not items:
            self._show_banner("لا توجد عناصر في الطلب الحالي.", "warn")
            return
        sub, disc, tot = order_manager.get_totals(self.current_table)
        # طباعة إيصال يدوي بدون تحصيل/إقفال
        printer.print_cashier_receipt(self.current_table, items, sub, disc, tot, method="manual", cashier=self.user.username)
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
        self.pages.setCurrentIndex(PAGE_TABLES); self.act_back.setVisible(False)
        self.table_map.clear_selection(); self.current_table=None; self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
        self.order_header.setText("طلب:")
        self._refresh_print_buttons()
        self._status.showMessage(random_tip(), 10000)

    def _switch_user(self):
        dlg=LoginDialog()
        if dlg.exec()==dlg.DialogCode.Accepted:
            self.user=dlg.get_user()
            self.setWindowTitle(f"Beirut POS — {self.user.username} ({self.user.role})")
            for a in (self.act_manage,self.act_users,self.act_reports,self.act_settings,self.act_zreport):
                a.setVisible(self.user.role=="admin")

    def _open_manage_products(self):
        if self.user.role!="admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        cats=[c for c,_ in order_manager.categories]
        AdminProductsDialog(cats,
            on_add_category=lambda name: order_manager.catalog.add_category(name),
            on_add_product=lambda cat,name,price: order_manager.catalog.add_product(cat,name,price,username=self.user.username),
            current_admin=self.user.username).exec()

    def _open_users(self):
        if self.user.role!="admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        from .admin_users_dialog import AdminUsersDialog
        AdminUsersDialog(self.user.username).exec()

    def _open_reports(self):
        if self.user.role!="admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        from .admin_reports_dialog import AdminReportsDialog
        AdminReportsDialog().exec()

    # NEW: dialogs
    def _open_settings(self):
        if self.user.role!="admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        SettingsDialog(self).exec()

    def _open_zreport(self):
        if self.user.role!="admin":
            self._show_banner("هذه العملية للمدير فقط.", "warn")
            return
        ZReportDialog(self).exec()

    # POS flow
    def _on_table_select(self, code):
        self.current_table=code; self.act_back.setVisible(True)
        self.order_header.setText(f"طلب: {code}")
        self.order_list.set_items(order_manager.get_items(code))
        sub,disc,tot=order_manager.get_totals(code); self.payment.set_totals(sub,disc,tot)
        self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
        self.pages.setCurrentIndex(PAGE_ORDER)
        self._refresh_print_buttons()
        self._status.showMessage(random_tip(), 9000)

    def _on_pick(self, label, price_cents):
        if not self.current_table: return
        prod = order_manager.catalog.get_product(label)
        final_label = label
        final_price = price_cents
        note = ""
        if prod and prod.get("category") in self._coffee_categories:
            dlg = CoffeeCustomizerDialog(label, price_cents, self)
            if dlg.exec() != dlg.DialogCode.Accepted:
                return
            selection = dlg.get_result()
            if not selection:
                return
            final_label = selection.label
            final_price = price_cents + selection.price_delta
            note = selection.note
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
        self.order_list.set_items(order_manager.get_items(self.current_table))
        sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)
        self._refresh_print_buttons()

    def _on_remove(self, index):
        if not self.current_table: return
        order_manager.remove_item(self.current_table, index, username=self.user.username)
        self.order_list.set_items(order_manager.get_items(self.current_table))
        sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)
        self._refresh_print_buttons()

    def _on_discount(self):
        if not self.current_table:
            self._show_banner("اختر طاولة لتطبيق الخصم.", "warn")
            return
        dlg=DiscountDialog()
        if dlg.exec()==dlg.DialogCode.Accepted:
            order_manager.apply_discount(self.current_table, dlg.amount)
            sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)
            self._refresh_print_buttons()

    def _on_pay(self, method):
        if not self.current_table:
            self._show_banner("اختر طاولة أولاً.", "warn")
            return
        # print bar ticket (items for bar) BEFORE settle
        items = order_manager.get_items(self.current_table)
        printer.print_bar_ticket(self.current_table, items)
        # settle (persists) & print cashier receipt AFTER totals are final
        if order_manager.settle(self.current_table, "cash" if method=="نقدي" else "visa", cashier=self.user.username):
            # recompute totals after settle if you want; here we print a final receipt with zeroed UI
            printer.print_cashier_receipt(self.current_table, items, 0, 0, 0, method, self.user.username)
            self.order_list.set_items([]); self.payment.set_totals(0,0,0)
            self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
            self._refresh_print_buttons()
            self._show_banner("تم إغلاق الطلب وطباعة الإيصالات.", "success")

    # PS controls
    def _ps_start(self, mode):
        if not self.current_table: return
        order_manager.ps_start(self.current_table, mode); self.ps_controls.show_running("P2" if mode=="P2" else "P4")

    def _ps_switch(self, mode):
        if not self.current_table: return
        order_manager.ps_switch(self.current_table, mode); self.ps_controls.show_running(mode)
        sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)
        self._refresh_print_buttons()

    def _ps_stop(self):
        if not self.current_table: return
        order_manager.ps_stop(self.current_table); self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
        self.order_list.set_items(order_manager.get_items(self.current_table))
        sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)
        self._refresh_print_buttons()

    # Bus handlers
    def _on_table_total_changed(self, table_code, _t):
        self.table_map.update_table(table_code, total_cents=_t)
        if self.current_table==table_code and self.pages.currentIndex()==PAGE_ORDER:
            sub,disc,tot=order_manager.get_totals(table_code); self.payment.set_totals(sub,disc,tot)
            self._refresh_print_buttons()

    def _on_table_state_changed(self, table_code, state): self.table_map.update_table(table_code, state=state)
    def _on_catalog_changed(self): self.cat_grid.set_categories(order_manager.categories)
    def _on_ps_state_changed(self, table_code, active): self.table_map.update_table(table_code, ps_active=active)
    def _on_inventory_low(self, product, prev_stock, new_stock, min_stock):
        if new_stock is None:
            return
        prev_val = 0 if prev_stock is None else prev_stock
        min_val = 0 if min_stock is None else min_stock
        msg = f"تنبيه المخزون: {product} {prev_val:g} ➜ {new_stock:g} (حد أدنى {min_val:g})"
        self._status.showMessage(msg, 10000)
        if self.user.role == "admin" and new_stock <= 0:
            QMessageBox.warning(self, "المخزون", msg)

    def _on_inventory_recovered(self, product, prev_stock, new_stock, min_stock):
        if new_stock is None:
            return
        prev_val = 0 if prev_stock is None else prev_stock
        min_val = 0 if min_stock is None else min_stock
        msg = f"تمت إعادة توافر {product}: {prev_val:g} ➜ {new_stock:g} (حد أدنى {min_val:g})"
        self._status.showMessage(msg, 7000)

    def _refresh_branding(self):
        pix = get_logo_pixmap(32)
        if pix:
            self.logo_label.setPixmap(pix)
            self.logo_label.setText("")
        else:
            self.logo_label.clear()
            self.logo_label.setText("Beirut POS")
        icon = get_logo_icon(64)
        if icon:
            self.setWindowIcon(icon)

    def _on_branding_changed(self, _logo_path):
        self._refresh_branding()
