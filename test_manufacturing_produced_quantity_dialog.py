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
        id=7, name_ar="خاتم", name_en="Ring", sku="R-1", qty_on_hand=4.0
    )
    bom = SimpleNamespace(id=11, product_id=7, name="Summer Ring", active=True)
    material = SimpleNamespace(
        id=3, name_ar="ذهب", name_en="Gold", qty_on_hand=10.0, unit="g"
    )
    line = SimpleNamespace(material_id=3, qty_required=1.25)
    monkeypatch.setattr(manufacturing_tab, "list_products", lambda: [product])
    monkeypatch.setattr(manufacturing_tab, "list_materials", lambda: [material])
    monkeypatch.setattr(manufacturing_tab, "list_boms", lambda: [bom])
    monkeypatch.setattr(manufacturing_tab, "list_bom_lines", lambda _bom_id: [line])
    widget = manufacturing_tab.ManufacturingTab()
    widget._selected_bom_id = bom.id
    widget.produce_design_btn.setEnabled(True)
    yield widget, material
    widget.close()


def test_legacy_orders_ui_is_not_exposed(tab):
    widget, _material = tab

    assert not hasattr(widget, "_build_orders_tab")
    assert not hasattr(widget, "orders_tab")
    assert not hasattr(widget, "production_dialog")
    assert [widget.tabs.tabText(index) for index in range(widget.tabs.count())] == [
        "Designs",
        "Materials",
        "Production History",
    ]


def test_selected_design_opens_only_simplified_quantity_dialog(app, tab):
    widget, material = tab

    widget._open_production_for_selected_design()
    app.processEvents()
    dialog = widget.produced_quantity_dialog

    assert dialog.isModal()
    assert dialog.windowTitle() == "Add Produced Quantity"
    assert dialog.findChild(QtWidgets.QTableWidget, "requiredMaterialsPreview") is not None
    assert [button.text() for button in dialog.findChildren(QtWidgets.QPushButton)] == [
        "Cancel",
        "Confirm Production",
    ]
    visible_text = " ".join(label.text() for label in dialog.findChildren(QtWidgets.QLabel))
    assert "Summer Ring" in visible_text
    assert "Ring" in visible_text
    assert "4.000" in visible_text
    assert all(forbidden not in visible_text for forbidden in ("Draft", "Order No", "Status", "Notes"))

    material.qty_on_hand = 8.0
    widget.produced_qty_input.setValue(3.0)
    app.processEvents()
    preview = widget.produced_materials_preview
    assert preview.item(0, 2).text() == "3.750"
    assert preview.item(0, 3).text() == "8.000"
    dialog.reject()


def test_confirmation_handler_ignores_reentrant_signal(app, tab, monkeypatch):
    widget, _material = tab
    service_calls = []
    inventory_changes = []
    widget.inventory_changed.connect(lambda: inventory_changes.append(True))

    def produce_once(bom_id, quantity):
        service_calls.append((bom_id, quantity))
        # Simulate a second queued/direct confirmation signal arriving while
        # the first database operation is still in progress.
        confirm.clicked.emit()
        return {"success": True, "shortages": []}

    monkeypatch.setattr(manufacturing_tab, "produce_from_bom", produce_once)
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *args: None)
    widget._open_production_for_selected_design()
    app.processEvents()
    dialog = widget.produced_quantity_dialog
    confirm = dialog.findChild(QtWidgets.QPushButton, "confirmProductionButton")

    confirm.clicked.emit()

    assert service_calls == [(11, 1.0)]
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted
    assert inventory_changes == [True]
