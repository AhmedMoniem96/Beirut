"""Main window for Jewelry app."""

from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtWidgets import QLabel, QMainWindow, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from ..services.settings import load_gallery_settings
from ..services.session import get_current_user
from .tabs.inventory_tab import InventoryTab
from .tabs.invoice_tab import InvoiceTab
from .tabs.manufacturing_tab import ManufacturingTab
from .tabs.reports_tab import ReportsTab
from .tabs.returns_tab import ReturnsTab
from .tabs.settings_tab import SettingsTab
from .theme import gallery_stylesheet


class JewelryMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Crystal Gallery - POS")
        self.resize(1280, 840)

        self.central = QWidget()
        self.setCentralWidget(self.central)
        layout = QVBoxLayout(self.central)

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        layout.addWidget(self.title_label)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.invoice_tab = InvoiceTab()
        self.returns_tab = ReturnsTab()
        self.inventory_tab = InventoryTab(on_products_changed=self.invoice_tab.refresh_products)
        self.reports_tab = ReportsTab()
        self.settings_tab = SettingsTab(
            on_settings_changed=self._apply_settings,
            on_payment_methods_changed=self.invoice_tab._refresh_payment_methods,
        )
        self.manufacturing_tab = ManufacturingTab()

        self.tabs.addTab(self.invoice_tab, "New Invoice (فاتورة جديدة)")
        self.tabs.addTab(self.returns_tab, "Returns (مرتجع)")
        self.tabs.addTab(self.inventory_tab, "Inventory (المخزون)")
        self.tabs.addTab(self.manufacturing_tab, "Manufacturing (التصنيع)")
        self.tabs.addTab(self.reports_tab, "Reports (التقارير)")
        self.tabs.addTab(self.settings_tab, "Settings (الإعدادات)")
        self.tabs.currentChanged.connect(self._handle_tab_change)

        self._last_allowed_tab = 0

        self.setStyleSheet(gallery_stylesheet())
        self._apply_settings()
        self._apply_user_context()

    def _apply_settings(self) -> None:
        settings = load_gallery_settings()
        title = "Crystal Gallery - POS"
        if settings.rtl_enabled:
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.title_label.setText(f"{title} | {settings.name_ar}")
        else:
            self.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            self.title_label.setText(title)
        self.invoice_tab.apply_rtl_layout(settings.rtl_enabled)
        self.settings_tab.apply_rtl_layout(settings.rtl_enabled)

    def _apply_user_context(self) -> None:
        user = get_current_user()
        if not user:
            return
        self.invoice_tab.set_cashier_name(user.full_name)
        self.reports_tab.set_cashier_name(user.full_name)
        is_admin = user.role == "Admin"
        self.inventory_tab.set_edit_permissions(is_admin)

    def _handle_tab_change(self, index: int) -> None:
        user = get_current_user()
        if not user:
            self._last_allowed_tab = index
            return
        if user.role != "Admin" and self.tabs.widget(index) in (
            self.settings_tab,
            self.manufacturing_tab,
        ):
            QMessageBox.information(
                self,
                "Access Restricted",
                "This section is available for Admin users only.",
            )
            blocker = QSignalBlocker(self.tabs)
            self.tabs.setCurrentIndex(self._last_allowed_tab)
            del blocker
            return
        self._last_allowed_tab = index
