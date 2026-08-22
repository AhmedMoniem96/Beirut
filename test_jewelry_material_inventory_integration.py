"""Focused integration tests for the shared jewelry material stock ledger."""

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


def save_material(**overrides):
    fields = dict(material_id=None, name_ar="فضة", name_en="Silver", code="AG",
                  qty_on_hand=10, unit="g", min_qty=1, cost_per_unit=3)
    fields.update(overrides)
    return db.save_material(**fields)


def sell(item):
    return db.create_invoice(
        cashier_name="tester", txn_type="sale", customer_id=None,
        customer_name="", customer_phone="", subtotal=item.line_total,
        discount=0, discount_type="amount", discount_value=0,
        loyalty_earned=0, loyalty_redeemed=0, total=item.line_total,
        payment_method="Cash", payment_due_date="",
        payment_order_status_id=None, order_source="in_store",
        website_order_ref="", delivery_enabled=False,
        delivery_customer_name="", delivery_phone="", delivery_company_id=None,
        delivery_fee=0, delivery_address="", delivery_notes="",
        delivery_status_id=None, notes="", return_reason="", items=[item],
    )


def material_item(material_id, qty, price=8):
    return db.JewelryInvoiceItem(None, "Silver", "AG", qty, price, qty * price,
                                 "material", material_id, "g")


def stock(path, material_id):
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT qty_on_hand FROM jw_materials WHERE id=?",
                            (material_id,)).fetchone()[0]


def test_defaults_price_validation_catalog_and_all_search_fields(jewelry_db):
    hidden_id = save_material(barcode="HIDDEN-BAR")
    assert db.list_materials()[0].saleable is False
    assert all(x.source_id != hidden_id for x in db.list_sale_catalog())

    for bad_price in (None, 0, -1):
        with pytest.raises(ValueError, match="greater than zero"):
            save_material(code=f"BAD-{bad_price}", saleable=True, sale_price=bad_price)

    visible_id = save_material(name_ar="ذهب", name_en="Gold wire", code="AU-WIRE",
                               barcode="MAT-900", saleable=True, sale_price=12)
    for query in ("ذهب", "Gold", "AU-WIRE", "MAT-900"):
        result = db.list_sale_catalog(query)
        assert [(x.source_type, x.source_id) for x in result] == [("material", visible_id)]


def test_decimal_sale_is_atomic_rejects_oversell_and_has_no_product_mirror(jewelry_db):
    material_id = save_material(qty_on_hand=2.75, saleable=True, sale_price=8)
    invoice_no, _ = sell(material_item(material_id, 1.25))
    assert invoice_no.startswith("JINV-")
    assert stock(jewelry_db, material_id) == pytest.approx(1.5)
    with sqlite3.connect(jewelry_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM jw_products").fetchone()[0] == 0

    with pytest.raises(ValueError, match="insufficient stock"):
        sell(material_item(material_id, 2))
    assert stock(jewelry_db, material_id) == pytest.approx(1.5)
    with sqlite3.connect(jewelry_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM jw_invoices").fetchone()[0] == 1


def test_purchase_manufacturing_sale_and_partial_return_share_one_row(jewelry_db):
    material_id = save_material(qty_on_hand=5, saleable=True, sale_price=8)
    db.create_purchase(date="2026-08-22", category="Material Purchase", vendor="V",
                       amount=30, payment_method="Cash", linked_material_id=material_id,
                       material_qty=3)
    assert stock(jewelry_db, material_id) == 8

    product_id, bom_id = db.save_product_design(
        product_id=None, bom_id=None, name_ar="خاتم", name_en="Ring", sku="R1",
        barcode="", price=50, design_name="Ring", active=True,
        lines=[(material_id, 1.5)],
    )
    db.produce_from_bom(bom_id, 2)
    assert stock(jewelry_db, material_id) == 5
    assert db.find_product_by_code("R1").qty_on_hand == 2

    sale_no, _ = sell(material_item(material_id, 2.5))
    source = db.fetch_source_invoice_items_with_remaining_returnable_qty(sale_no)[0]
    db.create_return_invoice_from_source(
        sale_no, "tester", "partial", [{"source_invoice_item_id": source.invoice_item_id,
                                          "qty": 0.75}],
    )
    assert stock(jewelry_db, material_id) == pytest.approx(3.25)


def test_historical_material_sale_remains_readable_after_saleability_disabled(jewelry_db):
    material_id = save_material(saleable=True, sale_price=8)
    sale_no, _ = sell(material_item(material_id, 2))
    save_material(material_id=material_id, saleable=False, sale_price=None,
                  qty_on_hand=8)
    assert db.find_sale_catalog_item_by_code("AG") is None
    item = db.fetch_source_invoice_items_with_remaining_returnable_qty(sale_no)[0]
    assert (item.item_type, item.material_id, item.product_name, item.unit) == (
        "material", material_id, "Silver", "g")


def test_legacy_blank_barcodes_are_assigned_only_when_each_row_is_saved(jewelry_db):
    material_id = save_material()
    product_id = db.save_product(None, "م", "Product", "P1", "", "", 1, 0, 0,
                                 "", False, "", "")
    with sqlite3.connect(jewelry_db) as conn:
        conn.execute("UPDATE jw_materials SET barcode='' WHERE id=?", (material_id,))
        conn.execute("UPDATE jw_products SET barcode='' WHERE id=?", (product_id,))
    assert db.list_materials()[0].barcode == ""
    assert db.find_product_by_code("P1").barcode == ""

    save_material(material_id=material_id)
    assert db.list_materials()[0].barcode == f"M{material_id:06d}"
    assert db.find_product_by_code("P1").barcode == ""
    db.save_product(product_id, "م", "Product", "P1", "", "", 1, 0, 0,
                    "", False, "", "")
    assert db.find_product_by_code("P1").barcode == f"P{product_id:010d}"
