"""Focused contracts for delivery linkage on the Jewelry new-invoice screen."""
from types import SimpleNamespace

import pytest

QtWidgets = pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)
from PyQt6.QtCore import Qt

from beirut_pos.apps.jewelry.ui.tabs.invoice_tab import DeliveryDetailsDialog, InvoiceTab


@pytest.fixture(scope="module")
def application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def companies():
    return [
        SimpleNamespace(id=11, name="In-house Delivery", default_fee=50, active=True),
        SimpleNamespace(id=12, name="Courier", default_fee=75, active=True),
    ]


def test_dialog_lists_active_companies_by_id_and_localizes(application, monkeypatch, companies):
    monkeypatch.setattr(
        "beirut_pos.apps.jewelry.ui.tabs.invoice_tab.list_delivery_companies",
        lambda include_inactive=False: companies,
    )
    dialog = DeliveryDetailsDialog(language="ar")

    assert [dialog.delivery_company_combo.itemData(i) for i in range(1, 3)] == [11, 12]
    assert "شركة التوصيل" in [label.text() for label in dialog.findChildren(QtWidgets.QLabel)]
    assert "Delivery Company" not in [label.text() for label in dialog.findChildren(QtWidgets.QLabel)]
    dialog.close()


def test_company_default_fee_reloads_but_remains_editable(application, monkeypatch, companies):
    monkeypatch.setattr(
        "beirut_pos.apps.jewelry.ui.tabs.invoice_tab.list_delivery_companies",
        lambda include_inactive=False: companies,
    )
    dialog = DeliveryDetailsDialog(language="en")
    dialog.delivery_company_combo.setCurrentIndex(1)
    assert dialog.delivery_fee_input.value() == 50
    dialog.delivery_fee_input.setValue(70)
    assert dialog.delivery_fee_input.value() == 70
    assert companies[0].default_fee == 50
    dialog.delivery_company_combo.setCurrentIndex(2)
    assert dialog.delivery_fee_input.value() == 75
    dialog.close()


def _make_tab(monkeypatch, companies):
    monkeypatch.setattr("beirut_pos.apps.jewelry.ui.tabs.invoice_tab.list_delivery_companies",
                        lambda include_inactive=False: companies)
    monkeypatch.setattr("beirut_pos.apps.jewelry.ui.tabs.invoice_tab.list_product_categories", lambda: [])
    monkeypatch.setattr("beirut_pos.apps.jewelry.ui.tabs.invoice_tab.list_sale_catalog", lambda **kwargs: [])
    return InvoiceTab()


def test_delivery_total_payment_default_status_and_clear(application, monkeypatch, companies):
    statuses = [SimpleNamespace(id=21, name_ar="قيد الانتظار", name_en="Pending")]
    monkeypatch.setattr("beirut_pos.apps.jewelry.ui.tabs.invoice_tab.list_active_statuses",
                        lambda group: statuses if group == "DELIVERY" else [])
    tab = _make_tab(monkeypatch, companies)
    tab.items_table.setRowCount(1)
    tab.items_table.setItem(0, tab.ITEM_COL_LINE_TOTAL, QtWidgets.QTableWidgetItem("500.00"))
    tab.delivery_enabled_checkbox.blockSignals(True)
    tab.delivery_enabled_checkbox.setChecked(True)
    tab.delivery_enabled_checkbox.blockSignals(False)
    tab._refresh_delivery_statuses(required=True)
    assert tab.delivery_status_combo.currentData() == 21

    tab.delivery_company_combo.setCurrentIndex(tab.delivery_company_combo.findData(11))
    tab.delivery_fee_input.setValue(50)
    tab._recalculate_totals()
    assert tab._compute_invoice_totals("sale")["total"] == 550
    assert tab._current_grand_total == 550
    assert tab.pay_now_input.value() == 550

    tab._delivery_customer_name = "Delivery customer"
    tab._delivery_phone = "123"
    tab._delivery_address = "Street"
    tab._delivery_notes = "Ring bell"
    tab.delivery_address_input.setText("Street")
    tab._update_delivery_state(False)
    assert tab.delivery_company_combo.currentData() is None
    assert tab.delivery_status_combo.currentData() is None
    assert tab.delivery_fee_input.value() == 0
    assert not any((tab._delivery_customer_name, tab._delivery_phone,
                    tab._delivery_address, tab._delivery_notes))
    assert tab._compute_invoice_totals("sale")["total"] == 500
    assert tab._current_grand_total == 500
    tab.close()


