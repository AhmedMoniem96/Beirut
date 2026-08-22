"""Small widget-contract tests for material selling, without a full main window."""

from types import SimpleNamespace

import pytest


QtWidgets = pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)
from PyQt6.QtCore import Qt

from beirut_pos.apps.jewelry.ui.tabs.invoice_tab import InvoiceTab


@pytest.fixture(scope="module")
def application():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.mark.parametrize(
    ("language", "expected"),
    [("en", "Silver — Material — 2.5 g"), ("ar", "فضة — خامة — 2.5 g")],
)
def test_catalog_material_displays_source_type_stock_and_bilingual_label(language, expected):
    tab = SimpleNamespace(_language=language)
    item = SimpleNamespace(source_type="material", name_ar="فضة", name_en="Silver",
                           qty_on_hand=2.5, unit="g")
    assert InvoiceTab._catalog_display_name(tab, item) == expected


def test_material_invoice_row_keeps_decimal_quantity_and_source_metadata(application, monkeypatch):
    """The isolated tab exposes three-decimal entry and identity on its row."""
    # Keep construction isolated from service state; only exercise row rendering.
    monkeypatch.setattr("beirut_pos.apps.jewelry.ui.tabs.invoice_tab.list_product_categories", lambda: [])
    monkeypatch.setattr("beirut_pos.apps.jewelry.ui.tabs.invoice_tab.list_sale_catalog", lambda **_kwargs: [])
    tab = InvoiceTab()
    material = SimpleNamespace(source_type="material", source_id=17, name_ar="فضة",
                               name_en="Silver", code="AG", barcode="M000017",
                               qty_on_hand=5, unit="g", price=8)

    tab._add_product_to_invoice(material, 1.125)

    assert tab.qty_input.decimals() == 3
    assert tab.items_table.item(0, tab.ITEM_COL_QTY).text() == "1.125"
    assert tab.items_table.item(0, tab.ITEM_COL_PRODUCT).data(Qt.ItemDataRole.UserRole) == (
        "material", 17, "g")
    tab.close()
