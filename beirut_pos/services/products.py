"""Product helpers that operate directly on SQLite rows."""

from typing import Iterator, Optional, Sequence, Tuple

from ..core.db import get_conn


ProductRow = Tuple[int, str, int, int, Optional[float], Optional[float]]


def iter_products(search: str = "") -> Iterator[ProductRow]:
    """Stream products to keep memory usage low for large catalogs."""

    conn = get_conn()
    cur = conn.cursor()
    query = (
        "SELECT id, name, price_cents, track_stock, stock_qty, min_stock "
        "FROM products "
    )
    params: Tuple[str, ...] = ()
    if search:
        query += "WHERE name LIKE ? "
        params = (f"%{search}%",)
    query += "ORDER BY name ASC"

    try:
        iterable = cur.execute(query, params) if params else cur.execute(query)
        for row in iterable:
            yield (
                row["id"],
                row["name"],
                int(row["price_cents"]),
                int(row["track_stock"]),
                row["stock_qty"],
                row["min_stock"],
            )
    finally:
        conn.close()


def list_products(search: str = "") -> Sequence[ProductRow]:
    """Return a materialised list for existing callers."""

    return tuple(iter_products(search))


def get_product(pid: int):
    conn = get_conn()
    row = conn.execute(
        """
        SELECT id, name, price_cents, track_stock, stock_qty, min_stock
        FROM products WHERE id=?
    """,
        (pid,),
    ).fetchone()
    conn.close()
    return row


def update_stock(pid: int, delta: float) -> Optional[float]:
    """Adjust stock by *delta* and return the new quantity."""

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE products SET stock_qty = COALESCE(stock_qty,0) + ? WHERE id=?",
        (delta, pid),
    )
    if cur.rowcount != 1:
        conn.close()
        raise RuntimeError("Failed to update stock (product not found?)")
    cur.execute("SELECT stock_qty FROM products WHERE id=?", (pid,))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    return None if row is None else row["stock_qty"]
