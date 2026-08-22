from types import SimpleNamespace

import pytest


pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)

from beirut_pos.apps.jewelry.ui.main_window import JewelryMainWindow
from beirut_pos.apps.jewelry.ui.tabs.manufacturing_tab import ManufacturingTab


class Calls:
    def __init__(self):
        self.names = []

    def callback(self, name):
        return lambda: self.names.append(name)


def test_manufacturing_activation_refreshes_all_live_sources():
    calls = Calls()
    tab = SimpleNamespace()
    for name in (
        "_refresh_materials",
        "_refresh_design_products",
        "_refresh_history_products",
        "_refresh_boms",
        "_refresh_history_report",
        "_refresh_design_cost_summary",
    ):
        setattr(tab, name, calls.callback(name))

    ManufacturingTab.on_activated(tab)

    assert calls.names == [
        "_refresh_materials",
        "_refresh_design_products",
        "_refresh_history_products",
        "_refresh_boms",
        "_refresh_history_report",
        "_refresh_design_cost_summary",
    ]


@pytest.mark.parametrize(
    ("selected", "expected"),
    [
        ("manufacturing_tab", "manufacturing"),
        ("inventory_tab", "inventory"),
        ("invoice_tab", "invoice"),
        ("purchases_tab", "purchases"),
    ],
)
def test_opening_data_tabs_refreshes_without_recreating_window(monkeypatch, selected, expected):
    calls = Calls()
    window = SimpleNamespace()
    window.manufacturing_tab = SimpleNamespace(on_activated=calls.callback("manufacturing"))
    window.inventory_tab = SimpleNamespace(refresh=calls.callback("inventory"))
    window.invoice_tab = SimpleNamespace(refresh_products=calls.callback("invoice"))
    window.purchases_tab = SimpleNamespace(on_activated=calls.callback("purchases"))
    window.settings_tab = object()
    window._last_allowed_tab = 0
    chosen = getattr(window, selected)
    window.tabs = SimpleNamespace(widget=lambda _index: chosen)
    window._activate_tab = lambda index: JewelryMainWindow._activate_tab(window, index)
    monkeypatch.setattr("beirut_pos.apps.jewelry.ui.main_window.get_current_user", lambda: None)

    JewelryMainWindow._handle_tab_change(window, 1)

    assert calls.names == [expected]
