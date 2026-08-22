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
    product = SimpleNamespace(id=7, name_ar="خاتم", name_en="Ring", sku="R-1")
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


def test_design_name_maps_to_bom_name_when_saved(monkeypatch, tab):
    saved = []
    inventory_changes = []
    tab.inventory_changed.connect(lambda: inventory_changes.append(True))
    monkeypatch.setattr(manufacturing_tab, "save_bom", lambda *args: saved.append(args))
    monkeypatch.setattr(manufacturing_tab.QMessageBox, "information", lambda *args: None)
    tab.bom_name_input.setText("Summer Ring")
    tab.bom_lines_table.insertRow(0)
    material_item = QtWidgets.QTableWidgetItem("Gold")
    material_item.setData(manufacturing_tab.Qt.ItemDataRole.UserRole, 3)
    tab.bom_lines_table.setItem(0, 0, material_item)
    tab.bom_lines_table.setItem(0, 2, QtWidgets.QTableWidgetItem("1.250"))

    tab._save_bom()

    assert saved[0][1:3] == (7, "Summer Ring")
    assert inventory_changes == [True]
