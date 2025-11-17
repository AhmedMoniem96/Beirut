"""Order lifecycle management, stock enforcement, and PS session handling."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple, Optional
import math  # ADD THIS IMPORT


from ..core.bus import bus
from ..core.db import (
    db_transaction,
    get_conn,
    init_db,
    log_action,
    setting_get,
    setting_set,
)
from ..texts import texts
import logging

# Add this after imports, before init_db()
logger = logging.getLogger(__name__)
init_db()

EDIT_WINDOW_SECONDS = 300
ALLOW_LATE_EDIT_OVERRIDE = os.getenv("ALLOW_ADMIN_EDIT_AFTER_WINDOW", "0") == "1"

class OrderError(Exception):
    """Base exception for order-related errors"""
    pass

class StockError(OrderError):
    """Raised when stock is insufficient"""
    pass

class MergeError(OrderError):
    """Raised when merge operations fail"""
    pass

class MoveError(OrderError):
    """Raised when move operations fail"""
    pass


class EditWindowError(OrderError):
    """Raised when attempting to edit outside the allowed window."""

    def __init__(self, message: str | None = None):
        super().__init__(message or texts.get("orders.edit_locked"))

# --- ONE-TIME migration to add inventory columns if missing ----------------
def _ensure_inventory_columns():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(products)")
    cols = {r[1] for r in cur.fetchall()}

    if "stock_qty" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN stock_qty REAL DEFAULT 0")
    if "min_stock" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN min_stock REAL DEFAULT 0")
    if "track_stock" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN track_stock INTEGER NOT NULL DEFAULT 1")
    if "package_size" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN package_size REAL NOT NULL DEFAULT 1")

    conn.commit()
    conn.close()

_ensure_inventory_columns()


def _ensure_order_item_notes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(order_items)")
    cols = {r[1] for r in cur.fetchall()}
    if "note" not in cols:
        cur.execute("ALTER TABLE order_items ADD COLUMN note TEXT DEFAULT ''")
    conn.commit()
    conn.close()

def _ensure_order_item_printed_qty():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(order_items)")
    cols = {r[1] for r in cur.fetchall()}
    if "printed_qty" not in cols:
        cur.execute("ALTER TABLE order_items ADD COLUMN printed_qty REAL NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()

_ensure_order_item_printed_qty()
_ensure_order_item_notes()

_TABLE_CODES_KEY = "table_codes"
# ---------------------------------------------------------------------------


def _deserialize_sugar_levels(raw) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        if isinstance(raw, str):
            return [part.strip() for part in raw.split(",") if part.strip()]
        return []
    if isinstance(data, list):
        return [str(item).strip() for item in data if str(item).strip()]
    return []


def _serialize_sugar_levels(levels: list[str]) -> str:
    cleaned = [str(item).strip() for item in levels if str(item).strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def get_category_order() -> list[str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories ORDER BY order_index, id")
    rows = [row["name"] for row in cur.fetchall()]
    conn.close()
    return rows


def set_category_order(order: list[str]) -> None:
    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM categories ORDER BY order_index, id")
        existing = cur.fetchall()
        id_by_name = {row["name"]: row["id"] for row in existing}
        cleaned: list[int] = []
        for name in order:
            cid = id_by_name.get(name)
            if cid is not None and cid not in cleaned:
                cleaned.append(cid)
        for row in existing:
            if row["id"] not in cleaned:
                cleaned.append(row["id"])
        for idx, cid in enumerate(cleaned):
            cur.execute("UPDATE categories SET order_index=? WHERE id=?", (idx, cid))
    bus.emit("catalog_changed")
# ---------------------------------------------------------------------------


def _default_table_codes() -> list[str]:
    return [f"T{i:02d}" for i in range(1, 31)]


def _normalize_table_codes(codes: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for code in codes:
        if not isinstance(code, str):
            continue
        norm = code.strip().upper()
        if not norm or norm in seen:
            continue
        cleaned.append(norm)
        seen.add(norm)
    return cleaned


def _load_table_codes() -> list[str]:
    raw = setting_get(_TABLE_CODES_KEY, "")
    if not raw:
        return _default_table_codes()
    try:
        data = json.loads(raw)
    except Exception:
        return _default_table_codes()
    if not isinstance(data, list):
        return _default_table_codes()
    cleaned = _normalize_table_codes(data)
    return cleaned or _default_table_codes()


def _store_table_codes(codes: list[str]) -> None:
    cleaned = _normalize_table_codes(codes)
    if not cleaned:
        cleaned = _default_table_codes()
    setting_set(_TABLE_CODES_KEY, json.dumps(cleaned, ensure_ascii=False))
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------


StockState = Tuple[Optional[float], Optional[float]]


class ProductCatalog:
    __slots__ = ()

    def categories(self) -> List[Tuple[str, List[Tuple[str, int, int, Optional[float]]]]]:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM categories ORDER BY order_index, id")
        cat_rows = cur.fetchall()
        out: List[Tuple[str, List[Tuple[str, int, int, Optional[float]]]]] = []
        for cat in cat_rows:
            cur.execute(
                """SELECT name, price_cents, track_stock, stock_qty
                       FROM products
                       WHERE category_id=?
                       ORDER BY order_index, id""",
                (cat["id"],),
            )
            items = [
                (row["name"], int(row["price_cents"]), int(row["track_stock"]), row["stock_qty"])
                for row in cur.fetchall()
            ]
            out.append((cat["name"], items))
        conn.close()
        return out

    def list_categories(self) -> list[dict]:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, name, order_index FROM categories ORDER BY order_index, id")
        rows = [
            {
                "id": row["id"],
                "name": row["name"],
                "order_index": int(row["order_index"] or 0),
            }
            for row in cur.fetchall()
        ]
        conn.close()
        return rows

    def list_products(self, category_id: int) -> list[dict]:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, name, price_cents, customizable, track_stock, stock_qty, min_stock, package_size, order_index, product_type, sugar_levels
                   FROM products
                   WHERE category_id=?
                   ORDER BY order_index, id""",
            (category_id,),
        )
        rows: list[dict] = []
        for row in cur.fetchall():
            keys = row.keys()
            rows.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "price_cents": int(row["price_cents"]),
                    "customizable": int(row["customizable"]),
                    "track_stock": int(row["track_stock"]),
                    "stock_qty": row["stock_qty"],
                    "min_stock": row["min_stock"],
                    "package_size": row["package_size"] if "package_size" in keys else 1,
                    "order_index": int(row["order_index"] or 0),
                    "product_type": row["product_type"] if "product_type" in keys else "",
                    "sugar_levels": _deserialize_sugar_levels(row["sugar_levels"] if "sugar_levels" in keys else ""),
                }
            )
        conn.close()
        return rows

    def list_options(self, product_id: int) -> list[dict]:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, label, price_delta_cents, order_index
                   FROM product_options
                   WHERE product_id=?
                   ORDER BY order_index, id""",
            (product_id,),
        )
        options = [
            {
                "id": row["id"],
                "label": row["label"],
                "price_delta_cents": int(row["price_delta_cents"]),
                "order_index": int(row["order_index"] or 0),
            }
            for row in cur.fetchall()
        ]
        conn.close()
        return options

    def create_category(self, name: str, *, username: str = "admin") -> dict:
        cleaned = (name or "").strip()
        if not cleaned:
            raise ValueError("اسم القسم مطلوب")
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM categories WHERE name=?", (cleaned,))
            if cur.fetchone():
                raise ValueError("القسم موجود بالفعل")
            cur.execute("SELECT COALESCE(MAX(order_index), -1) FROM categories")
            max_row = cur.fetchone()
            next_idx = int(max_row[0]) + 1 if max_row and max_row[0] is not None else 0
            cur.execute(
                "INSERT INTO categories(name, order_index) VALUES(?, ?)",
                (cleaned, next_idx),
            )
            category_id = cur.lastrowid
        log_action(username, "add_category", "category", cleaned, None, None)
        bus.emit("catalog_changed")
        return {"id": category_id, "name": cleaned, "order_index": next_idx}

    def add_category(self, name: str, *, username: str = "admin") -> None:
        try:
            self.create_category(name, username=username)
        except ValueError:
            pass

    def rename_category(self, category_id: int, new_name: str, *, username: str = "admin") -> bool:
        cleaned = (new_name or "").strip()
        if not cleaned:
            raise ValueError("اسم القسم مطلوب")
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM categories WHERE id=?", (category_id,))
            row = cur.fetchone()
            if not row:
                return False
            old_name = row["name"]
            if old_name == cleaned:
                return True
            cur.execute(
                "SELECT 1 FROM categories WHERE name=? AND id<>?",
                (cleaned, category_id),
            )
            if cur.fetchone():
                raise ValueError("القسم موجود بالفعل")
            cur.execute("UPDATE categories SET name=? WHERE id=?", (cleaned, category_id))
        log_action(username, "rename_category", "category", old_name, old_name, cleaned)
        bus.emit("catalog_changed")
        return True

    def delete_category(self, category_id: int, *, username: str = "admin") -> bool:
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM categories WHERE id=?", (category_id,))
            row = cur.fetchone()
            if not row:
                return False
            name = row["name"]
            cur.execute("DELETE FROM products WHERE category_id=?", (category_id,))
            cur.execute("DELETE FROM categories WHERE id=?", (category_id,))
            cur.execute("SELECT id FROM categories ORDER BY order_index, id")
            remaining = [r["id"] for r in cur.fetchall()]
            for idx, cid in enumerate(remaining):
                cur.execute("UPDATE products SET order_index=? WHERE id=?", (idx, cid))
        log_action(
            username,
            "delete_category",
            "category",
            name,
            name,
            None,
        )
        bus.emit("catalog_changed")
        return True

    def reorder_categories(self, ordered_ids: list[int]) -> None:
        if not ordered_ids:
            return
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM categories ORDER BY order_index, id")
            current = [row["id"] for row in cur.fetchall()]
            allowed = set(current)
            cleaned = [cid for cid in ordered_ids if cid in allowed]
            for cid in current:
                if cid not in cleaned:
                    cleaned.append(cid)
            for idx, cid in enumerate(cleaned):
                cur.execute("UPDATE categories SET order_index=? WHERE id=?", (idx, cid))
        bus.emit("catalog_changed")

    def create_product(
        self,
        category_id: int,
        name: str,
        price_cents: int,
        *,
        username: str = "admin",
        customizable: int = 0,
        track_stock: int = 0,
        stock_qty: Optional[float] = 0,
        min_stock: Optional[float] = 0,
        package_size: Optional[float] = 1,
        product_type: str = "",
        sugar_levels: Optional[list[str]] = None,
    ) -> dict:
        cleaned = (name or "").strip()
        if not cleaned:
            raise ValueError("اسم المنتج مطلوب")
        if price_cents <= 0:
            raise ValueError("السعر غير صالح")
        product_type = (product_type or "").strip()
        sugar_levels = sugar_levels or []
        track = 1 if track_stock else 0
        custom_flag = 1 if customizable else 0
        qty_value = float(stock_qty) if stock_qty is not None else 0.0
        min_value = float(min_stock) if min_stock is not None else 0.0
        pkg_value = float(package_size) if package_size not in (None, 0) else 1.0
        if pkg_value <= 0:
            pkg_value = 1.0
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM categories WHERE id=?", (category_id,))
            cat_row = cur.fetchone()
            if not cat_row:
                raise ValueError("القسم غير موجود")
            category_name = cat_row["name"]
            cur.execute(
                "SELECT 1 FROM products WHERE category_id=? AND name=?",
                (category_id, cleaned),
            )
            if cur.fetchone():
                raise ValueError("المنتج موجود بالفعل")
            cur.execute(
                "SELECT COALESCE(MAX(order_index), -1) FROM products WHERE category_id=?",
                (category_id,),
            )
            max_row = cur.fetchone()
            next_idx = int(max_row[0]) + 1 if max_row and max_row[0] is not None else 0
            qty_sql = qty_value if track else None
            min_sql = min_value if track else 0.0
            cur.execute(
                """INSERT INTO products(category_id,name,price_cents,customizable,track_stock,stock_qty,min_stock,package_size,product_type,sugar_levels,order_index)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    category_id,
                    cleaned,
                    price_cents,
                    custom_flag,
                    track,
                    qty_sql,
                    min_sql,
                    pkg_value,
                    product_type,
                    _serialize_sugar_levels(sugar_levels),
                    next_idx,
                ),
            )
            product_id = cur.lastrowid
        log_action(
            username,
            "add_product",
            "product",
            f"{category_name}/{cleaned}",
            None,
            str(price_cents),
        )
        bus.emit("catalog_changed")
        return {
            "id": product_id,
            "category_id": category_id,
            "name": cleaned,
            "price_cents": price_cents,
            "customizable": custom_flag,
            "track_stock": track,
            "stock_qty": qty_sql,
            "min_stock": min_sql,
            "package_size": pkg_value,
            "product_type": product_type,
            "sugar_levels": list(sugar_levels),
            "order_index": next_idx,
        }

    def add_product(
        self,
        category: str,
        label: str,
        price_cents: int,
        username: str = "admin",
        *,
        customizable: int = 0,
        track_stock: int = 0,
        stock_qty: Optional[float] = 0,
        min_stock: Optional[float] = 0,
        package_size: Optional[float] = 1,
        product_type: str = "",
        sugar_levels: Optional[list[str]] = None,
    ) -> None:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE name=?", (category,))
        row = cur.fetchone()
        conn.close()
        if row is None:
            created = self.create_category(category, username=username)
            category_id = created["id"]
        else:
            category_id = row["id"]
        self.create_product(
            category_id,
            label,
            price_cents,
            username=username,
            customizable=customizable,
            track_stock=track_stock,
            stock_qty=stock_qty,
            min_stock=min_stock,
            package_size=package_size,
            product_type=product_type,
            sugar_levels=sugar_levels,
        )

    def update_product(
        self,
        product_id: int,
        *,
        name: str | None = None,
        price_cents: int | None = None,
        customizable: int | None = None,
        track_stock: int | None = None,
        stock_qty: Optional[float] | None = None,
        min_stock: Optional[float] | None = None,
        package_size: Optional[float] | None = None,
        product_type: str | None = None,
        sugar_levels: Optional[list[str]] | None = None,
        username: str = "admin",
    ) -> bool:
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT name, price_cents, customizable, track_stock, stock_qty, min_stock, package_size, category_id, product_type, sugar_levels
                       FROM products WHERE id=?""",
                (product_id,),
            )
            row = cur.fetchone()
            if not row:
                return False
            old_name = row["name"]
            old_price = int(row["price_cents"])
            old_custom = int(row["customizable"])
            category_id = row["category_id"]
            old_package_size = float(row["package_size"] or 1.0)
            old_type = row["product_type"] if "product_type" in row.keys() else ""
            old_sugar = _deserialize_sugar_levels(row["sugar_levels"] if "sugar_levels" in row.keys() else "")
            cur.execute("SELECT name FROM categories WHERE id=?", (category_id,))
            cat_row = cur.fetchone()
            category_name = cat_row["name"] if cat_row else ""
            new_name = (name.strip() if isinstance(name, str) else old_name)
            if not new_name:
                raise ValueError("اسم المنتج مطلوب")
            new_price = old_price if price_cents is None else int(price_cents)
            new_custom = old_custom if customizable is None else int(customizable)
            if new_custom not in (0, 1):
                new_custom = old_custom
            new_track = int(row["track_stock"]) if track_stock is None else int(track_stock)
            if new_track not in (0, 1):
                new_track = int(row["track_stock"])
            new_type = old_type if product_type is None else (product_type or "").strip()
            new_sugar_levels = old_sugar if sugar_levels is None else [s.strip() for s in sugar_levels if s.strip()]
            qty_value = row["stock_qty"]
            min_value = row["min_stock"]
            if stock_qty is not None:
                qty_value = float(stock_qty)
            if min_stock is not None:
                min_value = float(min_stock)
            pkg_value = old_package_size
            if package_size is not None:
                pkg_value = float(package_size)
            if pkg_value <= 0:
                pkg_value = 1.0
            qty_sql = qty_value if new_track else None
            min_sql = min_value if new_track else 0.0
            cur.execute(
                """UPDATE products
                       SET name=?, price_cents=?, customizable=?, track_stock=?, stock_qty=?, min_stock=?, package_size=?, product_type=?, sugar_levels=?
                       WHERE id=?""",
                (
                    new_name,
                    new_price,
                    new_custom,
                    new_track,
                    qty_sql,
                    min_sql,
                    pkg_value,
                    new_type,
                    _serialize_sugar_levels(new_sugar_levels),
                    product_id,
                ),
            )
            if new_custom == 0:
                cur.execute("DELETE FROM product_options WHERE product_id=?", (product_id,))
        if (
            old_name != new_name
            or old_price != new_price
            or old_custom != new_custom
            or old_package_size != pkg_value
            or old_type != new_type
            or old_sugar != new_sugar_levels
        ):
            log_action(
                username,
                "update_product",
                "product",
                f"{category_name}/{old_name}" if category_name else old_name,
                f"{old_name}:{old_price}:{old_custom}:{old_package_size}:{old_type}:{'|'.join(old_sugar)}",
                f"{new_name}:{new_price}:{new_custom}:{pkg_value}:{new_type}:{'|'.join(new_sugar_levels)}",
            )
        bus.emit("catalog_changed")
        return True

    def update_product_price(self, category: str, label: str, new_price_cents: int, username: str) -> bool:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT p.id FROM products p
                   JOIN categories c ON c.id=p.category_id
                   WHERE c.name=? AND p.name=?""",
            (category, label),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return False
        return self.update_product(row["id"], price_cents=new_price_cents, username=username)

    def delete_product(self, product_id: int, *, username: str = "admin") -> bool:
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT name, category_id FROM products WHERE id=?", (product_id,))
            row = cur.fetchone()
            if not row:
                return False
            product_name = row["name"]
            category_id = row["category_id"]
            cur.execute("SELECT name FROM categories WHERE id=?", (category_id,))
            cat_row = cur.fetchone()
            category_name = cat_row["name"] if cat_row else ""
            cur.execute("DELETE FROM products WHERE id=?", (product_id,))
            cur.execute(
                "SELECT id FROM products WHERE category_id=? ORDER BY order_index, id",
                (category_id,),
            )
            remaining = [r["id"] for r in cur.fetchall()]
            for idx, pid in enumerate(remaining):
                cur.execute("UPDATE products SET order_index=? WHERE id=?", (idx, pid))
        log_action(
            username,
            "delete_product",
            "product",
            f"{category_name}/{product_name}",
            product_name,
            None,
        )
        bus.emit("catalog_changed")
        return True

    def reorder_products(self, category_id: int, ordered_ids: list[int]) -> None:
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM products WHERE category_id=? ORDER BY order_index, id",
                (category_id,),
            )
            current = [row["id"] for row in cur.fetchall()]
            allowed = set(current)
            cleaned = [pid for pid in ordered_ids if pid in allowed]
            for pid in current:
                if pid not in cleaned:
                    cleaned.append(pid)
            for idx, pid in enumerate(cleaned):
                cur.execute("UPDATE products SET order_index=? WHERE id=?", (idx, pid))
        bus.emit("catalog_changed")

    def reorder_options(self, product_id: int, ordered_ids: list[int]) -> None:
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id FROM product_options WHERE product_id=? ORDER BY order_index, id",
                (product_id,),
            )
            current = [row["id"] for row in cur.fetchall()]
            allowed = set(current)
            cleaned = [oid for oid in ordered_ids if oid in allowed]
            for oid in current:
                if oid not in cleaned:
                    cleaned.append(oid)
            for idx, oid in enumerate(cleaned):
                cur.execute("UPDATE product_options SET order_index=? WHERE id=?", (idx, oid))
        bus.emit("catalog_changed")

    def create_option(
        self,
        product_id: int,
        label: str,
        price_delta_cents: int,
        *,
        username: str = "admin",
    ) -> dict:
        cleaned = (label or "").strip()
        if not cleaned:
            raise ValueError("اسم الخيار مطلوب")
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT p.name, c.name as category FROM products p JOIN categories c ON c.id=p.category_id WHERE p.id=?",
                (product_id,),
            )
            prod_row = cur.fetchone()
            if not prod_row:
                raise ValueError("المنتج غير موجود")
            cur.execute(
                "SELECT 1 FROM product_options WHERE product_id=? AND label=?",
                (product_id, cleaned),
            )
            if cur.fetchone():
                raise ValueError("الخيار موجود بالفعل")
            cur.execute(
                "SELECT COALESCE(MAX(order_index), -1) FROM product_options WHERE product_id=?",
                (product_id,),
            )
            max_row = cur.fetchone()
            next_idx = int(max_row[0]) + 1 if max_row and max_row[0] is not None else 0
            cur.execute(
                """INSERT INTO product_options(product_id,label,price_delta_cents,order_index)
                       VALUES(?,?,?,?)""",
                (product_id, cleaned, int(price_delta_cents), next_idx),
            )
            option_id = cur.lastrowid
        log_action(
            username,
            "add_option",
            "product_option",
            f"{prod_row['category']}/{prod_row['name']}",
            None,
            f"{cleaned}:{price_delta_cents}",
        )
        bus.emit("catalog_changed")
        return {
            "id": option_id,
            "label": cleaned,
            "price_delta_cents": int(price_delta_cents),
            "order_index": next_idx,
        }

    def update_option(
        self,
        option_id: int,
        *,
        label: str,
        price_delta_cents: int,
        username: str = "admin",
    ) -> bool:
        cleaned = (label or "").strip()
        if not cleaned:
            raise ValueError("اسم الخيار مطلوب")
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT o.product_id, o.label, o.price_delta_cents, p.name, c.name as category
                       FROM product_options o
                       JOIN products p ON p.id=o.product_id
                       JOIN categories c ON c.id=p.category_id
                       WHERE o.id=?""",
                (option_id,),
            )
            row = cur.fetchone()
            if not row:
                return False
            cur.execute(
                "SELECT 1 FROM product_options WHERE product_id=? AND label=? AND id<>?",
                (row["product_id"], cleaned, option_id),
            )
            if cur.fetchone():
                raise ValueError("الخيار موجود بالفعل")
            cur.execute(
                "UPDATE product_options SET label=?, price_delta_cents=? WHERE id=?",
                (cleaned, int(price_delta_cents), option_id),
            )
        log_action(
            username,
            "update_option",
            "product_option",
            f"{row['category']}/{row['name']}",
            f"{row['label']}:{row['price_delta_cents']}",
            f"{cleaned}:{price_delta_cents}",
        )
        bus.emit("catalog_changed")
        return True

    def delete_option(self, option_id: int, *, username: str = "admin") -> bool:
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                """SELECT o.product_id, o.label, p.name, c.name as category
                       FROM product_options o
                       JOIN products p ON p.id=o.product_id
                       JOIN categories c ON c.id=p.category_id
                       WHERE o.id=?""",
                (option_id,),
            )
            row = cur.fetchone()
            if not row:
                return False
            product_id = row["product_id"]
            cur.execute("DELETE FROM product_options WHERE id=?", (option_id,))
            cur.execute(
                "SELECT id FROM product_options WHERE product_id=? ORDER BY order_index, id",
                (product_id,),
            )
            remaining = [r["id"] for r in cur.fetchall()]
            for idx, oid in enumerate(remaining):
                cur.execute("UPDATE product_options SET order_index=? WHERE id=?", (idx, oid))
        log_action(
            username,
            "delete_option",
            "product_option",
            f"{row['category']}/{row['name']}",
            row["label"],
            None,
        )
        bus.emit("catalog_changed")
        return True

    def get_product(self, name: str) -> Optional[dict]:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT p.id, p.name, p.price_cents, p.customizable, p.track_stock, p.stock_qty, p.min_stock, p.order_index,
                       p.product_type, p.sugar_levels, c.name as category
                   FROM products p
                   JOIN categories c ON c.id = p.category_id
                   WHERE p.name=?""",
            (name,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row["id"],
            "name": row["name"],
            "price_cents": int(row["price_cents"]),
            "customizable": int(row["customizable"]),
            "track_stock": int(row["track_stock"]),
            "stock_qty": row["stock_qty"],
            "min_stock": row["min_stock"],
            "order_index": int(row["order_index"] or 0),
            "category": row["category"],
            "product_type": row["product_type"] if "product_type" in row.keys() else "",
            "sugar_levels": _deserialize_sugar_levels(row["sugar_levels"] if "sugar_levels" in row.keys() else ""),
        }

    def get_product_with_options(self, name: str) -> Optional[dict]:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT p.id, p.name, p.price_cents, p.customizable, p.track_stock, p.stock_qty, p.min_stock,
                       p.product_type, p.sugar_levels, c.name as category
                   FROM products p
                   JOIN categories c ON c.id=p.category_id
                   WHERE p.name=?""",
            (name,),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return None
        cur.execute(
            "SELECT id, label, price_delta_cents, order_index FROM product_options WHERE product_id=? ORDER BY order_index, id",
            (row["id"],),
        )
        options = [
            {
                "id": opt["id"],
                "label": opt["label"],
                "price_delta_cents": int(opt["price_delta_cents"]),
                "order_index": int(opt["order_index"] or 0),
            }
            for opt in cur.fetchall()
        ]
        conn.close()
        return {
            "id": row["id"],
            "name": row["name"],
            "price_cents": int(row["price_cents"]),
            "customizable": int(row["customizable"]),
            "track_stock": int(row["track_stock"]),
            "stock_qty": row["stock_qty"],
            "min_stock": row["min_stock"],
            "category": row["category"],
            "product_type": row["product_type"] if "product_type" in row.keys() else "",
            "sugar_levels": _deserialize_sugar_levels(row["sugar_levels"] if "sugar_levels" in row.keys() else ""),
            "options": options,
        }

    def _fetch_stock_state(self, cur, label: str) -> Optional[StockState]:
        row = cur.execute(
            "SELECT stock_qty, min_stock FROM products WHERE name=?",
            (label,),
        ).fetchone()
        if not row:
            return None
        stock = row["stock_qty"]
        min_stock = row["min_stock"]
        return (
            float(stock) if stock is not None else None,
            float(min_stock) if min_stock is not None else None,
        )

    def dec_stock(self, label: str, qty: float = 1.0, conn=None) -> Optional[StockState]:
        own_conn = conn is None
        if own_conn:
            conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE products SET stock_qty = MAX(0, COALESCE(stock_qty,0) - ?) "
            "WHERE name=? AND track_stock=1",
            (qty, label),
        )
        state = self._fetch_stock_state(cur, label)
        if own_conn:
            conn.commit()
            conn.close()
        return state

    def inc_stock(self, label: str, qty: float = 1.0, conn=None) -> Optional[StockState]:
        own_conn = conn is None
        if own_conn:
            conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE products SET stock_qty = COALESCE(stock_qty,0) + ? "
            "WHERE name=? AND track_stock=1",
            (qty, label),
        )
        state = self._fetch_stock_state(cur, label)
        if own_conn:
            conn.commit()
            conn.close()
        return state

    def get_low_stock(self) -> List[Tuple[str, Optional[float], Optional[float]]]:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT name, stock_qty, min_stock FROM products WHERE track_stock=1 AND stock_qty <= min_stock"
        )
        res = [
            (
                r["name"],
                float(r["stock_qty"]) if r["stock_qty"] is not None else None,
                float(r["min_stock"]) if r["min_stock"] is not None else None,
            )
            for r in cur.fetchall()
        ]
        conn.close()
        return res

    def get_ps_rate_hour_cents(self, mode: str) -> Optional[int]:
        cat = "PlayStation 2 Players" if mode == "P2" else "PlayStation 4 Players"
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT p.price_cents FROM products p
                   JOIN categories c ON c.id = p.category_id
                   WHERE c.name=? ORDER BY p.order_index, p.id LIMIT 1""",
            (cat,),
        )
        row = cur.fetchone()
        conn.close()
        return None if row is None else int(row["price_cents"])


