"""Focused UI coverage for delivery data in historical invoice details."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QLineEdit, QSpinBox, QDoubleSpinBox

from beirut_pos.apps.jewelry.services.db import JewelryInvoice
from beirut_pos.apps.jewelry.ui.dialogs import invoice_details_dialog as details_module


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _invoice(*, delivery_enabled=True):
    return JewelryInvoice(
        invoice_no="INV-1", datetime="2026-08-28", cashier_name="Cashier",
        txn_type="sale", subtotal=100, discount=10, discount_type="amount",
        discount_value=10, total=140, payment_method="Cash", notes="Ring bell",
        return_reason="", delivery_enabled=delivery_enabled, delivery_fee=50,
        delivery_address="Main Street", delivery_customer_name="Ahmed",
        delivery_phone="0111111111", delivery_company_id=7,
        delivery_company_name="In-house Delivery", delivery_status_id=3,
        delivery_status_name_en="Pending", delivery_status_name_ar="قيد الانتظار",
    )


def _dialog(monkeypatch, app, language, invoice=None):
    monkeypatch.setattr(details_module, "get_ui_language", lambda: language)
    monkeypatch.setattr(details_module, "fetch_invoice_details", lambda _number: (invoice or _invoice(), []))
    monkeypatch.setattr(details_module, "list_linked_invoices", lambda _number: [])
    monkeypatch.setattr(details_module, "list_customers", lambda: [])
    return details_module.InvoiceDetailsDialog("INV-1")


@pytest.mark.parametrize(
    ("language", "title", "status", "expected_labels", "excluded_labels"),
    [
        ("en", "Delivery Details", "Pending",
         ["Delivery Company", "Delivery Status", "Delivery Fee", "Delivery Customer",
          "Phone", "Address", "Delivery Notes"],
         ["تفاصيل التوصيل", "شركة التوصيل", "حالة التوصيل", "رسوم التوصيل"]),
        ("ar", "تفاصيل التوصيل", "قيد الانتظار",
         ["شركة التوصيل", "حالة التوصيل", "رسوم التوصيل", "اسم المستلم",
          "الهاتف", "العنوان", "ملاحظات التوصيل"],
         ["Delivery Details", "Delivery Company", "Delivery Status", "Delivery Fee"]),
    ],
)
def test_delivery_details_are_localized_and_read_only(
    monkeypatch, app, language, title, status, expected_labels, excluded_labels
):
    dialog = _dialog(monkeypatch, app, language)
    assert dialog.delivery_box.isHidden() is False
    assert dialog.delivery_box.title() == title
    assert dialog.delivery_values["company"].text() == "In-house Delivery"
    assert dialog.delivery_values["status"].text() == status
    assert dialog.delivery_values["fee"].text() == "50.00"
    assert dialog.delivery_values["customer"].text() == "Ahmed"
    assert dialog.delivery_values["phone"].text() == "0111111111"
    assert dialog.delivery_values["address"].text() == "Main Street"
    assert dialog.delivery_values["notes"].text() == "Ring bell"
    visible_text = title + " " + " ".join(
        label.text() for label in dialog.delivery_box.findChildren(details_module.QLabel)
    )
    assert all(label in visible_text for label in expected_labels)
    assert all(label not in visible_text for label in excluded_labels)
    assert not any(
        dialog.delivery_box.findChildren(widget_type)
        for widget_type in (QLineEdit, QSpinBox, QDoubleSpinBox)
    )
    assert dialog.values["total"].text() == "140.00"


def test_non_delivery_invoice_hides_delivery_section(monkeypatch, app):
    dialog = _dialog(monkeypatch, app, "en", _invoice(delivery_enabled=False))
    assert dialog.delivery_box.isHidden()
