import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QDoubleSpinBox, QMessageBox

from beirut_pos.apps.jewelry.services.db import JewelryReturnSourceInvoice, ReturnableInvoiceItem
from beirut_pos.apps.jewelry.ui.tabs import returns_tab


@pytest.fixture(scope="module")
def app():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def tab(app, monkeypatch):
    monkeypatch.setattr(returns_tab, "list_return_invoices", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(returns_tab, "list_full_invoice_history", lambda *_args, **_kwargs: [])
    widget = returns_tab.ReturnsTab()
    yield widget
    widget.close()


def _item(item_id=10, remaining=2.0, returned=0.0, unit_price=25.0):
    return ReturnableInvoiceItem(
        invoice_item_id=item_id,
        invoice_id=1,
        invoice_no="INV-1",
        product_id=item_id,
        product_name=f"Item {item_id}",
        product_code=f"SKU-{item_id}",
        sold_qty=remaining + returned,
        returned_qty=returned,
        remaining_qty=remaining,
        unit_price=unit_price,
    )


def _source():
    return JewelryReturnSourceInvoice("INV-1", "Customer", "2026-08-01T10:00:00", "Cash", 50.0)


def test_history_starts_collapsed_and_single_item_is_preselected(tab, monkeypatch):
    monkeypatch.setattr(returns_tab, "fetch_source_invoice_items_with_remaining_returnable_qty", lambda _no: [_item()])
    monkeypatch.setattr(returns_tab, "fetch_return_source_invoice", lambda _no: _source())

    tab.source_invoice_edit.setText("INV-1")
    tab.load_source_invoice()

    assert not tab.history_group.isChecked()
    assert not tab.history_content.isVisible()
    assert tab.invoice_info.isVisibleTo(tab)
    assert tab.source_items_table.item(0, 0).checkState() == Qt.CheckState.Checked
    qty = tab.source_items_table.cellWidget(0, 5)
    assert isinstance(qty, QDoubleSpinBox)
    assert qty.value() == 2.0
    assert tab.items_selected_value.text() == "1"
    assert tab.return_total_value.text() == "50.00"


def test_multi_item_selection_updates_summary_live(tab, monkeypatch):
    monkeypatch.setattr(
        returns_tab,
        "fetch_source_invoice_items_with_remaining_returnable_qty",
        lambda _no: [_item(10, 2.0, unit_price=25.0), _item(11, 1.0, returned=1.0, unit_price=40.0)],
    )
    monkeypatch.setattr(returns_tab, "fetch_return_source_invoice", lambda _no: _source())

    tab.source_invoice_edit.setText("INV-1")
    tab.load_source_invoice()
    assert tab.items_selected_value.text() == "0"
    tab.source_items_table.item(1, 0).setCheckState(Qt.CheckState.Checked)
    tab.source_items_table.cellWidget(1, 5).setValue(0.5)

    assert tab.items_selected_value.text() == "1"
    assert tab.return_total_value.text() == "20.00"
    tab.return_method_combo.setCurrentText("Exchange")
    assert tab.summary_method_value.text() == "Exchange"


def test_success_resets_workflow_and_refreshes_history(tab, monkeypatch):
    monkeypatch.setattr(returns_tab, "fetch_source_invoice_items_with_remaining_returnable_qty", lambda _no: [_item()])
    monkeypatch.setattr(returns_tab, "fetch_return_source_invoice", lambda _no: _source())
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: messages.append(_args[1:]))
    created = []
    monkeypatch.setattr(returns_tab, "create_return_invoice_from_source", lambda **kwargs: (created.append(kwargs) or ("RET-1", 2)))
    refreshes = []
    monkeypatch.setattr(tab, "refresh", lambda: refreshes.append("daily"))
    monkeypatch.setattr(tab, "load_full_history", lambda: refreshes.append("full"))

    tab.source_invoice_edit.setText("INV-1")
    tab.load_source_invoice()
    tab.return_method_combo.setCurrentText("Credit / Customer Balance")
    tab.return_reason_combo.setCurrentText("Defective item")
    tab.create_return_invoice()

    assert created[0]["payment_method"] == "Credit / Customer Balance"
    assert created[0]["return_reason"].startswith("Defective item | Ref:")
    assert tab.source_invoice_edit.text() == "INV-1"
    assert tab.source_invoice_edit.hasSelectedText()
    assert tab.source_items_table.rowCount() == 0
    assert not tab.invoice_info.isVisible()
    assert tab.return_method_combo.currentIndex() == 0
    assert tab.return_reason_combo.currentIndex() == 0
    assert refreshes == ["daily", "full"]


def test_failed_return_keeps_loaded_invoice_and_selection(tab, monkeypatch):
    monkeypatch.setattr(returns_tab, "fetch_source_invoice_items_with_remaining_returnable_qty", lambda _no: [_item()])
    monkeypatch.setattr(returns_tab, "fetch_return_source_invoice", lambda _no: _source())
    monkeypatch.setattr(QMessageBox, "information", lambda *_args: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *_args: None)
    monkeypatch.setattr(
        returns_tab, "create_return_invoice_from_source",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("database failed")),
    )

    tab.source_invoice_edit.setText("INV-1")
    tab.load_source_invoice()
    tab.create_return_invoice()

    assert tab.source_items_table.rowCount() == 1
    assert tab.source_items_table.item(0, 0).checkState() == Qt.CheckState.Checked
    assert tab.invoice_info.isVisibleTo(tab)