def test_delivery_company_required_and_non_delivery_unchanged(application, monkeypatch, companies):
    tab = _make_tab(monkeypatch, companies)
    tab.items_table.setRowCount(1)
    tab.items_table.setItem(0, tab.ITEM_COL_LINE_TOTAL, QtWidgets.QTableWidgetItem("500.00"))
    tab.delivery_enabled_checkbox.blockSignals(True)
    tab.delivery_enabled_checkbox.setChecked(True)
    tab.delivery_enabled_checkbox.blockSignals(False)
    assert tab._validation_message() == "Please select a delivery company."
    tab.delivery_enabled_checkbox.setChecked(False)
    assert tab._compute_invoice_totals("sale")["total"] == 500
    tab.close()


def test_dialog_company_id_survives_validation_and_is_persisted(
        application, monkeypatch, companies):
    """Regression: accepting details must retain the itemData database ID."""
    statuses = [SimpleNamespace(id=21, name_ar="قيد الانتظار", name_en="Pending")]
    monkeypatch.setattr("beirut_pos.apps.jewelry.ui.tabs.invoice_tab.list_active_statuses",
                        lambda group: statuses if group == "DELIVERY" else [])
    tab = _make_tab(monkeypatch, companies)
    tab.items_table.setRowCount(1)
    tab.items_table.setItem(0, tab.ITEM_COL_LINE_TOTAL, QtWidgets.QTableWidgetItem("500.00"))

    def accept_company_a(dialog):
        dialog.delivery_company_combo.setCurrentIndex(
            dialog.delivery_company_combo.findData(11)
        )
        dialog.address_input.setText("Street")
        return QtWidgets.QDialog.DialogCode.Accepted

    monkeypatch.setattr(DeliveryDetailsDialog, "exec", accept_company_a)
    tab.delivery_enabled_checkbox.setChecked(True)

    assert tab._delivery_company_id == 11
    assert tab.delivery_company_combo.currentData() == 11
    assert tab.delivery_fee_input.value() == 50
    assert tab._validation_message() == ""

    # Reopening is preselected, and changing company updates both ID and fee.
    def accept_company_b(dialog):
        assert dialog.delivery_company_combo.currentData() == 11
        dialog.delivery_company_combo.setCurrentIndex(
            dialog.delivery_company_combo.findData(12)
        )
        return QtWidgets.QDialog.DialogCode.Accepted

    monkeypatch.setattr(DeliveryDetailsDialog, "exec", accept_company_b)
    assert tab._open_delivery_details_dialog()
    assert tab._delivery_company_id == 12
    assert tab.delivery_fee_input.value() == 75

    persisted = {}

    def capture_invoice(*args):
        persisted["delivery_company_id"] = args[20]
        return "JINV-00001", 1

    invoice_module = "beirut_pos.apps.jewelry.ui.tabs.invoice_tab"
    monkeypatch.setattr(f"{invoice_module}.create_invoice", capture_invoice)
    monkeypatch.setattr(f"{invoice_module}.create_order_payment", lambda *args, **kwargs: None)
    monkeypatch.setattr(f"{invoice_module}.recalculate_invoice_payment_totals", lambda *_: None)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(tab, "_collect_items", lambda: [])
    monkeypatch.setattr(tab, "_validate_material_stock", lambda items: None)
    monkeypatch.setattr(tab, "_refresh_recently_sold", lambda: None)
    monkeypatch.setattr(tab, "refresh_products", lambda: None)
    tab._save_invoice()

    assert persisted["delivery_company_id"] == 12
    tab.close()