@dataclass(slots=True)
class OrderItem:
    product: str
    unit_price_cents: int
    qty: float = 1
    note: str = ""
    row_id: int | None = None
    printed_qty: float = 0.0

    @property
    def total_cents(self) -> int:
        return int(self.unit_price_cents * self.qty)


@dataclass(slots=True)
class Order:
    id: int
    table_code: str
    items: List[OrderItem] = field(default_factory=list)
    status: str = "open"  # open/paid/void
    opened_by: str = ""
    client_name: str = ""
    discount_type: str = "amount"
    discount_value: float = 0.0
    discount_reason: str = ""
    paid_at: datetime | None = None
    editable_until: datetime | None = None

    @property
    def subtotal_cents(self) -> int:
        return sum(i.total_cents for i in self.items)

    @property
    def discount_cents(self) -> int:
        subtotal = max(int(self.subtotal_cents), 0)
        if self.discount_type == "percent":
            value = max(float(self.discount_value or 0.0), 0.0)
            discount = int(round(subtotal * (value / 100.0)))
        else:
            discount = int(round(float(self.discount_value or 0.0)))
        return max(0, min(subtotal, discount))

    @property
    def total_cents(self) -> int:
        return max(self.subtotal_cents - self.discount_cents, 0)

    @property
    def discount_label_key(self) -> str:
        return (
            "orders.discount_label_percent"
            if self.discount_type == "percent"
            else "orders.discount_label_amount"
        )


