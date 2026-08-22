import sqlite3
import sys
import types


fake_core_db = types.ModuleType("beirut_pos.core.db")
fake_core_db.get_conn = lambda: None
sys.modules.setdefault("beirut_pos.core.db", fake_core_db)

from beirut_pos.apps.jewelry.services import db
from beirut_pos.apps.jewelry.services import auth


def test_legacy_bom_cost_columns_migrate_with_zero_defaults(tmp_path, monkeypatch):
    path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE jw_boms(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            INSERT INTO jw_boms(product_id, name, active)
            VALUES (42, 'Legacy design', 1);
            """
        )
    monkeypatch.setattr(db, "get_conn", lambda: sqlite3.connect(path))
    monkeypatch.setattr(auth, "get_conn", lambda: sqlite3.connect(path))

    db.init_jewelry_db()

    with sqlite3.connect(path) as conn:
        columns = {row[1]: row for row in conn.execute("PRAGMA table_info(jw_boms)")}
        costs = conn.execute(
            "SELECT labor_cost, packaging_cost, other_cost FROM jw_boms"
        ).fetchone()
    assert columns["labor_cost"][4] == "0"
    assert columns["packaging_cost"][4] == "0"
    assert columns["other_cost"][4] == "0"
    assert costs == (0.0, 0.0, 0.0)
    assert db.list_boms()[0].labor_cost == 0.0
