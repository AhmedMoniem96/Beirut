import sqlite3
import sys
import types

import pytest

fake_core_db = types.ModuleType("beirut_pos.core.db")
fake_core_db.get_conn = lambda: None
sys.modules.setdefault("beirut_pos.core.db", fake_core_db)

from beirut_pos.apps.jewelry.services import auth, db


@pytest.fixture
def material_db(tmp_path, monkeypatch):
    path = tmp_path / "materials.sqlite"
    monkeypatch.setattr(db, "get_conn", lambda: sqlite3.connect(path))
    monkeypatch.setattr(auth, "get_conn", lambda: sqlite3.connect(path))
    db.init_jewelry_db()
    return path


def save(**overrides):
    values = dict(
        material_id=None,
        name_ar="فضة",
        name_en="Silver",
        code="SILVER",
        qty_on_hand=2,
        unit="g",
        min_qty=1,
        cost_per_unit=3,
    )
    values.update(overrides)
    return db.save_material(**values)


def test_material_migration_and_generated_barcode(material_db):
    material_id = save()
    material = db.list_materials()[0]

    assert material_id == material.id
    assert material.barcode == f"M{material_id:06d}"
    assert material.saleable is False
    assert material.sale_price is None
    with sqlite3.connect(material_db) as conn:
        indexes = {row[1] for row in conn.execute("PRAGMA index_list(jw_materials)")}
    assert "jw_materials_barcode_unique" in indexes


def test_saleable_material_requires_positive_price(material_db):
    with pytest.raises(ValueError, match="greater than zero"):
        save(saleable=True, sale_price=0)


def test_blank_barcode_on_edit_preserves_generated_value(material_db):
    material_id = save()
    original = db.list_materials()[0].barcode

    save(material_id=material_id, code="UPDATED", barcode="")

    material = db.list_materials()[0]
    assert material.code == "UPDATED"
    assert material.barcode == original


def test_barcodes_are_unique_across_products_and_materials(material_db):
    material_id = save(barcode="SHARED")
    assert db.barcode_exists("SHARED")
    with pytest.raises(ValueError, match="Duplicate barcode"):
        db.save_product(
            None, "منتج", "Product", "P1", "SHARED", "", 10, 0, 0, "", False, "", ""
        )

    with sqlite3.connect(material_db) as conn:
        conn.execute("""INSERT INTO jw_products
               (name_ar, name_en, sku, barcode, barcode_type, price, qty_on_hand,
                min_qty, category, handmade_flag, stone_type, color)
               VALUES ('م', 'P', 'P2', 'PRODUCT-CODE', '', 1, 0, 0, '', 0, '', '')""")
    with pytest.raises(ValueError, match="product"):
        save(material_id=material_id, barcode="PRODUCT-CODE")
