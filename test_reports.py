import importlib
import sys


def _reload_modules(monkeypatch, data_dir):
    monkeypatch.setenv("BEIRUTPOS_DATA_DIR", str(data_dir))

    existing_db = sys.modules.get("beirut_pos.core.db")
    if existing_db:
        try:
            existing_db.close_engine()
        except Exception:
            pass

    for mod in (
        "beirut_pos.core.paths",
        "beirut_pos.core.db",
        "beirut_pos.services.reports",
    ):
        sys.modules.pop(mod, None)

    import beirut_pos.core.db as db
    import beirut_pos.services.reports as reports

    importlib.reload(db)
    importlib.reload(reports)

    return db, reports


def test_z_report_uses_paid_at_bounds(tmp_path, monkeypatch):
    db, reports = _reload_modules(monkeypatch, tmp_path / "beirut_data")

    db.safe_migrations()
    conn = db.get_conn()
    cur = conn.cursor()

    cur.executescript(
        """
        DELETE FROM payments;
        DELETE FROM order_items;
        DELETE FROM orders;
        """
    )

    cur.execute(
        """
        INSERT INTO orders (id, table_code, opened_at, closed_at, status, opened_by, closed_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            1,
            "A1",
            "2024-01-01T20:00:00",
            "2024-01-01T22:00:00",
            "paid",
            "alice",
            "alice",
        ),
    )
    cur.execute(
        """
        INSERT INTO orders (id, table_code, opened_at, closed_at, status, opened_by, closed_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            2,
            "B2",
            "2024-01-01T21:00:00",
            "2024-01-02T00:30:00",
            "paid",
            "bob",
            "bob",
        ),
    )

    cur.execute(
        """
        INSERT INTO order_items (order_id, product_name, price_cents, qty, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (1, "PS Latte", 1500, 1, ""),
    )
    cur.execute(
        """
        INSERT INTO order_items (order_id, product_name, price_cents, qty, note)
        VALUES (?, ?, ?, ?, ?)
        """,
        (2, "Americano", 2000, 1, ""),
    )

    cur.execute(
        """
        INSERT INTO payments (order_id, method, amount_cents, paid_at, cashier)
        VALUES (?, ?, ?, ?, ?)
        """,
        (1, "cash", 1400, "2024-01-02T01:00:00", "alice"),
    )
    cur.execute(
        """
        INSERT INTO payments (order_id, method, amount_cents, paid_at, cashier)
        VALUES (?, ?, ?, ?, ?)
        """,
        (2, "card", 2000, "2024-01-01T23:00:00", "bob"),
    )

    conn.commit()
    report = reports.z_report("2024-01-02")

    assert report["orders_count"] == 1
    assert report["total_cents"] == 1400
    assert report["discount_cents"] == 100
    assert report["ps_items_count"] == 1
    assert dict(report["by_method"]) == {"cash": 1400}

    conn.close()
    db.close_engine()