@dataclass(slots=True)
class PSSession:
    mode: str
    started_at: datetime
    total_seconds: int = 0


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except Exception:
        return None
    # treat naive datetimes as UTC (project currently writes datetime.utcnow())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class OrderManager:
    __slots__ = ("catalog", "orders", "ps_sessions", "table_codes", "table_clients")

    def __init__(self):
        self.catalog = ProductCatalog()
        self.orders: Dict[str, Order] = {}  # table_code -> current open order
        self.ps_sessions: Dict[str, PSSession] = {}  # table_code -> session
        self.table_codes: List[str] = _load_table_codes()
        self.table_clients: Dict[str, str] = {}
        self._load_open_orders()
        self._load_ps_sessions()
        self._load_table_clients()
        self._sync_open_tables()

    @staticmethod
    def _isoutc(dt: datetime) -> str:
        """Convert datetime to ISO format string in UTC."""
        return dt.isoformat() + 'Z'

    def _load_open_orders(self):
        # Rehydrate open orders on startup
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, table_code, status, opened_by,
                      COALESCE(client_name, '')        AS client_name,
                      COALESCE(discount_type, 'amount') AS discount_type,
                      COALESCE(discount_value, 0)      AS discount_value,
                      COALESCE(discount_reason, '')    AS discount_reason,
                      paid_at, editable_until
                   FROM orders
                   WHERE status='open'"""
        )
        for o in cur.fetchall():
            order = Order(
                id=o["id"],
                table_code=o["table_code"],
                status=o["status"],
                opened_by=o["opened_by"],
                client_name=o["client_name"] or "",
                discount_type=(o["discount_type"] or "amount"),
                discount_value=float(o["discount_value"] or 0),
                discount_reason=o["discount_reason"] or "",
                paid_at=_parse_iso_datetime(o["paid_at"] if "paid_at" in o.keys() else None),
                editable_until=_parse_iso_datetime(
                    o["editable_until"] if "editable_until" in o.keys() else None
                ),
            )
            cur.execute(
                """
                SELECT
                    id,
                    product_name,
                    price_cents,
                    qty,
                    COALESCE(printed_qty, 0) AS printed_qty,
                    COALESCE(note, '')       AS note
                FROM order_items
                WHERE order_id=?
                """,
                (order.id,),
            )
            order.items = [
                OrderItem(
                    product=r["product_name"],
                    unit_price_cents=int(r["price_cents"]),
                    qty=float(r["qty"]),
                    note=r["note"],
                    row_id=r["id"],
                    printed_qty=float(r["printed_qty"] or 0.0),
                )
                for r in cur.fetchall()
            ]
            self.orders[order.table_code] = order
            if not order.items:
                # An empty order shouldn't block table management; clean it up.
                self._cleanup_empty_order(
                    order.table_code,
                    username="system",
                    emit_events=False,
                    log_event=False,
                )
                continue
            bus.emit("table_state_changed", order.table_code, "occupied")
            bus.emit("table_total_changed", order.table_code, order.total_cents)
        conn.close()

    def reopen_for_edit(self, order_id: int, username: str = "system", reason: str = "") -> bool:
        """
        Reopen a paid order for editing:
        - delete payments
        - set status -> 'open' and clear paid/closed timestamps
        - set editable_until to now(UTC)+5min (ISO string)
        - rehydrate in-memory Order/OrderItem so UI shows items immediately
        - emit bus events so UI updates
        """
        try:
            with db_transaction() as conn:
                cur = conn.cursor()
                cur.execute("SELECT * FROM orders WHERE id=?", (order_id,))
                row = cur.fetchone()
                if not row:
                    raise OrderError("الطلب غير موجود")

                # require paid orders only (adjust policy as needed)
                if row["status"] != "paid":
                    raise OrderError("لا يمكن إعادة فتح طلب غير مدفوع")

                table_code = row["table_code"]

                # load items and convert to dicts so we can use .get safely
                cur.execute(
                    "SELECT id, product_name, price_cents, qty, COALESCE(printed_qty,0) AS printed_qty, COALESCE(note,'') AS note "
                    "FROM order_items WHERE order_id=? ORDER BY id",
                    (order_id,),
                )
                item_rows = [dict(r) for r in cur.fetchall()]

                # delete payments so order becomes editable
                cur.execute("DELETE FROM payments WHERE order_id=?", (order_id,))

                # set editable_until as aware UTC ISO (5 minutes window)
                editable_until_dt = datetime.now(timezone.utc) + timedelta(minutes=5)
                editable_until_iso = editable_until_dt.isoformat()

                # update only the known columns (do NOT touch total_cents if it doesn't exist)
                cur.execute(
                    "UPDATE orders SET status = 'open', closed_at = NULL, closed_by = NULL, paid_at = NULL, editable_until = ? WHERE id = ?",
                    (editable_until_iso, order_id),
                )

                # take a snapshot of order row as dict for later use outside transaction
                order_row = dict(row)

            # --- build in-memory items (outside transaction) ---
            items = []
            for r in item_rows:
                items.append(
                    OrderItem(
                        product=r.get("product_name", ""),
                        unit_price_cents=int(r.get("price_cents") or 0),
                        qty=float(r.get("qty") or 0.0),
                        note=r.get("note") or "",
                        row_id=r.get("id"),
                        printed_qty=float(r.get("printed_qty") or 0.0),
                    )
                )

            # create in-memory Order object (adjust args to your Order ctor)
            order = Order(
                id=order_id,
                table_code=table_code,
                items=items,
                status="open",
                opened_by=order_row.get("opened_by", "") if order_row else "",
                client_name=(order_row.get("client_name", "") if order_row else ""),
                discount_type="amount",
                discount_value=0.0,
                discount_reason="",
                paid_at=None,
                editable_until=editable_until_iso,
            )

            # put in-memory map & emit events so UI updates immediately
            self.orders[table_code] = order
            try:
                bus.emit("table_state_changed", table_code, "occupied")
                # emit total in cents computed from items (UI expects numeric cents)
                subtotal_cents = sum(int(round(it.unit_price_cents * it.qty)) for it in items)
                bus.emit("table_total_changed", table_code, int(round(subtotal_cents)))
            except Exception:
                pass

            # log the action
            try:
                log_action(username, "reopen_for_edit", "order", table_code, str(order_id), reason or "")
            except Exception:
                pass

            return True

        except OrderError:
            raise
        except Exception as e:
            logger.exception("Failed to reopen order %s: %s", order_id, e)
            raise OrderError(f"فشل إعادة فتح الطلب: {e}")

    def load_order_for_edit(self, order_id: int, username: str = "admin"):
        import warnings
        warnings.warn("load_order_for_edit is deprecated; use reopen_for_edit()", DeprecationWarning)
        return self.reopen_for_edit(order_id, username=username)

    # In orders.py, update the _load_ps_sessions method to ensure it emits the proper events:

    def _load_ps_sessions(self) -> None:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT table_code, mode, started_at, total_seconds FROM ps_sessions")
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            started_raw = row["started_at"] or ""
            try:
                started_at = datetime.fromisoformat(started_raw)
            except Exception:
                started_at = datetime.utcnow()
            sess = PSSession(
                mode=row["mode"],
                started_at=started_at,
                total_seconds=int(row["total_seconds"] or 0),
            )
            table_code = row["table_code"]
            self.ps_sessions[table_code] = sess
            if table_code not in self.table_codes:
                self.table_codes.append(table_code)
            bus.emit("ps_state_changed", table_code, True)
            # Also emit table state changed to ensure UI updates
            bus.emit("table_state_changed", table_code, "occupied")

    def _load_table_clients(self) -> None:
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT table_code, client_name FROM table_clients")
        except Exception:
            conn.close()
            return
        mapping: Dict[str, str] = {}
        for row in cur.fetchall():
            code = (row["table_code"] or "").strip().upper()
            name = (row["client_name"] or "").strip()
            if code and name:
                mapping[code] = name
        conn.close()
        self.table_clients = mapping

    def _write_client_name(self, conn, code: str, name: str) -> None:
        cur = conn.cursor()
        if name:
            cur.execute(
                """
                INSERT INTO table_clients(table_code, client_name, updated_at)
                VALUES(?,?,?)
                ON CONFLICT(table_code) DO UPDATE SET
                    client_name=excluded.client_name,
                    updated_at=excluded.updated_at
                """,
                (code, name, datetime.utcnow().isoformat()),
            )
        else:
            cur.execute("DELETE FROM table_clients WHERE table_code=?", (code,))

    def _apply_client_name(self, code: str, name: str) -> None:
        normalized = (code or "").strip().upper()
        if not normalized:
            return
        if name:
            self.table_clients[normalized] = name
        else:
            self.table_clients.pop(normalized, None)
        order = self.orders.get(normalized)
        if not order and code != normalized:
            order = self.orders.get(code)
        if order:
            order.client_name = name
        try:
            bus.emit("table_client_name_changed", normalized, name)
        except Exception:
            pass

    def get_client_name(self, table_code: str) -> str:
        return self.table_clients.get((table_code or "").strip().upper(), "")

    def list_client_names(self) -> Dict[str, str]:
        return dict(self.table_clients)

    def set_client_name(self, table_code: str, client_name: str, *, actor: str = "system") -> str:
        code = (table_code or "").strip().upper()
        if not code:
            return ""
        name = (client_name or "").strip()
        with db_transaction() as conn:
            self._write_client_name(conn, code, name)
            conn.execute(
                "UPDATE orders SET client_name=? WHERE table_code=? AND status='open'",
                (name, code),
            )
        self._apply_client_name(code, name)
        if name:
            try:
                log_action(actor, "table_client_named", "table", code, None, name)
            except Exception:
                pass
        return name

    def _sync_open_tables(self) -> None:
        missing = [code for code in self.orders.keys() if code not in self.table_codes]
        if not missing:
            return
        self.table_codes.extend(missing)
        _store_table_codes(self.table_codes)
        bus.emit("tables_changed", list(self.table_codes))

    def _is_order_edit_locked(self, order: Order) -> bool:
        """
        Return True if the order is locked for editing.
        MODIFIED: Always returns False to remove time restrictions.
        """
        # ALWAYS allow editing - remove all time restrictions!
        return False
    def _ensure_order_editable(self, order: Order) -> None:
        if self._is_order_edit_locked(order):
            raise EditWindowError()

    def can_edit(self, table_code: str) -> bool:
        order = self.orders.get(table_code)
        if not order:
            return False
        return not self._is_order_edit_locked(order)

    def get_discount_label_key(self, table_code: str) -> str:
        order = self.orders.get(table_code)
        if not order:
            return "orders.discount_label_amount"
        return order.discount_label_key

    @property
    def categories(self):
        return self.catalog.categories()

    def get_table_codes(self) -> List[str]:
        return list(self.table_codes)

    def set_table_codes(self, codes: List[str], *, actor: str = "system") -> List[str]:
        cleaned = _normalize_table_codes(codes)
        if not cleaned:
            cleaned = _default_table_codes()
        for open_code in self.orders.keys():
            if open_code not in cleaned:
                cleaned.append(open_code)
        if cleaned == self.table_codes:
            return list(self.table_codes)
        previous = json.dumps(self.table_codes, ensure_ascii=False)
        self.table_codes = cleaned
        _store_table_codes(cleaned)
        bus.emit("tables_changed", list(self.table_codes))
        try:
            log_action(actor, "tables_update", "table_map", None, previous, json.dumps(cleaned, ensure_ascii=False))
        except Exception:
            pass
        return list(self.table_codes)

    def _ensure_db_order_tx(self, conn, table_code: str, opened_by: str) -> tuple[Order, bool]:
        existing = self.orders.get(table_code)
        if existing and existing.status == "open":
            return existing, False
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO orders(table_code, opened_at, status, opened_by, client_name)
               VALUES(?,?,?,?,?)""",
            (
                table_code,
                datetime.utcnow().isoformat(),
                "open",
                opened_by,
                self.table_clients.get(table_code, ""),
            ),
        )
        order = Order(
            id=cur.lastrowid,
            table_code=table_code,
            opened_by=opened_by,
            client_name=self.table_clients.get(table_code, ""),
        )
        self.orders[table_code] = order
        return order, True

    def add_item(
            self,
            table_code: str,
            product: str,
            price_cents: int,
            qty: float = 1.0,
            cashier: str = "cashier",
            note: str = "",
    ):
        """
        Enforces stock for tracked products; ignores stock for services/unlimited.
        If the 'product' is not found in DB (e.g., PS billing line), treat as non-tracked.
        """
        # Resolve product record (if exists)
        prod = self.catalog.get_product(product)

        low_stock_event = None
        catalog_refresh = False
        if prod and prod["track_stock"] == 1:
            stock = float(prod["stock_qty"]) if prod["stock_qty"] is not None else 0.0
            if stock < qty:
                raise StockError(f"المنتج '{product}' غير متوفر في المخزون")

            def _check_state(state):
                nonlocal low_stock_event, catalog_refresh
                new_stock = state[0] if state else None
                min_stock = state[1] if state else None
                if new_stock is not None and stock > 0 and new_stock <= 0:
                    catalog_refresh = True
                if (
                        new_stock is not None
                        and min_stock is not None
                        and stock >= min_stock
                        and new_stock <= min_stock
                ):
                    low_stock_event = (product, stock, new_stock, min_stock)

            with db_transaction() as conn:
                order, created = self._ensure_db_order_tx(conn, table_code, opened_by=cashier)
                self._ensure_order_editable(order)
                state = self.catalog.dec_stock(product, qty, conn=conn)
                _check_state(state)
                cursor = conn.execute(
                    "INSERT INTO order_items(order_id, product_name, price_cents, qty, note, printed_qty) VALUES(?,?,?,?,?,?)",
                    (order.id, product, price_cents, qty, note, 0),
                )
                order.items.append(
                    OrderItem(product, price_cents, qty, note=note, row_id=cursor.lastrowid, printed_qty=0.0)
                )
            if created:
                bus.emit("table_state_changed", table_code, "occupied")
        else:
            with db_transaction() as conn:
                order, created = self._ensure_db_order_tx(conn, table_code, opened_by=cashier)
                self._ensure_order_editable(order)
                cursor = conn.execute(
                    "INSERT INTO order_items(order_id, product_name, price_cents, qty, note, printed_qty) VALUES(?,?,?,?,?,?)",
                    (order.id, product, price_cents, qty, note, 0),
                )
                order.items.append(
                    OrderItem(product, price_cents, qty, note=note, row_id=cursor.lastrowid, printed_qty=0.0)
                )
            if created:
                bus.emit("table_state_changed", table_code, "occupied")

        bus.emit("table_total_changed", table_code, order.total_cents)
        if catalog_refresh:
            bus.emit("catalog_changed")
        if low_stock_event:
            product_name, before, after, threshold = low_stock_event
            bus.emit("inventory_low", product_name, before, after, threshold)
            log_action(
                cashier,
                "inventory_low",
                "product",
                product_name,
                str(before),
                str(after),
            )

    def remove_item(self, table_code: str, index: int, username: str = "system"):
        order = self.orders.get(table_code)
        if not order:
            return
        self._ensure_order_editable(order)
        if 0 <= index < len(order.items):
            item = order.items.pop(index)

            prod = self.catalog.get_product(item.product)
            before = None
            refresh_catalog = False
            recovery_event = None
            if prod and prod["track_stock"] == 1:
                before = float(prod["stock_qty"]) if prod["stock_qty"] is not None else 0.0

            with db_transaction() as conn:
                if prod and prod["track_stock"] == 1:
                    state = self.catalog.inc_stock(item.product, item.qty, conn=conn)
                    new_stock = state[0] if state else None
                    min_stock = state[1] if state else None
                    if before is not None and before <= 0 and new_stock is not None and new_stock > 0:
                        refresh_catalog = True
                    if (
                            before is not None
                            and new_stock is not None
                            and min_stock is not None
                            and before <= min_stock < new_stock
                    ):
                        recovery_event = (item.product, before, new_stock, min_stock)
                if item.row_id is not None:
                    conn.execute("DELETE FROM order_items WHERE id=?", (item.row_id,))
                else:
                    conn.execute(
                        """DELETE FROM order_items WHERE id IN (
                             SELECT id FROM order_items
                             WHERE order_id=? AND product_name=? AND price_cents=? AND qty=? AND COALESCE(note,'')=?
                             LIMIT 1
                           )""",
                        (order.id, item.product, item.unit_price_cents, item.qty, item.note or ""),
                    )

            if refresh_catalog:
                bus.emit("catalog_changed")
            if recovery_event:
                prod_name, prev, new_stock, min_stock = recovery_event
                bus.emit("inventory_recovered", prod_name, prev, new_stock, min_stock)
                log_action(
                    username,
                    "inventory_recovered",
                    "product",
                    prod_name,
                    str(prev),
                    str(new_stock),
                )
            bus.emit("table_total_changed", table_code, order.total_cents)
            if not order.items:
                self._cleanup_empty_order(table_code, username=username)

    def update_item(
            self,
            table_code: str,
            index: int,
            *,
            qty: float | None = None,
            note: str | None = None,
            username: str = "system",
    ) -> bool:
        order = self.orders.get(table_code)
        if not order or not (0 <= index < len(order.items)):
            return False
        self._ensure_order_editable(order)
        item = order.items[index]
        new_qty = float(qty) if qty is not None else float(item.qty)
        if new_qty <= 0:
            self.remove_item(table_code, index, username=username)
            return True
        new_note = (note.strip() if isinstance(note, str) else item.note).strip()
        if abs(new_qty - item.qty) < 1e-6 and new_note == item.note:
            return True

        prod = self.catalog.get_product(item.product)
        track = prod and prod["track_stock"] == 1
        before_stock = None
        if track:
            stock_val = prod.get("stock_qty") if prod else None
            before_stock = float(stock_val) if stock_val is not None else 0.0

        delta_qty = new_qty - item.qty
        low_stock_event = None
        recovery_event = None
        refresh_catalog = False

        with db_transaction() as conn:
            if track and delta_qty > 0:
                available = before_stock if before_stock is not None else 0.0
                if available < delta_qty - 1e-6:
                    raise StockError(f"المنتج '{item.product}' غير متوفر بالكمية المطلوبة")
                state = self.catalog.dec_stock(item.product, delta_qty, conn=conn)
                new_stock = state[0] if state else None
                min_stock = state[1] if state else None
                if new_stock is not None and (before_stock or 0) > 0 and new_stock <= 0:
                    refresh_catalog = True
                if (
                        new_stock is not None
                        and min_stock is not None
                        and (before_stock is not None and before_stock >= min_stock)
                        and new_stock <= min_stock
                ):
                    low_stock_event = (item.product, before_stock, new_stock, min_stock)
            elif track and delta_qty < 0:
                state = self.catalog.inc_stock(item.product, -delta_qty, conn=conn)
                new_stock = state[0] if state else None
                min_stock = state[1] if state else None
                if before_stock is not None and before_stock <= 0 and new_stock is not None and new_stock > 0:
                    refresh_catalog = True
                if (
                        before_stock is not None
                        and new_stock is not None
                        and min_stock is not None
                        and before_stock <= min_stock < new_stock
                ):
                    recovery_event = (item.product, before_stock, new_stock, min_stock)

            # clamp printed_qty so it never exceeds the new qty
            item.printed_qty = min(float(getattr(item, "printed_qty", 0.0)), float(new_qty))

            if item.row_id is not None:
                conn.execute(
                    "UPDATE order_items SET qty=?, note=?, printed_qty=? WHERE id=?",
                    (new_qty, new_note, item.printed_qty, item.row_id),
                )
            else:
                conn.execute(
                    """UPDATE order_items SET qty=?, note=?, printed_qty=? WHERE id IN (
                           SELECT id FROM order_items
                           WHERE order_id=? AND product_name=? AND price_cents=?
                                 AND qty=? AND COALESCE(note,'')=?
                           LIMIT 1
                       )""",
                    (new_qty, new_note, item.printed_qty,
                     order.id, item.product, item.unit_price_cents, item.qty, item.note or ""),
                )
            item.qty = new_qty
            item.note = new_note

        if refresh_catalog:
            bus.emit("catalog_changed")
        if low_stock_event:
            prod_name, before, after, threshold = low_stock_event
            bus.emit("inventory_low", prod_name, before, after, threshold)
            log_action(
                username,
                "inventory_low",
                "product",
                prod_name,
                str(before),
                str(after),
            )
        if recovery_event:
            prod_name, before, after, threshold = recovery_event
            bus.emit("inventory_recovered", prod_name, before, after, threshold)
            log_action(
                username,
                "inventory_recovered",
                "product",
                prod_name,
                str(before),
                str(after),
            )
        bus.emit("table_total_changed", table_code, order.total_cents)
        return True

    def get_items(self, table_code: str):
        o = self.orders.get(table_code)
        return [] if not o else o.items

    def reload_table_items(self, table_code: str) -> None:
        """Reload order items for *table_code* from the database."""

        code = (table_code or "").strip().upper()
        if not code:
            return
        order = self.orders.get(code)
        if not order:
            return
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT id, product_name, price_cents, qty, COALESCE(note,'') AS note,
                       COALESCE(printed_qty,0) AS printed_qty
                FROM order_items
                WHERE order_id=?
                ORDER BY id
                """,
                (order.id,),
            )
            order.items = [
                OrderItem(
                    product=row["product_name"],
                    unit_price_cents=int(row["price_cents"]),
                    qty=float(row["qty"]),
                    note=row["note"],
                    row_id=row["id"],
                    printed_qty=float(row["printed_qty"] or 0.0),
                )
                for row in cur.fetchall()
            ]
        finally:
            conn.close()

    def list_open_tables(self, exclude: str | None = None) -> list[str]:
        exclude_norm = (exclude or "").strip().upper()
        return [
            code
            for code, order in self.orders.items()
            if order.status == "open" and code != exclude_norm
        ]

    def list_open_tables_with_totals(self, exclude: str | None = None) -> list[tuple[str, int]]:
        exclude_norm = (exclude or "").strip().upper()
        return [
            (code, order.total_cents)
            for code, order in self.orders.items()
            if order.status == "open" and code != exclude_norm
        ]

    def get_totals(self, table_code: str):
        o = self.orders.get(table_code)
        if not o:
            return 0, 0, 0, "orders.discount_label_amount"
        return o.subtotal_cents, o.discount_cents, o.total_cents, o.discount_label_key

    def move_table(self, source_table: str, dest_table: str, *, username: str = "system") -> bool:
        """Move order from source to dest (dest must be FREE)"""
        try:
            src = (source_table or "").strip().upper()
            dst = (dest_table or "").strip().upper()

            if not src or not dst:
                raise MoveError("اسم الطاولة غير صالح")
            if src == dst:
                raise MoveError("لا يمكن نقل الطاولة إلى نفسها")

            src_order = self.orders.get(src)
            if not src_order or src_order.status != "open":
                raise MoveError(f"الطاولة {src} ليس لديها طلب مفتوح")

            dst_order = self.orders.get(dst)
            if dst_order and dst_order.status == "open":
                raise MoveError(f"الطاولة {dst} مشغولة. استخدم الدمج بدلاً من النقل")

            # Move PS session if exists
            ps_sess = self.ps_sessions.pop(src, None)

            with db_transaction() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE orders SET table_code=? WHERE id=?", (dst, src_order.id))
                if ps_sess:
                    cur.execute("UPDATE ps_sessions SET table_code=? WHERE table_code=?", (dst, src))
                    self.ps_sessions[dst] = ps_sess
                client_name = self.table_clients.get(src, "")
                self._write_client_name(conn, src, "")
                self._write_client_name(conn, dst, client_name)

            # Update in-memory
            src_order.table_code = dst
            self.orders[dst] = src_order
            self.orders.pop(src, None)
            client_name = self.table_clients.get(src, "")
            self._apply_client_name(src, "")
            self._apply_client_name(dst, client_name)

            # Ensure dest in table_codes
            if dst not in self.table_codes:
                self.table_codes.append(dst)
                _store_table_codes(self.table_codes)
                bus.emit("tables_changed", list(self.table_codes))

            # Emit events
            bus.emit("table_state_changed", src, "free")
            bus.emit("table_total_changed", src, 0)
            bus.emit("ps_state_changed", src, False)
            bus.emit("table_state_changed", dst, "occupied")
            bus.emit("table_total_changed", dst, src_order.total_cents)
            if ps_sess:
                bus.emit("ps_state_changed", dst, True)

            log_action(username, "move_table", "order", src, src, dst)
            return True

        except MoveError:
            raise
        except Exception as e:
            logger.error(f"Move failed {src}->{dst}: {e}")
            raise MoveError(f"فشل نقل الطاولة: {e}")

    def _merge_tables_core(
            self,
            target_table: str,
            source_table: str,
            *,
            username: str = "system",
    ) -> bool:
        """
        Core merge logic: Merge SOURCE into TARGET.
        - source = table being merged FROM (will be cleared)
        - target = table being merged INTO (gets all items)
        """
        try:
            target = (target_table or "").strip().upper()
            source = (source_table or "").strip().upper()

            # Validation
            if not target or not source:
                logger.warning(f"Invalid table codes: target='{target}', source='{source}'")
                raise MergeError("أسماء الطاولات غير صالحة")

            if target == source:
                logger.warning(f"Attempt to merge table with itself: '{target}'")
                raise MergeError("لا يمكن دمج الطاولة مع نفسها")

            # Get orders
            primary = self.orders.get(target)
            secondary = self.orders.get(source)

            if not primary or primary.status != "open":
                logger.warning(f"Target table '{target}' has no open order")
                raise MergeError(f"الطاولة {target} ليس لديها طلب مفتوح")

            if not secondary or secondary.status != "open":
                logger.warning(f"Source table '{source}' has no open order")
                raise MergeError(f"الطاولة {source} ليس لديها طلب مفتوح")

            # Bill any running PS session on SOURCE before merging
            try:
                if source in self.ps_sessions:
                    logger.info(f"Closing PS session on source table '{source}' before merge")
                    self._close_session_and_bill(source)
                    # Reload secondary order after billing
                    secondary = self.orders.get(source)
                    if not secondary or secondary.status != "open":
                        logger.error(f"Source order vanished after PS billing: '{source}'")
                        raise MergeError("فشل إغلاق جلسة البلايستيشن")
            except MergeError:
                raise
            except Exception as e:
                logger.error(f"Failed to close PS session during merge: {e}")
                raise MergeError(f"فشل إغلاق جلسة البلايستيشن: {e}")

            # Perform merge in database transaction
            target_name = self.table_clients.get(target, "")
            source_name = self.table_clients.get(source, "")
            try:
                with db_transaction() as conn:
                    cur = conn.cursor()

                    # Move all items from source to target
                    for item in secondary.items:
                        if item.row_id is not None:
                            # Relink existing DB rows
                            cur.execute(
                                "UPDATE order_items SET order_id=? WHERE id=?",
                                (primary.id, item.row_id),
                            )
                        else:
                            # Insert ephemeral items (shouldn't happen normally)
                            cur.execute(
                                "INSERT INTO order_items(order_id, product_name, price_cents, qty, note, printed_qty) "
                                "VALUES(?,?,?,?,?,?)",
                                (primary.id, item.product, item.unit_price_cents, item.qty,
                                 item.note, float(getattr(item, 'printed_qty', 0.0))),
                            )
                            item.row_id = cur.lastrowid

                    # Move any payments from source to target (partial payments support)
                    cur.execute("UPDATE payments SET order_id=? WHERE order_id=?", (primary.id, secondary.id))

                    # Merge discounts
                    merged_disc = max(0, int(primary.discount_cents) + int(secondary.discount_cents))
                    try:
                        cur.execute(
                            "UPDATE orders SET discount_cents=?, discount_type='amount', discount_value=?, discount_reason='' WHERE id=?",
                            (merged_disc, float(merged_disc), primary.id),
                        )
                    except Exception as e:
                        logger.warning(f"Could not update discount columns (old DB?): {e}")
                        # Continue without discount if column doesn't exist

                    # Void the source order
                    cur.execute(
                        "UPDATE orders SET status='void', closed_at=?, closed_by=? WHERE id=?",
                        (datetime.utcnow().isoformat(), username, secondary.id),
                    )
                    chosen_name = target_name or source_name
                    self._write_client_name(conn, source, "")
                    self._write_client_name(conn, target, chosen_name)

            except Exception as e:
                logger.error(f"Database error during merge {source}->{target}: {e}")
                raise MergeError(f"فشل حفظ الدمج في قاعدة البيانات: {e}")

            # Update in-memory state
            try:
                primary.items.extend(secondary.items)
                primary.discount_type = "amount"
                primary.discount_value = float(merged_disc)
                primary.discount_reason = ""

                secondary.items = []
                secondary.status = "void"
                self.orders.pop(source, None)
                chosen_name = target_name or source_name
                self._apply_client_name(source, "")
                self._apply_client_name(target, chosen_name)
            except Exception as e:
                logger.error(f"Error updating in-memory state: {e}")
                # Database is already updated, so continue

            # Emit UI events
            try:
                bus.emit("table_state_changed", source, "free")
                bus.emit("table_total_changed", source, 0)
                bus.emit("ps_state_changed", source, False)
                bus.emit("table_state_changed", target, "occupied")
                bus.emit("table_total_changed", target, primary.total_cents)
            except Exception as e:
                logger.error(f"Error emitting bus events: {e}")
                # Continue - UI will eventually sync

            # Log the action
            try:
                log_action(
                    username,
                    "merge_tables",
                    "order",
                    target,
                    f"{source} -> {target}",
                    str(primary.total_cents),
                )
            except Exception as e:
                logger.warning(f"Failed to log merge action: {e}")

            logger.info(f"Successfully merged '{source}' into '{target}' (total: {primary.total_cents})")
            return True

        except MergeError:
            raise  # Re-raise MergeError as-is
        except Exception as e:
            logger.error(f"Unexpected error merging '{source_table}' into '{target_table}': {e}")
            raise MergeError(f"فشل دمج الطاولات: {e}")

    def relocate_or_merge_table(
            self,
            source_table: str,
            dest_table: str,
            *,
            username: str = "system",
    ) -> str:
        """
        If dest has an open order -> MERGE (source -> dest).
        If dest is free (no open order) -> MOVE (source -> dest).
        Returns: "merged", "moved", or raises ValueError on invalid inputs.
        """
        src = (source_table or "").strip().upper()
        dst = (dest_table or "").strip().upper()

        if not src or not dst or src == dst:
            raise ValueError("Invalid source/destination")

        src_order = self.orders.get(src)
        if not src_order or src_order.status != "open":
            raise ValueError("Source table has no open order")

        dst_order = self.orders.get(dst)

        # Case A: destination already has an open order -> MERGE
        if dst_order and dst_order.status == "open":
            ok = self._merge_tables_core(target_table=dst, source_table=src, username=username)
            if not ok:
                raise RuntimeError("Merge failed")
            return "merged"

        # Case B: destination is free -> MOVE
        ok = self.move_table(source_table=src, dest_table=dst, username=username)
        if not ok:
            raise RuntimeError("Move failed")
        return "moved"

    def merge_tables(
            self,
            target_table: str,
            source_table: str,
            *,
            username: str = "system",
    ) -> bool:
        """
        Backward-compatible wrapper for old UI code.
        Calls the core merge directly (no recursion).
        """
        try:
            return self._merge_tables_core(target_table=target_table, source_table=source_table, username=username)
        except Exception:
            return False

    def apply_discount(
            self,
            table_code: str,
            value: float,
            discount_type: str = "amount",
            *,
            reason: str = "",
            username: str = "system",
    ) -> None:
        order = self.orders.get(table_code)
        if not order:
            return
        self._ensure_order_editable(order)
        dtype = "percent" if discount_type == "percent" else "amount"
        try:
            raw_value = float(value)
        except (TypeError, ValueError):
            raw_value = 0.0
        raw_value = max(raw_value, 0.0)

        subtotal = order.subtotal_cents
        if dtype == "percent":
            discount_cents = int(round(subtotal * (raw_value / 100.0)))
        else:
            discount_cents = int(round(raw_value))
        discount_cents = max(0, min(subtotal, discount_cents))

        with db_transaction() as conn:
            conn.execute(
                "UPDATE orders SET discount_cents=?, discount_type=?, discount_value=?, discount_reason=? WHERE id=?",
                (discount_cents, dtype, raw_value, reason or "", order.id),
            )

        order.discount_type = dtype
        order.discount_value = raw_value
        order.discount_reason = reason or ""
        bus.emit("table_total_changed", table_code, order.total_cents)

    def _cleanup_empty_order(
            self,
            table_code: str,
            *,
            username: str = "system",
            emit_events: bool = True,
            log_event: bool = True,
    ) -> bool:
        """Remove an order that no longer has any items."""
        order = self.orders.get(table_code)
        if not order or order.items:
            return False

        with db_transaction() as conn:
            conn.execute("DELETE FROM order_items WHERE order_id=?", (order.id,))
            conn.execute("DELETE FROM orders WHERE id=?", (order.id,))
            self._write_client_name(conn, table_code, "")

        self.orders.pop(table_code, None)
        self._apply_client_name(table_code, "")

        if emit_events:
            bus.emit("table_state_changed", table_code, "free")
            bus.emit("table_total_changed", table_code, 0)
            bus.emit("ps_state_changed", table_code, False)

        if log_event:
            try:
                log_action(
                    username,
                    "order_auto_cleared",
                    "table",
                    table_code,
                    None,
                    "auto",
                )
            except Exception:
                pass

        return True

    def empty_table(
            self,
            table_code: str,
            *,
            username: str = "system",
            reason: str = "",
    ) -> bool:
        """Force-clear a table by voiding the open order and restoring stock."""
        code = (table_code or "").strip().upper()
        if not code:
            raise OrderError("رمز الطاولة غير صالح")

        order = self.orders.get(code)
        refresh_catalog = False
        recovery_events: list[tuple[str, float, float, float]] = []
        now_iso = datetime.utcnow().isoformat()
        had_order = bool(order)

        with db_transaction() as conn:
            if order:
                for item in list(order.items):
                    prod = self.catalog.get_product(item.product)
                    before = None
                    if prod and prod.get("track_stock") == 1:
                        stock_val = prod.get("stock_qty")
                        before = float(stock_val) if stock_val is not None else 0.0
                        state = self.catalog.inc_stock(item.product, item.qty, conn=conn)
                        new_stock = state[0] if state else None
                        min_stock = state[1] if state else None
                        if (
                                before is not None
                                and before <= 0
                                and new_stock is not None
                                and new_stock > 0
                        ):
                            refresh_catalog = True
                        if (
                                before is not None
                                and new_stock is not None
                                and min_stock is not None
                                and before <= min_stock < new_stock
                        ):
                            recovery_events.append((item.product, before, new_stock, min_stock))
                    if item.row_id is not None:
                        conn.execute("DELETE FROM order_items WHERE id=?", (item.row_id,))
                conn.execute("DELETE FROM order_items WHERE order_id=?", (order.id,))
                conn.execute("DELETE FROM payments WHERE order_id=?", (order.id,))
                conn.execute(
                    "UPDATE orders SET status='void', closed_at=?, closed_by=?, paid_at=NULL WHERE id=?",
                    (now_iso, username, order.id),
                )
                self._write_client_name(conn, code, "")
            else:
                conn.execute(
                    "UPDATE orders SET status='void', closed_at=?, closed_by=? WHERE table_code=? AND status='open'",
                    (now_iso, username, code),
                )
                self._write_client_name(conn, code, "")

            conn.execute("DELETE FROM ps_sessions WHERE table_code=?", (code,))

        self.orders.pop(code, None)
        self.ps_sessions.pop(code, None)
        self._apply_client_name(code, "")

        if refresh_catalog:
            bus.emit("catalog_changed")
        for prod_name, prev, new_stock, min_stock in recovery_events:
            bus.emit("inventory_recovered", prod_name, prev, new_stock, min_stock)
            try:
                log_action(
                    username,
                    "inventory_recovered",
                    "product",
                    prod_name,
                    str(prev),
                    str(new_stock),
                )
            except Exception:
                pass

        bus.emit("table_state_changed", code, "free")
        bus.emit("table_total_changed", code, 0)
        bus.emit("ps_state_changed", code, False)

        try:
            log_action(
                username,
                "table_cleared",
                "table",
                code,
                str(getattr(order, "id", "")),
                reason or "",
            )
        except Exception:
            pass

        return had_order
    def clear_discount(self, table_code: str, username: str = "system") -> None:
        order = self.orders.get(table_code)
        if not order:
            return
        self._ensure_order_editable(order)
        order.discount_type = "amount"
        order.discount_value = 0.0
        order.discount_reason = ""
        with db_transaction() as conn:
            conn.execute(
                "UPDATE orders SET discount_cents=0, discount_type='amount', discount_value=0, discount_reason='' WHERE id=?",
                (order.id,),
            )
        bus.emit("table_total_changed", table_code, order.total_cents)

    def _ensure_dt(self, value) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            dt = value
        else:
            # value may be an ISO string saved earlier
            try:
                dt = datetime.fromisoformat(str(value))
            except Exception:
                # fallback: try naive parsing and assume UTC
                try:
                    dt = datetime.strptime(str(value), "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    return None
        # If naive, treat as UTC (project writes utcnow() historically).
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _force_add_ps_item(self, table_code: str, detail: str, amount_cents: int):
        """Force add PS billing item bypassing normal edit checks"""
        # Get or create order
        if table_code not in self.orders:
            # Create a new order for the PS billing
            from datetime import datetime
            new_order = type('Order', (), {})()  # Create a simple order object
            new_order.table_code = table_code
            new_order.opened_at = datetime.utcnow().isoformat()
            new_order.status = "open"
            new_order.opened_by = "system"
            self.orders[table_code] = new_order

        # Add the item directly to order items
        order = self.orders[table_code]
        if not hasattr(order, 'items'):
            order.items = []

        # Create item object
        new_item = type('OrderItem', (), {})()
        new_item.product = detail
        new_item.price_cents = amount_cents
        new_item.qty = 1
        new_item.note = ""

        order.items.append(new_item)

        # Update totals
        bus.emit("table_total_changed", table_code, self._calculate_order_total(table_code))

    def _close_session_and_bill(self, table_code: str):
        """Close PlayStation session and bill it to the order"""
        sess = self.ps_sessions.get(table_code)
        if not sess:
            return

        try:
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            started = sess.started_at
            if isinstance(started, str):
                try:
                    started_dt = datetime.fromisoformat(started)
                except Exception:
                    started_dt = now
            else:
                started_dt = started

            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)

            elapsed = int(sess.total_seconds or 0) + max(0, int((now - started_dt).total_seconds()))
            minutes = max(1, math.ceil(elapsed / 60.0))

            # Get PS prices from settings
            from ..core.db import setting_get

            table_code_norm = (table_code or "").strip().upper()
            vip_tables_raw = setting_get("ps_vip_tables", "[]")
            vip_tables: set[str] = set()
            try:
                parsed = json.loads(vip_tables_raw)
                if isinstance(parsed, list):
                    vip_tables = {str(code).strip().upper() for code in parsed if isinstance(code, str)}
            except Exception:
                vip_tables = set()
            is_vip = table_code_norm in vip_tables

            if sess.mode == "P2":
                base_rate = setting_get("ps_rate_p2", "50")
                rate_str = setting_get("ps_vip_rate_p2", base_rate) if is_vip else base_rate
            else:
                base_rate = setting_get("ps_rate_p4", "80")
                rate_str = setting_get("ps_vip_rate_p4", base_rate) if is_vip else base_rate

            try:
                rate_le_per_hour = int(rate_str)
            except (ValueError, TypeError):
                rate_le_per_hour = 50 if sess.mode == "P2" else 80

            # Calculate price in LE (no need to multiply by 100!)
            le_per_minute = rate_le_per_hour / 60.0
            amount_le = le_per_minute * minutes

            # Store as LE amount (not cents) - just round it
            amount_for_storage = int(round(amount_le))

            label = "PS ٢ لاعبين" if sess.mode == "P2" else "PS ٤ لاعبين"
            if is_vip:
                label += " (VIP)"
            detail = f"{label} — {minutes} دقيقة"

            print(f"DEBUG: PS billing:")
            print(f"  Amount in LE: {amount_le:.2f} LE")
            print(f"  Stored as: {amount_for_storage}")  # Should be 1 for 1.33 LE
            print(f"  Will display as: {amount_for_storage} ج.م")

            try:
                self.add_item(table_code, detail, amount_for_storage)
                print(f"SUCCESS: PS billing added - {amount_le:.2f} LE for {minutes} minutes")
            except Exception as e:
                print(f"ERROR: Failed to add PS billing item: {e}")

        except Exception as e:
            logger.error(f"Error calculating PS bill for '{table_code}': {e}")

        finally:
            try:
                self.ps_sessions.pop(table_code, None)
                with db_transaction() as conn:
                    conn.execute("DELETE FROM ps_sessions WHERE table_code=?", (table_code,))
                bus.emit("ps_state_changed", table_code, False)
            except Exception as e:
                logger.error(f"Failed to cleanup PS session for '{table_code}': {e}")
    def ps_start(self, table_code: str, mode: str):
        # if there's an open session, bill it first
        self._close_session_and_bill(table_code)
        now = datetime.now(timezone.utc)
        # keep started_at as datetime on object, store ISO in DB
        self.ps_sessions[table_code] = PSSession(mode=mode, started_at=now, total_seconds=0)
        with db_transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ps_sessions(table_code, mode, started_at, total_seconds) VALUES(?,?,?,?)",
                (table_code, mode, self._isoutc(now), 0),
            )
        bus.emit("ps_state_changed", table_code, True)

    def ps_switch(self, table_code: str, new_mode: str):
        # close and bill current session first
        self._close_session_and_bill(table_code)
        now = datetime.now(timezone.utc)
        self.ps_sessions[table_code] = PSSession(mode=new_mode, started_at=now, total_seconds=0)
        with db_transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ps_sessions(table_code, mode, started_at, total_seconds) VALUES(?,?,?,?)",
                (table_code, new_mode, self._isoutc(now), 0),
            )
        bus.emit("ps_state_changed", table_code, True)

    def ps_stop(self, table_code: str):
        self._close_session_and_bill(table_code)

    def snapshot_ps_sessions(self) -> None:
        """Persist current sessions: update total_seconds and started_at (reset to now)."""
        if not self.ps_sessions:
            return
        with db_transaction() as conn:
            for table_code, sess in list(self.ps_sessions.items()):
                now = datetime.now(timezone.utc)
                started_at = self._ensure_dt(sess.started_at)
                if started_at is None:
                    started_at = now
                elapsed = max(0, int((now - started_at).total_seconds()))
                sess.total_seconds = int(getattr(sess, "total_seconds", 0) or 0) + elapsed
                # reset started_at to now (persisted)
                sess.started_at = now
                conn.execute(
                    "INSERT OR REPLACE INTO ps_sessions(table_code, mode, started_at, total_seconds) VALUES(?,?,?,?)",
                    (table_code, sess.mode, self._isoutc(sess.started_at), sess.total_seconds),
                )

    def get_unprinted_bar_items(self, table_code: str) -> List[OrderItem]:
        o = self.orders.get(table_code)
        if not o:
            return []
        result: List[OrderItem] = []
        for it in o.items:
            pq = float(getattr(it, "printed_qty", 0.0))
            remaining = max(0.0, float(it.qty) - pq)
            if remaining > 0:
                result.append(
                    OrderItem(
                        product=it.product,
                        unit_price_cents=it.unit_price_cents,
                        qty=remaining,
                        note=it.note,
                        row_id=it.row_id,
                        printed_qty=0.0,
                    )
                )
        return result

    def mark_bar_items_as_printed(self, table_code: str, printed_items: List[OrderItem]) -> int:
        """
        Increment printed_qty on matching order_items by the amounts we just printed.
        Matching key = (product, note, unit_price_cents). Never exceed qty.
        Returns the total quantity marked as printed (for info only).
        """
        if not printed_items:
            return 0
        order = self.orders.get(table_code)
        if not order:
            return 0

        EPS = 1e-6

        def make_key(x: OrderItem):
            return (x.product, (x.note or ""), int(x.unit_price_cents))

        # Aggregate what was printed per key
        printed_totals: Dict[tuple, float] = {}
        for p in printed_items:
            k = make_key(p)
            printed_totals[k] = printed_totals.get(k, 0.0) + float(p.qty)

        marked_total = 0.0
        with db_transaction() as conn:
            for it in order.items:
                k = make_key(it)
                to_apply = printed_totals.get(k, 0.0)
                if to_apply <= EPS:
                    continue

                current_printed = float(getattr(it, "printed_qty", 0.0) or 0.0)
                qty = float(it.qty)

                remaining = max(0.0, qty - current_printed)
                if remaining <= EPS:
                    continue

                take = min(remaining, to_apply)
                new_printed = min(qty, current_printed + take)  # clamp ≤ qty

                # Persist
                if it.row_id is not None:
                    conn.execute(
                        "UPDATE order_items SET printed_qty=? WHERE id=?",
                        (new_printed, it.row_id)
                    )

                # Update in-memory
                it.printed_qty = new_printed

                # Decrease what's left to apply for that key
                printed_totals[k] = max(0.0, to_apply - take)
                marked_total += take

        return int(marked_total)  # or round(...) if you expect halves

    def settle(self, table_code: str, method: str = "cash", cashier: str = "cashier"):
        # Close any running PS session and bill it first
        self._close_session_and_bill(table_code)

        o = self.orders.get(table_code)
        if not o:
            return False

        amount = o.total_cents

        # Persist payment & close order in DB
        paid_dt = datetime.utcnow()
        paid_at = paid_dt.isoformat()
        editable_until = (paid_dt + timedelta(seconds=EDIT_WINDOW_SECONDS)).isoformat()
        with db_transaction() as conn:
            conn.execute(
                """INSERT INTO payments(order_id, method, amount_cents, paid_at, cashier)
                   VALUES(?,?,?,?,?)""",
                (o.id, method, amount, paid_at, cashier),
            )
            conn.execute(
                """UPDATE orders
                   SET status='paid', closed_at=?, closed_by=?, paid_at=?, editable_until=?
                   WHERE id=?""",
                (paid_at, cashier, paid_at, editable_until, o.id),
            )
            self._write_client_name(conn, table_code, "")

        # Clear in-memory + update UI
        o.status = "paid"
        self.orders.pop(table_code, None)
        self._apply_client_name(table_code, "")
        bus.emit("table_state_changed", table_code, "free")
        bus.emit("table_total_changed", table_code, 0)
        bus.emit("ps_state_changed", table_code, False)
        return True

    def load_ps_session_from_db(self, table_code: str) -> Optional[PSSession]:
        """Load PS session from database for a table."""
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT table_code, mode, started_at, total_seconds FROM ps_sessions WHERE table_code=?",
            (table_code,)
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        # Convert database row to PSSession object
        started_raw = row["started_at"] or ""
        try:
            started_at = datetime.fromisoformat(started_raw)
        except Exception:
            started_at = datetime.utcnow()

        return PSSession(
            mode=row["mode"],
            started_at=started_at,
            total_seconds=int(row["total_seconds"] or 0),
        )


# --- keep this at the VERY END of the file ---
order_manager = OrderManager()


def default_table_codes() -> List[str]:
    return _default_table_codes()


def get_table_codes() -> List[str]:
    return order_manager.get_table_codes()


def set_table_codes(codes: List[str], *, actor: str = "system") -> List[str]:
    return order_manager.set_table_codes(codes, actor=actor)
# Add these function exports at the end of orders.py, after the order_manager instance

def get_table_history(
    conn,
    table_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    q: str | None = None,
    *,
    limit: int = 100,
    offset: int = 0,
):
    """Return historical closed orders for *table_id*.

    Results include paid and void orders. Date filtering is applied using UTC
    timestamps (ISO8601 strings stored in the database). Free-text search is
    matched against the order id, cashier name, and discount reason (used as a
    note field).
    """

    limit = max(1, int(limit or 1))
    offset = max(0, int(offset or 0))

    filters: list[str] = []
    params: list = [table_id]

    if date_from:
        filters.append("COALESCE(paid_at, closed_at, opened_at) >= ?")
        params.append(date_from)
    if date_to:
        filters.append("COALESCE(paid_at, closed_at, opened_at) <= ?")
        params.append(date_to)
    if q:
        term = f"%{q.strip()}%"
        filters.append(
            "(CAST(order_id AS TEXT) LIKE ? OR "
            "UPPER(COALESCE(cashier, '')) LIKE UPPER(?) OR "
            "UPPER(COALESCE(note, '')) LIKE UPPER(?))"
        )
        params.extend([term, term, term])

    where_clause = " AND ".join(filters) if filters else "1=1"

    query = f"""
        WITH base AS (
            SELECT
                o.id AS order_id,
                o.table_code,
                o.opened_at,
                o.closed_at,
                CAST(COALESCE(o.discount_cents, 0) AS INTEGER) AS discount_cents,
                COALESCE(o.discount_reason, '') AS note,
                CAST(ROUND(COALESCE(SUM(oi.price_cents * oi.qty), 0)) AS INTEGER) AS subtotal_cents,
                COALESCE(SUM(oi.qty), 0) AS items_count,
                MAX(p.paid_at) AS paid_at,
                MAX(p.cashier) AS cashier,
                MAX(COALESCE(NULLIF(o.client_name, ''), tc.client_name, '')) AS client_name
            FROM orders o
            LEFT JOIN order_items oi ON oi.order_id = o.id
            LEFT JOIN payments p ON p.order_id = o.id
            LEFT JOIN table_clients tc ON tc.table_code = UPPER(o.table_code)
            WHERE o.table_code = ?
              AND o.status IN ('paid', 'void')
            GROUP BY o.id
        )
        SELECT
            order_id,
            opened_at,
            paid_at,
            closed_at,
            subtotal_cents,
            discount_cents,
            note,
            cashier,
            items_count,
            client_name,
            CASE
                WHEN subtotal_cents > discount_cents THEN subtotal_cents - discount_cents
                ELSE 0
            END AS total_cents
        FROM base
        WHERE {where_clause}
        ORDER BY COALESCE(paid_at, closed_at, opened_at) DESC, order_id DESC
        LIMIT ? OFFSET ?
    """

    cur = conn.cursor()
    rows = cur.execute(query, (*params, limit, offset)).fetchall()
    result = []
    for row in rows:
        result.append(
            {
                "order_id": int(row["order_id"]),
                "opened_at": row["opened_at"],
                "paid_at": row["paid_at"],
                "closed_at": row["closed_at"],
                "subtotal_cents": int(row["subtotal_cents"] or 0),
                "discount_cents": int(row["discount_cents"] or 0),
                "total_cents": int(row["total_cents"] or 0),
                "cashier": row["cashier"],
                "items_count": float(row["items_count"] or 0),
                "note": row["note"],
                "client_name": row["client_name"],
            }
        )
    return result


def load_order_by_id(order_id: int) -> dict | None:
    """Return a lightweight dict for a historical order (paid/void).
    Similar shape to get_table_history() rows but includes order_items rows with id so we can edit.
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, table_code, opened_at, closed_at,
               COALESCE(client_name,'') as client_name,
               COALESCE(discount_cents,0) as discount_cents,
               COALESCE(discount_reason,'') as discount_reason,
               COALESCE(discount_type,'amount') as discount_type,
               COALESCE(discount_value,0) as discount_value,
               paid_at, editable_until
        FROM orders
        WHERE id=?
        """,
        (order_id,),
    )
    o = cur.fetchone()
    if not o:
        conn.close()
        return None

    cur.execute(
        "SELECT id, product_name, price_cents, qty, COALESCE(note,'') as note, COALESCE(printed_qty,0) as printed_qty "
        "FROM order_items WHERE order_id=? ORDER BY id",
        (order_id,),
    )
    items = [
        {
            "row_id": r["id"],
            "product": r["product_name"],
            "unit_price_cents": int(r["price_cents"]),
            "qty": float(r["qty"]),
            "note": r["note"],
            "printed_qty": float(r["printed_qty"]),
        }
        for r in cur.fetchall()
    ]
    conn.close()
    return {
        "id": int(o["id"]),
        "table_code": o["table_code"],
        "opened_at": o["opened_at"],
        "closed_at": o["closed_at"],
        "client_name": o["client_name"],
        "discount_cents": int(o["discount_cents"]),
        "discount_reason": o["discount_reason"],
        "discount_type": o["discount_type"],
        "discount_value": float(o["discount_value"]),
        "paid_at": o["paid_at"],
        "editable_until": o["editable_until"],
        "items": items,
    }


def _parse_iso_dt(v: str | None):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v))
    except Exception:
        return None


def edit_historical_order_item(order_id: int, row_id: int, qty: float, note: str, username: str = "system") -> bool:
    """Edit order_items.id==row_id for a historical order (must be within editable window).
    Returns True if updated, False if validation prevents update.
    Raises OrderError on DB/logic failures.
    """
    # load order header and editable_until
    o = load_order_by_id(order_id)
    if not o:
        raise OrderError("الطلب غير موجود")

    # Check editable window
    if o.get("editable_until") is not None:
        editable_until = _parse_iso_dt(o["editable_until"])
        if not ALLOW_LATE_EDIT_OVERRIDE:
            now = datetime.utcnow()
            if editable_until is None or now > editable_until:
                raise EditWindowError()  # same error used for open orders
    else:
        # no editable window on this historic order
        raise EditWindowError()

    # Validate qty
    qty_val = float(qty)
    if qty_val <= 0:
        # if qty <= 0 treat as delete of the item: delete row
        with db_transaction() as conn:
            conn.execute("DELETE FROM order_items WHERE id=?", (row_id,))
        # recalc payments/totals is out-of-scope here — UI should warn if needed
        bus.emit("ui_texts_changed")  # nudge UI re-synch if desired
        return True

    # Before applying, ensure stock constraints if product is tracked
    # get product name for row
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT product_name, price_cents, qty, printed_qty FROM order_items WHERE id=?", (row_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise OrderError("بند الطلب غير موجود")
    product_name = row["product_name"]
    old_qty = float(row["qty"] or 0.0)
    printed_qty = float(row["printed_qty"] or 0.0)
    # If new qty < printed_qty, refuse (can't reduce below printed)
    if qty_val < printed_qty - 1e-6:
        conn.close()
        raise OrderError("لا يمكن تقليل الكمية تحت كمية المطبوع")

    # handle stock adjustments if product tracks stock (similar logic to update_item)
    prod = None
    try:
        prod = OrderManager().catalog.get_product(product_name)  # lightweight catalog access
    except Exception:
        prod = None

    try:
        with db_transaction() as tx:
            # if tracked and qty increases -> dec_stock, if decreases -> inc_stock
            delta = qty_val - old_qty
            if prod and prod.get("track_stock") == 1:
                if delta > 0:
                    # check available
                    before = float(prod["stock_qty"] or 0.0)
                    if before < delta - 1e-6:
                        raise StockError(f"المنتج '{product_name}' غير متوفر بالكميات المطلوبة")
                    # decrement
                    OrderManager().catalog.dec_stock(product_name, delta, conn=tx)
                elif delta < 0:
                    OrderManager().catalog.inc_stock(product_name, -delta, conn=tx)

            # persist change
            tx.execute("UPDATE order_items SET qty=?, note=? WHERE id=?", (qty_val, str(note or ""), row_id))
    except Exception as e:
        raise OrderError(f"تعذر تعديل بند الطلب: {e}")

    # optionally emit an event so UI/listeners can refresh relevant screens
    bus.emit("tables_changed", OrderManager().get_table_codes())
    return True