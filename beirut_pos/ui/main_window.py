from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QLabel, QToolBar, QMessageBox,
    QStackedWidget, QHBoxLayout, QPushButton)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QShortcut, QKeySequence
from .components.table_map import TableMap
from .components.category_grid import CategoryGrid
from .components.order_list import OrderList
from .components.payment_panel import PaymentPanel
from .components.ps_controls import PSControls
from ..services.orders import order_manager
from ..services.printer import printer
from ..core.bus import bus
from .login_dialog import LoginDialog
from .admin_products_dialog import AdminProductsDialog
from .discount_dialog import DiscountDialog
from .admin_users_dialog import AdminUsersDialog
from .admin_reports_dialog import AdminReportsDialog

PAGE_TABLES=0; PAGE_ORDER=1

class MainWindow(QMainWindow):
    def __init__(self, current_user):
        super().__init__()
        self.user=current_user
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.resize(1366,768)
        self.setWindowTitle(f"Beirut POS — {self.user.username} ({self.user.role})")  # cashier name on top

        bar=QToolBar("Main"); self.addToolBar(bar)
        self.act_back=QAction("رجوع", self); self.act_back.triggered.connect(self._go_back); self.act_back.setVisible(False); bar.addAction(self.act_back)
        act_switch=QAction("تبديل المستخدم", self); act_switch.triggered.connect(self._switch_user); bar.addAction(act_switch)
        self.act_manage=QAction("إدارة الأصناف (مدير)", self); self.act_manage.triggered.connect(self._open_manage_products)
        self.act_users=QAction("إدارة المستخدمين", self); self.act_users.triggered.connect(self._open_users)
        self.act_reports=QAction("التقارير", self); self.act_reports.triggered.connect(self._open_reports)
        for a in (self.act_manage,self.act_users,self.act_reports):
            a.setVisible(self.user.role=="admin"); bar.addAction(a)

        # ESC to go back
        esc = QShortcut(QKeySequence("Esc"), self)
        esc.activated.connect(self._go_back)

        self.pages=QStackedWidget(); self.setCentralWidget(self.pages)

        # Tables page
        tables_page=QWidget(); tv=QVBoxLayout(tables_page)
        title=QLabel("الطاولات — اختر طاولة"); title.setAlignment(Qt.AlignmentFlag.AlignCenter); tv.addWidget(title)
        self.table_codes=[f"T{i:02d}" for i in range(1,31)]
        self.table_map=TableMap(self.table_codes, self._on_table_select)
        tv.addWidget(self.table_map,1)

        # Order page
        order_page=QWidget(); ov=QVBoxLayout(order_page)
        head_row=QHBoxLayout()
        self.order_header=QLabel("طلب: —"); self.order_header.setAlignment(Qt.AlignmentFlag.AlignCenter); head_row.addWidget(self.order_header,1)
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

        self.current_table=None

    # Navigation/Admin
    def _go_back(self):
        self.pages.setCurrentIndex(PAGE_TABLES); self.act_back.setVisible(False)
        self.table_map.clear_selection(); self.current_table=None; self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")

    def _switch_user(self):
        dlg=LoginDialog()
        if dlg.exec()==dlg.DialogCode.Accepted:
            self.user=dlg.get_user()
            self.setWindowTitle(f"Beirut POS — {self.user.username} ({self.user.role})")
            for a in (self.act_manage,self.act_users,self.act_reports): a.setVisible(self.user.role=="admin")

    def _open_manage_products(self):
        if self.user.role!="admin": QMessageBox.warning(self,"الصلاحيات","هذه العملية للمدير فقط."); return
        cats=[c for c,_ in order_manager.categories]
        AdminProductsDialog(cats,
            on_add_category=lambda name: order_manager.catalog.add_category(name),
            on_add_product=lambda cat,name,price: order_manager.catalog.add_product(cat,name,price,username=self.user.username),
            current_admin=self.user.username).exec()

    def _open_users(self):
        if self.user.role!="admin": return
        from .admin_users_dialog import AdminUsersDialog
        AdminUsersDialog(self.user.username).exec()

    def _open_reports(self):
        if self.user.role!="admin": return
        from .admin_reports_dialog import AdminReportsDialog
        AdminReportsDialog().exec()

    # POS flow
    def _on_table_select(self, code):
        self.current_table=code; self.act_back.setVisible(True)
        self.order_header.setText(f"طلب: {code}")
        self.order_list.set_items(order_manager.get_items(code))
        sub,disc,tot=order_manager.get_totals(code); self.payment.set_totals(sub,disc,tot)
        self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
        self.pages.setCurrentIndex(PAGE_ORDER)

    def _on_pick(self, label, price_cents):
        if not self.current_table: return
        order_manager.add_item(self.current_table, label, price_cents, cashier=self.user.username)
        self.order_list.set_items(order_manager.get_items(self.current_table))
        sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)

    def _on_remove(self, index):
        if not self.current_table: return
        order_manager.remove_item(self.current_table, index)
        self.order_list.set_items(order_manager.get_items(self.current_table))
        sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)

    def _on_discount(self):
        if not self.current_table: return
        dlg=DiscountDialog()
        if dlg.exec()==dlg.DialogCode.Accepted:
            order_manager.apply_discount(self.current_table, dlg.amount)
            sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)

    def _on_pay(self, method):
        if not self.current_table: return
        # print bar ticket (items for bar) BEFORE settle
        items = order_manager.get_items(self.current_table)
        printer.print_bar_ticket(self.current_table, items)
        # settle (persists) & print cashier receipt AFTER totals are final
        if order_manager.settle(self.current_table, "cash" if method=="نقدي" else "visa", cashier=self.user.username):
            sub,disc,tot=0,0,0
            printer.print_cashier_receipt(self.current_table, items, 0, 0, 0, method, self.user.username)
            self.order_list.set_items([]); self.payment.set_totals(0,0,0)
            self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")

    # PS controls
    def _ps_start(self, mode):
        if not self.current_table: return
        order_manager.ps_start(self.current_table, mode); self.ps_controls.show_running("P2" if mode=="P2" else "P4")

    def _ps_switch(self, mode):
        if not self.current_table: return
        order_manager.ps_switch(self.current_table, mode); self.ps_controls.show_running(mode)
        sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)

    def _ps_stop(self):
        if not self.current_table: return
        order_manager.ps_stop(self.current_table); self.ps_controls.show_stopped("لا توجد جلسة بلايستيشن")
        self.order_list.set_items(order_manager.get_items(self.current_table))
        sub,disc,tot=order_manager.get_totals(self.current_table); self.payment.set_totals(sub,disc,tot)

    # Bus handlers
    def _on_table_total_changed(self, table_code, _t):
        self.table_map.update_table(table_code, total_cents=_t)
        if self.current_table==table_code and self.pages.currentIndex()==PAGE_ORDER:
            sub,disc,tot=order_manager.get_totals(table_code); self.payment.set_totals(sub,disc,tot)

    def _on_table_state_changed(self, table_code, state): self.table_map.update_table(table_code, state=state)
    def _on_catalog_changed(self): self.cat_grid.set_categories(order_manager.categories)
    def _on_ps_state_changed(self, table_code, active): self.table_map.update_table(table_code, ps_active=active)
