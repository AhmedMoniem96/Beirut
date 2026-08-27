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


class _OpenConnection:
    def __init__(self, connection):
        self.connection = connection

    def __getattr__(self, name):
        if name == "close":
            return lambda: None
        return getattr(self.connection, name)


@pytest.fixture
def wage_db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
        CREATE TABLE jw_workers(id INTEGER PRIMARY KEY, name TEXT, phone TEXT, role TEXT,
          default_wage REAL, wage_type TEXT, notes TEXT, active INTEGER);
        INSERT INTO jw_workers VALUES (1, 'Worker', '', '', 3000, 'monthly', '', 1);
        CREATE TABLE jw_purchases(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, category TEXT,
          vendor TEXT, description TEXT, amount REAL, payment_method TEXT, notes TEXT,
          linked_material_id INTEGER, material_qty REAL, worker_id INTEGER, wage_period TEXT,
          created_at TEXT, movement_type TEXT DEFAULT 'wage_payment',
          applied_amount REAL DEFAULT 0, remaining_amount REAL DEFAULT 0, gross_amount REAL DEFAULT 0);
        ALTER TABLE jw_purchases ADD COLUMN apply_to_month TEXT;
    """)
    monkeypatch.setattr(db, "get_conn", lambda: _OpenConnection(conn))
    return conn


@pytest.mark.parametrize("movement_type", ["advance", "deduction"])
def test_delete_unapplied_movement_removes_outstanding_balance(wage_db, movement_type):
    movement = db.create_wage_movement(
        worker_id=1, movement_type=movement_type, date="2026-08-01", amount=50000
    )
    assert wage_db.execute(
        "SELECT SUM(remaining_amount) FROM jw_purchases WHERE worker_id=1"
    ).fetchone()[0] == 50000

    db.delete_wage_movement(movement["id"])

    assert wage_db.execute(
        "SELECT COUNT(*) FROM jw_purchases WHERE id=?", (movement["id"],)
    ).fetchone()[0] == 0
    assert wage_db.execute(
        "SELECT COALESCE(SUM(remaining_amount), 0) FROM jw_purchases WHERE worker_id=1"
    ).fetchone()[0] == 0


def test_delete_applied_movement_is_blocked(wage_db):
    movement = db.create_wage_movement(
        worker_id=1, movement_type="advance", date="2026-08-01", amount=500
    )
    db.create_wage_movement(
        worker_id=1, movement_type="wage_payment", date="2026-08-31", amount=3000
    )

    with pytest.raises(ValueError, match="already affected a wage payment"):
        db.delete_wage_movement(movement["id"])

    assert wage_db.execute(
        "SELECT applied_amount FROM jw_purchases WHERE id=?", (movement["id"],)
    ).fetchone()[0] == 500
