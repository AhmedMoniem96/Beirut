import pytest


QtWidgets = pytest.importorskip("PyQt6.QtWidgets", exc_type=ImportError)
QApplication = QtWidgets.QApplication

from beirut_pos.apps.jewelry.ui.tabs import customers_tab


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    yield instance


@pytest.fixture
def tab(monkeypatch, app):
    rows = [{
        "name": "Existing Customer",
        "phone": "100",
        "address": "Beirut",
        "notes": "",
        "total_spend": 0,
        "invoice_count": 0,
        "last_invoice_date": "",
    }]
    monkeypatch.setattr(customers_tab, "get_customer_summary_rows", lambda term: rows)
    monkeypatch.setattr(customers_tab, "get_loyalty_balance", lambda phone: 0)
    monkeypatch.setattr(customers_tab, "get_customer_invoices", lambda customer_id: [])
    monkeypatch.setattr(customers_tab, "get_loyalty_history", lambda customer_id: [])
    return customers_tab.CustomersTab()


def test_selecting_customer_does_not_show_success(monkeypatch, tab):
    notifications = []
    monkeypatch.setattr(
        customers_tab.QMessageBox,
        "information",
        lambda *args: notifications.append(args),
    )

    tab.table.selectRow(0)

    assert notifications == []


def test_save_shows_create_then_update_notifications(monkeypatch, tab):
    notifications = []
    saves = []
    monkeypatch.setattr(
        customers_tab.QMessageBox,
        "information",
        lambda _parent, _title, message: notifications.append(message),
    )
    monkeypatch.setattr(
        customers_tab,
        "save_customer",
        lambda **kwargs: saves.append(kwargs) or kwargs["phone"],
    )

    tab._new_customer()
    tab.name_input.setText("New Customer")
    tab.phone_input.setText("200")
    tab.save_btn.click()

    tab.name_input.setText("Updated Customer")
    tab.save_btn.click()

    assert len(saves) == 2
    assert saves[0]["selected_phone"] == ""
    assert saves[1]["selected_phone"] == "200"
    assert notifications == [
        "Customer created successfully",
        "Customer updated successfully",
    ]
