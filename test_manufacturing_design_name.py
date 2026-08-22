from types import SimpleNamespace

import pytest


QtWidgets = pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)
QApplication = QtWidgets.QApplication

from beirut_pos.apps.jewelry.ui.tabs import manufacturing_tab


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(monkeypatch, app):
    product = SimpleNamespace(
        id=7,
        name_ar="خاتم",
        name_en="Ring",
        sku="R-1",
        barcode="1007",
        price=75.0,
    )
    monkeypatch.setattr(manufacturing_tab, "list_products", lambda: [product])
    monkeypatch.setattr(manufacturing_tab, "list_materials", lambda: [])
    monkeypatch.setattr(manufacturing_tab, "list_boms", lambda: [])
    widget = manufacturing_tab.ManufacturingTab()
    widget.show()
    app.processEvents()
    yield widget
    widget.close()


def test_design_name_is_visible_editable_and_has_client_facing_validation(monkeypatch, tab):
    assert tab.bom_name_input.isVisible()
    assert not tab.bom_name_input.isReadOnly()
    assert tab.bom_name_label.text() == "Design Name"

    warnings = []
    monkeypatch.setattr(
        manufacturing_tab.QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    tab.bom_name_input.clear()
    tab._save_bom()

    assert warnings == ["Design Name is required."]
    assert "BOM" not in warnings[0]
    assert "Recipe" not in warnings[0]


def test_design_form_does_not_create_a_product_selector(tab):
    assert not hasattr(tab, "bom_product_combo")
    assert "product" not in tab._design_field_labels


def test_edit_design_loads_its_linked_product_without_a_product_selector(monkeypatch, tab):
    bom = SimpleNamespace(
        id=12,
        product_id=7,
        name="Classic Ring",
        active=True,
        labor_cost=4.0,
        packaging_cost=2.0,
        other_cost=1.0,
    )
    line = SimpleNamespace(material_id=3, qty_required=1.25)
    monkeypatch.setattr(manufacturing_tab, "list_boms", lambda: [bom])
    monkeypatch.setattr(manufacturing_tab, "list_bom_lines", lambda _bom_id: [line])

    tab._load_design_by_id(bom.id)

    assert tab._selected_bom_id == bom.id
    assert tab._editing_product_id == bom.product_id
    assert tab.bom_name_input.text() == "Classic Ring"
    assert tab.design_product_name_en.text() == "Ring"
    assert tab.design_product_sku.text() == "R-1"
    assert tab.design_product_barcode.text() == "1007"
    assert tab.design_product_price.value() == 75.0
    assert tab.bom_lines_table.rowCount() == 1


def test_design_name_maps_to_bom_name_when_saved(monkeypatch, tab):
    saved = []
    inventory_changes = []
    tab.inventory_changed.connect(lambda: inventory_changes.append(True))
    def save_design(**kwargs):
        saved.append(kwargs)
        return 7, 8

    monkeypatch.setattr(manufacturing_tab, "save_product_design", save_design)
    monkeypatch.setattr(manufacturing_tab.QMessageBox, "information", lambda *args: None)
    tab.bom_name_input.setText("Summer Ring")
    tab.bom_lines_table.insertRow(0)
    material_item = QtWidgets.QTableWidgetItem("Gold")
    material_item.setData(manufacturing_tab.Qt.ItemDataRole.UserRole, 3)
    tab.bom_lines_table.setItem(0, 0, material_item)
    tab.bom_lines_table.setItem(0, 2, QtWidgets.QTableWidgetItem("1.250"))

    tab._save_bom()

    assert saved[0]["product_id"] == 7
    assert saved[0]["design_name"] == "Summer Ring"
    assert saved[0]["lines"] == [(3, 1.25)]
    assert inventory_changes == [True]
