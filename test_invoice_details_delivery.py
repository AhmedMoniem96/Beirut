"""Focused UI coverage for delivery data in the shared invoice details dialog."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QSpinBox

from beirut_pos.apps.jewelry.services.db import JewelryInvoice
from beirut_pos.apps.jewelry.ui.dialogs import invoice_details_dialog as details_module


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _invoice(*, delivery_enabled=True):
    return JewelryInvoice(
        invoice_no="INV-DELIVERY", datetime="2026-08-28", cashier_name="Cashier",
        txn_type="sale", subtotal=100, discount=5, discount_type="amount",
        discount_value=5, total=145, payment_method="Cash", notes="Ring bell",
        return_reason="", delivery_enabled=delivery_enabled, delivery_fee=50,
        delivery_address="Beirut, Hamra", delivery_customer_name="Ahmed",
        delivery_phone="011234567", delivery_company_name="In-house Delivery",
        delivery_status_name_ar="قيد الانتظار", delivery_status_name_en="Pending",
    )


def _dialog(monkeypatch, app, language="en", *, delivery_enabled=True):
    monkeypatch.setattr(details_module, "fetch_invoice_details", lambda _number: (
        _invoice(delivery_enabled=delivery_enabled), []
    ))
    monkeypatch.setattr(details_module, "list_linked_invoices", lambda _number: [])
    monkeypatch.setattr(details_module, "list_customers", lambda: [])
    monkeypatch.setattr(details_module, "get_ui_language", lambda: language)
    return details_module.InvoiceDetailsDialog("INV-DELIVERY")


def test_delivery_invoice_shows_complete_read_only_english_section(monkeypatch, app):
    dialog = _dialog(monkeypatch, app)

    assert not dialog.delivery_section.isHidden()
    assert dialog.delivery_section.title() == "Delivery Details"
    assert {key: value.text() for key, value in dialog.delivery_values.items()} == {
        "company": "In-house Delivery", "status": "Pending", "fee": "50.00",
        "customer": "Ahmed", "phone": "011234567", "address": "Beirut, Hamra",
        "notes": "Ring bell",
    }
    assert [label.text() for label in dialog.delivery_labels.values()] == [
        "Delivery Company", "Delivery Status", "Delivery Fee", "Delivery Customer",
        "Phone", "Address", "Delivery Notes",
    ]
    assert dialog.values["total"].text() == "145.00"
    assert all(isinstance(value, QLabel) for value in dialog.delivery_values.values())
    assert not dialog.delivery_section.findChildren(QLineEdit)
    assert not dialog.delivery_section.findChildren(QSpinBox)


def test_non_delivery_invoice_hides_delivery_section(monkeypatch, app):
    dialog = _dialog(monkeypatch, app, delivery_enabled=False)
    assert dialog.delivery_section.isHidden()


def test_arabic_mode_uses_only_arabic_delivery_labels_and_status(monkeypatch, app):
    dialog = _dialog(monkeypatch, app, language="ar")

    assert dialog.delivery_section.title() == "تفاصيل التوصيل"
    assert dialog.delivery_values["status"].text() == "قيد الانتظار"
    assert [label.text() for label in dialog.delivery_labels.values()] == [
        "شركة التوصيل", "حالة التوصيل", "رسوم التوصيل", "اسم المستلم",
        "الهاتف", "العنوان", "ملاحظات التوصيل",
    ]
    assert "Delivery" not in dialog.delivery_section.title()


def test_empty_delivery_values_use_em_dash(monkeypatch, app):
    invoice = _invoice()
    invoice.delivery_company_name = ""
    invoice.delivery_phone = ""
    monkeypatch.setattr(details_module, "fetch_invoice_details", lambda _number: (invoice, []))
    monkeypatch.setattr(details_module, "list_linked_invoices", lambda _number: [])
    monkeypatch.setattr(details_module, "list_customers", lambda: [])
    monkeypatch.setattr(details_module, "get_ui_language", lambda: "en")

    dialog = details_module.InvoiceDetailsDialog(invoice.invoice_no)
    assert dialog.delivery_values["company"].text() == "—"
    assert dialog.delivery_values["phone"].text() == "—"
