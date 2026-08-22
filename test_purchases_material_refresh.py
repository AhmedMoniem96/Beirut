from types import SimpleNamespace

import pytest


QtWidgets = pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)
QApplication = QtWidgets.QApplication

from beirut_pos.apps.jewelry.ui.tabs import purchases_tab


def _material(material_id, name_ar="", name_en="", code=""):
    return SimpleNamespace(
        id=material_id,
        name_ar=name_ar,
        name_en=name_en,
        code=code,
    )


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def material_rows(monkeypatch):
    rows = [_material(1, "ذهب", "Gold", "AU")]
    monkeypatch.setattr(purchases_tab, "list_materials", lambda: list(rows))
    monkeypatch.setattr(purchases_tab, "list_purchases", lambda: [])
    monkeypatch.setattr(purchases_tab, "list_workers", lambda: [])
    return rows


def test_opening_material_purchases_reloads_shared_materials(app, material_rows):
    tab = purchases_tab.PurchasesTab()
    material_rows.append(_material(2, "فضة", "Silver", "AG"))

    tab.tabs.setCurrentWidget(tab.material_tab)

    assert tab.mat_material.count() == 3
    assert tab.mat_material.itemText(tab.mat_material.findData(2)) == "فضة (AG)"
    assert tab.mat_material.itemData(tab.mat_material.findData(2)) == 2


def test_refresh_preserves_valid_selection_and_removes_stale_rows(app, material_rows):
    material_rows.append(_material(2, "", "Silver", "AG"))
    tab = purchases_tab.PurchasesTab()
    tab.mat_material.setCurrentIndex(tab.mat_material.findData(2))

    material_rows[1] = _material(2, "فضة معدلة", "Edited Silver", "AG-2")
    tab.on_activated()

    assert tab.mat_material.currentData() == 2
    assert tab.mat_material.currentText() == "فضة معدلة (AG-2)"

    material_rows.pop()
    tab.on_activated()
    assert tab.mat_material.findData(2) == -1
    assert tab.mat_material.currentData() is None


def test_empty_material_database_is_safe(app, material_rows):
    material_rows.clear()
    tab = purchases_tab.PurchasesTab()

    tab._refresh_material_combo()

    assert tab.mat_material.count() == 1
    assert tab.mat_material.currentData() is None


def test_material_label_falls_back_to_english_then_code(app, material_rows):
    material_rows[:] = [
        _material(3, "", "Copper", "CU"),
        _material(4, "", "", "PT"),
    ]
    tab = purchases_tab.PurchasesTab()

    assert tab.mat_material.itemText(tab.mat_material.findData(3)) == "Copper (CU)"
    assert tab.mat_material.itemText(tab.mat_material.findData(4)) == "PT"
