"""Product helpers and catalog wrappers for external callers."""

from typing import Iterator, Optional, Sequence, Tuple

from ..core.db import get_conn
from .orders import order_manager


ProductRow = Tuple[int, str, int, int, int, Optional[float], Optional[float]]
OptionRow = Tuple[int, int, str, int, int]


def iter_products(search: str = "") -> Iterator[ProductRow]:
    """Stream products to keep memory usage low for large catalogs."""

    conn = get_conn()
    cur = conn.cursor()
    query = (
        "SELECT id, name, price_cents, customizable, track_stock, stock_qty, min_stock "
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
                int(row["customizable"]),
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
        SELECT id, name, price_cents, customizable, track_stock, stock_qty, min_stock
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


# ---- high-level catalog wrappers (delegating to OrderManager) -----------------


def list_categories() -> list[dict]:
    return order_manager.catalog.list_categories()


def create_category(name: str, username: str = "admin") -> dict:
    return order_manager.catalog.create_category(name, username=username)


def rename_category(category_id: int, new_name: str, username: str = "admin") -> bool:
    return order_manager.catalog.rename_category(category_id, new_name, username=username)


def delete_category(category_id: int, username: str = "admin") -> bool:
    return order_manager.catalog.delete_category(category_id, username=username)


def reorder_categories(order: list[int]) -> None:
    order_manager.catalog.reorder_categories(order)


def list_products_for_category(category_id: int) -> list[dict]:
    return order_manager.catalog.list_products(category_id)


def create_product(
    category_id: int,
    name: str,
    price_cents: int,
    *,
    username: str = "admin",
    customizable: int = 0,
    track_stock: int = 0,
    stock_qty: Optional[float] = 0,
    min_stock: Optional[float] = 0,
) -> dict:
    return order_manager.catalog.create_product(
        category_id,
        name,
        price_cents,
        username=username,
        customizable=customizable,
        track_stock=track_stock,
        stock_qty=stock_qty,
        min_stock=min_stock,
    )


def update_product(
    product_id: int,
    *,
    name: str | None = None,
    price_cents: int | None = None,
    customizable: int | None = None,
    track_stock: int | None = None,
    stock_qty: Optional[float] | None = None,
    min_stock: Optional[float] | None = None,
    username: str = "admin",
) -> bool:
    return order_manager.catalog.update_product(
        product_id,
        name=name,
        price_cents=price_cents,
        customizable=customizable,
        track_stock=track_stock,
        stock_qty=stock_qty,
        min_stock=min_stock,
        username=username,
    )


def delete_product(product_id: int, username: str = "admin") -> bool:
    return order_manager.catalog.delete_product(product_id, username=username)


def reorder_products(category_id: int, ordered_ids: list[int]) -> None:
    order_manager.catalog.reorder_products(category_id, ordered_ids)


def list_options(product_id: int) -> list[dict]:
    return order_manager.catalog.list_options(product_id)


def create_option(product_id: int, label: str, price_delta_cents: int, username: str = "admin") -> dict:
    return order_manager.catalog.create_option(
        product_id,
        label,
        price_delta_cents,
        username=username,
    )


def update_option(option_id: int, label: str, price_delta_cents: int, username: str = "admin") -> bool:
    return order_manager.catalog.update_option(
        option_id,
        label=label,
        price_delta_cents=price_delta_cents,
        username=username,
    )


def delete_option(option_id: int, username: str = "admin") -> bool:
    return order_manager.catalog.delete_option(option_id, username=username)


def reorder_options(product_id: int, ordered_ids: list[int]) -> None:
    order_manager.catalog.reorder_options(product_id, ordered_ids)
