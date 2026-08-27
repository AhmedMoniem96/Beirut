import sqlite3
import sys
import types

import pytest

core_db = types.ModuleType("beirut_pos.core.db")
core_db.get_conn = lambda: None
original_core_db = sys.modules.get("beirut_pos.core.db")
sys.modules["beirut_pos.core.db"] = core_db
from beirut_pos.apps.jewelry.services import db
if original_core_db is None:
    del sys.modules["beirut_pos.core.db"]
else:
    sys.modules["beirut_pos.core.db"] = original_core_db
from beirut_pos.apps.jewelry.services.i18n import t


class OpenConnection:
    def __init__(self, connection): self.connection = connection
    def __getattr__(self, name):
        return (lambda: None) if name == "close" else getattr(self.connection, name)


@pytest.fixture
def wages(monkeypatch):
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
      CREATE TABLE jw_workers(id INTEGER PRIMARY KEY, name TEXT, phone TEXT, role TEXT,
        default_wage REAL, wage_type TEXT, notes TEXT, active INTEGER);
      INSERT INTO jw_workers VALUES (1, 'Worker', '', '', 5000, 'monthly', '', 1);
      CREATE TABLE jw_purchases(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, category TEXT,
        vendor TEXT, description TEXT, amount REAL, payment_method TEXT, notes TEXT,
        linked_material_id INTEGER, material_qty REAL, worker_id INTEGER, wage_period TEXT,
        created_at TEXT, movement_type TEXT DEFAULT 'wage_payment', applied_amount REAL DEFAULT 0,
        remaining_amount REAL DEFAULT 0, gross_amount REAL DEFAULT 0, apply_to_month TEXT);
    """)
    monkeypatch.setattr(db, "get_conn", lambda: OpenConnection(connection))
    return connection


def test_account_and_preview_share_balance_service(wages):
    db.create_wage_movement(worker_id=1, movement_type="advance", date="2026-08-01", amount=500)
    db.create_wage_movement(worker_id=1, movement_type="deduction", date="2026-08-02", amount=200)
    preview = db.get_worker_wage_account(1, gross=5000, wage_date="2026-08-31")
    assert preview == {"default_wage": 5000, "gross": 5000, "outstanding_advances": 500,
                       "outstanding_deductions": 200, "net_payable": 4300}
    assert db.create_wage_movement(worker_id=1, movement_type="wage_payment",
        date="2026-08-31", amount=5000)["net_payable"] == preview["net_payable"]


def test_specific_month_is_not_applied_early_then_carries_forward(wages):
    movement = db.create_wage_movement(worker_id=1, movement_type="advance",
        date="2026-09-01", amount=6000, apply_to_month="2026-10")
    assert db.create_wage_movement(worker_id=1, movement_type="wage_payment",
        date="2026-09-30", amount=5000)["net_payable"] == 5000
    assert db.create_wage_movement(worker_id=1, movement_type="wage_payment",
        date="2026-10-31", amount=5000)["net_payable"] == 0
    assert wages.execute("SELECT remaining_amount FROM jw_purchases WHERE id=?", (movement["id"],)).fetchone()[0] == 1000
    assert db.create_wage_movement(worker_id=1, movement_type="wage_payment",
        date="2026-11-30", amount=5000)["net_payable"] == 4000


def test_worker_wage_labels_are_single_language():
    keys = ["purchases.worker_information", "purchases.worker_account", "purchases.movement_type",
            "purchases.add_advance", "purchases.add_deduction", "purchases.pay_wage",
            "purchases.delete_movement", "purchases.apply_to_wage", "purchases.specific_month"]
    assert all(not any('\u0600' <= char <= '\u06ff' for char in t(key, language="en")) for key in keys)
    assert all(any('\u0600' <= char <= '\u06ff' for char in t(key, language="ar")) for key in keys)
    assert all(" / " not in t(key, language=language) for key in keys for language in ("en", "ar"))
