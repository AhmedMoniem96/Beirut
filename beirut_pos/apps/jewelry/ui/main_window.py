"""Main window for Jewelry app."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QSettings, QSignalBlocker, QSize, Qt
from PyQt6.QtGui import QAction, QGuiApplication
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..services.settings import load_gallery_settings
from ..services.i18n import choose_name, get_ui_language, t
from ..services.session import get_current_user
from .dialogs.unpaid_orders_dialog import UnpaidOrdersDialog
from .tabs.inventory_tab import InventoryTab
from .tabs.invoice_tab import InvoiceTab
from .tabs.manufacturing_tab import ManufacturingTab
from .tabs.reports_tab import ReportsTab
from .tabs.returns_tab import ReturnsTab
from .tabs.settings_tab import SettingsTab
from .tabs.customers_tab import CustomersTab
from .tabs.purchases_tab import PurchasesTab
from .theme import gallery_stylesheet

logger = logging.getLogger(__name__)


class JewelryMainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self._language = get_ui_language()
        self.setWindowTitle(t("app.title", language=self._language))
        self.resize(1280, 840)

        settings = QSettings()
        saved_geometry = settings.value("jw_main_geometry")
        if saved_geometry:
            self.restoreGeometry(saved_geometry)
        saved_state = settings.value("jw_main_state")
        if saved_state:
            self.restoreState(saved_state)
        self._ensure_window_visible(QSize(1280, 840))

        self.central = QWidget()
        self.central.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCentralWidget(self.central)
        layout = QVBoxLayout(self.central)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self.title_label = QLabel()
        self.title_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        header_layout.addWidget(self.title_label, 1)

        self.maximize_button = QToolButton()
        self.maximize_button.setText("▢")
        self.maximize_button.setAccessibleName("Toggle maximize")
        self.maximize_button.clicked.connect(self._toggle_maximize_restore)
        header_layout.addWidget(self.maximize_button, 0, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.tabs, 1)

        self.invoice_tab = InvoiceTab()
        self.returns_tab = ReturnsTab()
        self.inventory_tab = InventoryTab(on_products_changed=self.invoice_tab.refresh_products)
        self.reports_tab = ReportsTab()
        self.settings_tab = SettingsTab(
            on_settings_changed=self._apply_settings,
            on_payment_methods_changed=self.invoice_tab._refresh_payment_methods,
            on_language_changed=self._apply_language,
        )
        self.manufacturing_tab = ManufacturingTab()
        self.customers_tab = CustomersTab()
        self.purchases_tab = PurchasesTab()

        self.tabs.addTab(self.settings_tab, "")
        self.tabs.addTab(self.reports_tab, "")
        self.tabs.addTab(self.manufacturing_tab, "")
        self.tabs.addTab(self.inventory_tab, "")
        self.tabs.addTab(self.returns_tab, "")
        self.tabs.addTab(self.invoice_tab, "")
        self.tabs.addTab(self.customers_tab, "")
        self.tabs.addTab(self.purchases_tab, "")
        self.tabs.currentChanged.connect(self._handle_tab_change)
        self.tabs.setCurrentWidget(self.manufacturing_tab)
        if hasattr(self.manufacturing_tab, "inventory_changed"):
            self.manufacturing_tab.inventory_changed.connect(self.inventory_tab.refresh)

        self._build_menu()

        self._last_allowed_tab = 0
        self._normal_geometry = None

        self.setStyleSheet(gallery_stylesheet())
        self._apply_language(self._language)
        self._apply_settings()
        self._apply_user_context()

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()
        self.orders_menu = menu_bar.addMenu("")
        self.unpaid_orders_action = QAction("", self)
        self.unpaid_orders_action.triggered.connect(self._open_unpaid_orders)
        self.orders_menu.addAction(self.unpaid_orders_action)

    def closeEvent(self, event) -> None:
        settings = QSettings()
        settings.setValue("jw_main_geometry", self.saveGeometry())
        settings.setValue("jw_main_state", self.saveState())
        super().closeEvent(event)

    def _ensure_window_visible(self, default_size: QSize) -> None:
        screens = QGuiApplication.screens()
        if not screens:
            return
        window_state = self.windowState()
        has_fullscreen = window_state & Qt.WindowState.WindowFullScreen
        has_maximized = window_state & Qt.WindowState.WindowMaximized
        if has_fullscreen or has_maximized:
            geometry = self.geometry()
            if any(geometry.intersects(screen.availableGeometry()) for screen in screens):
                return
            normal_geometry = self.normalGeometry()
            self.showNormal()
            geometry = normal_geometry if normal_geometry.isValid() else geometry
        else:
            geometry = self.geometry()
        if any(geometry.intersects(screen.availableGeometry()) for screen in screens):
            return
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        width = min(default_size.width(), available.width())
        height = min(default_size.height(), available.height())
        x = max(available.left(), min(geometry.x(), available.right() - width + 1))
        y = max(available.top(), min(geometry.y(), available.bottom() - height + 1))
        self.resize(width, height)
        self.move(x, y)
        if has_fullscreen:
            self.showFullScreen()
        elif has_maximized:
            self.showMaximized()
        logger.debug(
            "Corrected main window geometry to %s (state=%s)",
            self.geometry(),
            int(self.windowState()),
        )

    def _apply_language(self, language: str | None = None) -> None:
        self._language = language or get_ui_language()
        self.setWindowTitle(t("app.title", language=self._language))
        self.tabs.setTabText(0, t("tab.settings", language=self._language))
        self.tabs.setTabText(1, t("tab.reports", language=self._language))
        self.tabs.setTabText(2, t("tab.manufacturing", language=self._language))
        self.tabs.setTabText(3, t("tab.inventory", language=self._language))
        self.tabs.setTabText(4, t("tab.returns", language=self._language))
        self.tabs.setTabText(5, t("tab.invoice", language=self._language))
        self.tabs.setTabText(6, t("tab.customers", language=self._language))
        self.tabs.setTabText(7, t("tab.purchases", language=self._language))
        self.orders_menu.setTitle(t("menu.orders", language=self._language))
        self.unpaid_orders_action.setText(t("menu.unpaid_orders", language=self._language))
        self.invoice_tab.apply_language(self._language)
        self.returns_tab.apply_language(self._language)
        self.inventory_tab.apply_language(self._language)
        self.manufacturing_tab.apply_language(self._language)
        self.reports_tab.apply_language(self._language)
        self.settings_tab.apply_language(self._language)
        self.customers_tab.apply_language(self._language)
        self.purchases_tab.apply_language(self._language)

        for widget in QApplication.topLevelWidgets():
            if widget is self:
                continue
            apply_language = getattr(widget, "apply_language", None)
            if callable(apply_language):
                apply_language(self._language)

    def _apply_settings(self) -> None:
        settings = load_gallery_settings()
        if hasattr(self, "inventory_tab"):
            self.inventory_tab.barcode_printing_panel.refresh_configuration()
        title = t("app.title", language=self._language)
        if settings.rtl_enabled:
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            gallery_name = choose_name(settings.name_ar, settings.name_en, language=self._language)
            self.title_label.setText(f"{title} | {gallery_name}")
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

    def _open_unpaid_orders(self) -> None:
        dialog = UnpaidOrdersDialog(self)
        dialog.exec()

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
                t("common.access_restricted_title", language=self._language),
                t("common.access_admin_only", language=self._language),
            )
            blocker = QSignalBlocker(self.tabs)
            self.tabs.setCurrentIndex(self._last_allowed_tab)
            del blocker
            return
        self._last_allowed_tab = index

    def _toggle_maximize_restore(self) -> None:
        logger.debug(
            "Toggle maximize before: state=%s maximized=%s size=%s",
            int(self.windowState()),
            self.isMaximized(),
            self.size(),
        )
        if self.window().isMaximized():
            self.showNormal()
            target_geometry = None
            if self._normal_geometry and self._normal_geometry.isValid():
                target_geometry = self._normal_geometry
            else:
                fallback_geometry = self.normalGeometry()
                if fallback_geometry.isValid():
                    target_geometry = fallback_geometry
            if target_geometry:
                self.resize(target_geometry.size())
                self.move(target_geometry.topLeft())
        else:
            self._normal_geometry = self.geometry()
            self.showMaximized()
        logger.debug(
            "Toggle maximize after: state=%s maximized=%s size=%s",
            int(self.windowState()),
            self.isMaximized(),
            self.size(),
        )
