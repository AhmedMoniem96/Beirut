"""Database coverage for delivery invoice persistence and configured defaults."""
import sqlite3
import sys
import types

import pytest

fake_core_db = types.ModuleType("beirut_pos.core.db")
fake_core_db.get_conn = lambda: None
sys.modules.setdefault("beirut_pos.core.db", fake_core_db)

from beirut_pos.apps.jewelry.services import auth, db


@pytest.fixture
def jewelry_db(tmp_path, monkeypatch):
    path = tmp_path / "jewelry.sqlite"
    monkeypatch.setattr(db, "get_conn", lambda: sqlite3.connect(path))
    monkeypatch.setattr(auth, "get_conn", lambda: sqlite3.connect(path))
    db.init_jewelry_db()
    return path


def test_active_companies_and_delivery_invoice_persistence(jewelry_db):
    company_id = db.create_delivery_company("Courier", "EXTERNAL", "", "", 50)
    disabled_id = db.create_delivery_company("Old Courier", "EXTERNAL", "", "", 99)
    db.disable_delivery_company(disabled_id)
    active = db.list_delivery_companies(include_inactive=False)
    assert company_id in [company.id for company in active]
    assert disabled_id not in [company.id for company in active]
    assert next(company.default_fee for company in active if company.id == company_id) == 50

    pending = db.list_active_statuses("DELIVERY")[0]
    with sqlite3.connect(jewelry_db) as conn:
        product_id = conn.execute(
            "INSERT INTO jw_products(name_ar, name_en, sku, price, qty_on_hand) "
            "VALUES ('خاتم', 'Ring', 'R1', 500, 1)"
        ).lastrowid
    item = db.JewelryInvoiceItem(product_id, "Ring", "R1", 1, 500, 500)
    invoice_no, _ = db.create_invoice(
        cashier_name="tester", txn_type="sale", customer_id=None,
        customer_name="Customer", customer_phone="123", subtotal=500,
        discount=0, discount_type="amount", discount_value=0,
        loyalty_earned=0, loyalty_redeemed=0, total=570,
        payment_method="Cash", payment_due_date="",
        payment_order_status_id=None, order_source="in_store",
        website_order_ref="", delivery_enabled=True,
        delivery_customer_name="Customer", delivery_phone="123",
        delivery_company_id=company_id, delivery_fee=70,
        delivery_address="Street", delivery_notes="Ring bell",
        delivery_status_id=pending.id, notes="", return_reason="", items=[item],
    )

    with sqlite3.connect(jewelry_db) as conn:
        row = conn.execute(
            "SELECT total, delivery_company_id, delivery_fee, delivery_status_id, "
            "delivery_customer_name, delivery_phone, delivery_address FROM jw_invoices "
            "WHERE invoice_no=?", (invoice_no,),
        ).fetchone()
        configured_fee = conn.execute(
            "SELECT default_fee FROM jw_delivery_companies WHERE id=?", (company_id,),
        ).fetchone()[0]
    assert row == (570, company_id, 70, pending.id, "Customer", "123", "Street")
    assert configured_fee == 50
    assert pending.name_en == "Pending"
    assert pending.name_ar == "قيد الانتظار"

    saved_invoice, _items = db.fetch_invoice_details(invoice_no)
    assert saved_invoice.total == 570
    assert saved_invoice.delivery_fee == 70
    assert saved_invoice.delivery_company_name == "Courier"
    assert saved_invoice.delivery_status_name_en == "Pending"
    assert saved_invoice.delivery_status_name_ar == "قيد الانتظار"
    assert saved_invoice.delivery_customer_name == "Customer"
    assert saved_invoice.delivery_phone == "123"
