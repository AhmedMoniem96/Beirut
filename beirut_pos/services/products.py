from typing import Optional, Sequence
from ..core.db import get_conn

def list_products(search: str = "") -> Sequence:
    conn = get_conn()
    cur = conn.cursor()
    if search:
        rows = cur.execute("""
            SELECT id, name, price_cents, track_stock, stock
            FROM products
            WHERE name LIKE ?
            ORDER BY name ASC
        """, (f"%{search}%",)).fetchall()
    else:
        rows = cur.execute("""
            SELECT id, name, price_cents, track_stock, stock
            FROM products
            ORDER BY name ASC
        """).fetchall()
    conn.close()
    return rows

def get_product(pid: int):
    conn = get_conn()
    row = conn.execute("""
        SELECT id, name, price_cents, track_stock, stock
        FROM products WHERE id=?
    """, (pid,)).fetchone()
    conn.close()
    return row

def update_stock(pid: int, delta: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE products SET stock = COALESCE(stock,0) + ? WHERE id=?", (delta, pid))
    if cur.rowcount != 1:
        conn.close()
        raise RuntimeError("Failed to update stock (product not found?)")
    conn.commit()
    conn.close()
