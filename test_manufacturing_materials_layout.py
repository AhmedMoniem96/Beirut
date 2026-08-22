from types import SimpleNamespace

import pytest


QtWidgets = pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)
QApplication = QtWidgets.QApplication
QSizePolicy = QtWidgets.QSizePolicy

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
    yield widget
    widget.close()


@pytest.mark.parametrize(
    "width,height", [(1366, 768), (1920, 1080), (2560, 1440)]
)
def test_materials_table_is_the_expandable_section(tab, app, width, height):
    tab.resize(width, height)
    tab.show()
    app.processEvents()

    layout = tab.materials_tab.layout()
    assert layout.stretch(0) == 0
    assert layout.stretch(1) == 1
    assert layout.stretch(2) == 0
    assert tab.materials_table.minimumHeight() == 240
    assert tab.materials_table.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert tab.materials_table.height() >= 240


def test_materials_table_receives_extra_height_when_window_grows(tab, app):
    tab.resize(1366, 768)
    tab.show()
    app.processEvents()
    compact_height = tab.materials_table.height()

    tab.resize(1920, 1080)
    app.processEvents()

    assert tab.materials_table.height() > compact_height
    assert tab.material_barcode_printing_panel.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Preferred
    assert tab.material_barcode_printing_panel.diagnostics.minimumHeight() == 60


def test_design_used_materials_table_gets_the_section_height(tab, app):
    tab.tabs.setCurrentWidget(tab.boms_tab)
    tab.resize(1366, 768)
    tab.show()
    app.processEvents()

    lines_layout = tab.lines_box.layout()
    assert tab.lines_box.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert tab.bom_lines_table.minimumHeight() == 220
    assert tab.bom_lines_table.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert lines_layout.stretch(lines_layout.indexOf(tab.bom_lines_table)) == 1
    assert tab.bom_lines_table.height() >= 220

    # The input row and remove button stay compact around the expanding table.
    assert tab.add_bom_line_btn.sizePolicy().verticalPolicy() != QSizePolicy.Policy.Expanding
    assert tab.remove_line_btn.sizePolicy().verticalPolicy() != QSizePolicy.Policy.Expanding
