from types import SimpleNamespace

import pytest


QtWidgets = pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)
QApplication = QtWidgets.QApplication

from beirut_pos.apps.jewelry.ui.tabs import purchases_tab


def _purchase(purchase_id: int, *, quantity: float = 2, amount: float = 20):
    return SimpleNamespace(
        id=purchase_id,
        date="2026-08-01",
        category="Material Purchase",
        vendor=f"Supplier {purchase_id}",
        description="",
        amount=amount,
        payment_method="cash",
        notes="",
        linked_material_id=7,
        material_qty=quantity,
        worker_id=None,
        wage_period="",
    )


def _expense(purchase_id: int, *, amount: float = 20):
    purchase = _purchase(purchase_id, amount=amount)
    purchase.category = "Rent"
    purchase.linked_material_id = None
    purchase.material_qty = None
    return purchase


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def tab(monkeypatch, app):
    rows = [_purchase(11), _purchase(12, quantity=3, amount=45), _expense(21)]
    material = SimpleNamespace(id=7, name_ar="فضة", name_en="Silver")
    monkeypatch.setattr(purchases_tab, "list_purchases", lambda: list(rows))
    monkeypatch.setattr(purchases_tab, "list_materials", lambda: [material])
    monkeypatch.setattr(purchases_tab, "list_workers", lambda: [])
    widget = purchases_tab.PurchasesTab()
    widget._test_rows = rows
    return widget


def test_delete_with_no_selection_or_unsaved_form_does_nothing(monkeypatch, tab):
    calls = []
    monkeypatch.setattr(purchases_tab, "delete_purchase", lambda *args, **kwargs: calls.append((args, kwargs)))

    tab.material_table.clearSelection()
    tab.mat_supplier.setText("Unsaved supplier")
    tab._delete_material_purchase()

    assert calls == []
    assert tab.material_table.rowCount() == 2


def test_cancel_confirmation_keeps_selected_purchase(monkeypatch, tab):
    calls = []
    monkeypatch.setattr(purchases_tab, "delete_purchase", lambda *args, **kwargs: calls.append((args, kwargs)))
    monkeypatch.setattr(
        purchases_tab.QMessageBox,
        "question",
        lambda *args, **kwargs: purchases_tab.QMessageBox.StandardButton.No,
    )
    tab.material_table.selectRow(0)

    tab._delete_material_purchase()

    assert calls == []
    assert tab.material_table.rowCount() == 2


def test_confirm_deletes_only_selected_purchase_and_refreshes(monkeypatch, tab):
    calls = []

    def delete(purchase_id, *, reverse_stock=False):
        calls.append((purchase_id, reverse_stock))
        tab._test_rows[:] = [row for row in tab._test_rows if row.id != purchase_id]

    monkeypatch.setattr(purchases_tab, "delete_purchase", delete)
    monkeypatch.setattr(
        purchases_tab.QMessageBox,
        "question",
        lambda *args, **kwargs: purchases_tab.QMessageBox.StandardButton.Yes,
    )
    tab.material_table.selectRow(1)

    tab.mat_del_btn.click()

    assert calls == [(12, True)]
    assert [row.id for row in tab._test_rows] == [11]
    assert tab.material_table.rowCount() == 1
    assert tab._selected_material_purchase_id is None
    assert tab._material_delete_in_progress is False


def test_delete_guard_prevents_a_second_trigger(monkeypatch, tab):
    calls = []
    monkeypatch.setattr(purchases_tab, "delete_purchase", lambda *args, **kwargs: calls.append((args, kwargs)))
    tab.material_table.selectRow(0)
    tab._material_delete_in_progress = True

    tab._delete_material_purchase()

    assert calls == []


def test_clear_material_form_never_deletes_and_removes_selection(monkeypatch, tab):
    calls = []
    monkeypatch.setattr(purchases_tab, "delete_purchase", lambda *args, **kwargs: calls.append((args, kwargs)))
    tab.material_table.selectRow(0)
    tab._load_material_row(0, 0)

    tab.mat_clear_btn.click()
    tab.mat_del_btn.click()

    assert calls == []
    assert not tab.material_table.selectionModel().hasSelection()
    assert tab._selected_material_purchase_id is None
    assert tab.mat_supplier.text() == ""


def test_expense_delete_requires_selection_and_confirmation(monkeypatch, tab):
    calls = []
    monkeypatch.setattr(purchases_tab, "delete_purchase", lambda *args, **kwargs: calls.append((args, kwargs)))
    tab.expenses_table.clearSelection()

    tab._delete_expense()
    assert calls == []

    tab.expenses_table.selectRow(0)
    monkeypatch.setattr(
        purchases_tab.QMessageBox,
        "question",
        lambda *args, **kwargs: purchases_tab.QMessageBox.StandardButton.No,
    )
    tab._delete_expense()
    assert calls == []

    monkeypatch.setattr(
        purchases_tab.QMessageBox,
        "question",
        lambda *args, **kwargs: purchases_tab.QMessageBox.StandardButton.Yes,
    )
    tab._delete_expense()
    assert calls == [((21,), {})]


def test_clear_expense_form_never_deletes_and_removes_selection(monkeypatch, tab):
    calls = []
    monkeypatch.setattr(purchases_tab, "delete_purchase", lambda *args, **kwargs: calls.append((args, kwargs)))
    tab.expenses_table.selectRow(0)
    tab._load_expense_row(0, 0)

    tab.expense_clear_btn.click()
    tab.expense_del_btn.click()

    assert calls == []
    assert not tab.expenses_table.selectionModel().hasSelection()
    assert tab._selected_expense_id is None
    assert tab.expense_vendor.text() == ""


def test_purchase_clear_buttons_have_unambiguous_translations(tab):
    tab.apply_language("ar")
    assert tab.expense_clear_btn.text() == "تفريغ النموذج"
    assert tab.mat_clear_btn.text() == "تفريغ النموذج"

    tab.apply_language("en")
    assert tab.expense_clear_btn.text() == "Clear Form"
    assert tab.mat_clear_btn.text() == "Clear Form"
