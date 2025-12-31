"""SQLite helpers for Jewelry app data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

from beirut_pos.core.db import get_conn


@dataclass
class JewelryProduct:
    id: int
    name_ar: str
    name_en: str
    sku: str
    barcode: str
    barcode_type: str
    price: float
    qty_on_hand: float
    min_qty: float
    category: str
    handmade_flag: bool
    stone_type: str
    color: str


@dataclass
class JewelryInvoiceItem:
    product_id: int
    product_name: str
    product_code: str
    qty: float
    unit_price: float
    line_total: float


@dataclass
class JewelryInvoice:
    invoice_no: str
    datetime: str
    cashier_name: str
    txn_type: str
    subtotal: float
    discount: float
    total: float
    payment_method: str
    notes: str
    return_reason: str


@dataclass
class JewelryMaterial:
    id: int
    name_ar: str
    name_en: str
    code: str
    qty_on_hand: float
    unit: str
    min_qty: float
    cost_per_unit: float


@dataclass
class JewelryBom:
    id: int
    product_id: int
    name: str
    active: bool


@dataclass
class JewelryBomLine:
    id: int
    bom_id: int
    material_id: int
    qty_required: float


@dataclass
class JewelryProductionOrder:
    id: int
    order_no: str
    datetime: str
    status: str
    product_id: int
    qty_to_produce: float
    qty_produced: float
    labor_cost: float
    overhead_cost: float
    notes: str
    bom_id: Optional[int]


def init_jewelry_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL,
            sku TEXT NOT NULL UNIQUE,
            price REAL NOT NULL,
            qty_on_hand REAL NOT NULL DEFAULT 0,
            min_qty REAL NOT NULL DEFAULT 0,
            category TEXT DEFAULT '',
            handmade_flag INTEGER NOT NULL DEFAULT 0,
            stone_type TEXT DEFAULT '',
            color TEXT DEFAULT ''
        )"""
    )
    _ensure_column(cur, "jw_products", "barcode", "TEXT")
    _ensure_column(cur, "jw_products", "barcode_type", "TEXT")
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_payment_methods(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(name_ar, name_en)
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )"""
    )
    _ensure_column(cur, "jw_users", "username", "TEXT")
    _ensure_column(cur, "jw_users", "password_hash", "TEXT")
    _ensure_column(cur, "jw_users", "full_name", "TEXT")
    _ensure_column(cur, "jw_users", "role", "TEXT")
    _ensure_column(cur, "jw_users", "is_active", "INTEGER")
    _ensure_column(cur, "jw_users", "created_at", "TEXT")
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_login_audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            success INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL UNIQUE,
            datetime TEXT NOT NULL,
            cashier_name TEXT NOT NULL,
            txn_type TEXT NOT NULL CHECK(txn_type in ('sale','return')),
            subtotal REAL NOT NULL,
            discount REAL NOT NULL,
            total REAL NOT NULL,
            payment_method TEXT NOT NULL,
            notes TEXT DEFAULT '',
            return_reason TEXT DEFAULT ''
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_invoice_items(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            product_code TEXT NOT NULL,
            qty REAL NOT NULL,
            unit_price REAL NOT NULL,
            line_total REAL NOT NULL,
            FOREIGN KEY(invoice_id) REFERENCES jw_invoices(id)
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_shift_sessions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cashier TEXT NOT NULL,
            open_time TEXT NOT NULL,
            close_time TEXT NOT NULL,
            opening_cash REAL NOT NULL DEFAULT 0,
            closing_cash_actual REAL NOT NULL DEFAULT 0,
            notes TEXT DEFAULT ''
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_materials(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            qty_on_hand REAL NOT NULL DEFAULT 0,
            unit TEXT DEFAULT '',
            min_qty REAL NOT NULL DEFAULT 0,
            cost_per_unit REAL NOT NULL DEFAULT 0
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_boms(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY(product_id) REFERENCES jw_products(id)
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_bom_lines(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bom_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            qty_required REAL NOT NULL,
            FOREIGN KEY(bom_id) REFERENCES jw_boms(id),
            FOREIGN KEY(material_id) REFERENCES jw_materials(id)
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_production_orders(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT NOT NULL UNIQUE,
            datetime TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status in ('draft','confirmed','done','cancelled')),
            product_id INTEGER NOT NULL,
            qty_to_produce REAL NOT NULL,
            qty_produced REAL NOT NULL DEFAULT 0,
            labor_cost REAL NOT NULL DEFAULT 0,
            overhead_cost REAL NOT NULL DEFAULT 0,
            notes TEXT DEFAULT '',
            bom_id INTEGER,
            FOREIGN KEY(product_id) REFERENCES jw_products(id)
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_production_consumption(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_order_id INTEGER NOT NULL,
            material_id INTEGER NOT NULL,
            qty_consumed REAL NOT NULL,
            cost_at_time REAL NOT NULL,
            FOREIGN KEY(production_order_id) REFERENCES jw_production_orders(id),
            FOREIGN KEY(material_id) REFERENCES jw_materials(id)
        )"""
    )
    _ensure_column(cur, "jw_production_orders", "bom_id", "INTEGER")
    try:
        cur.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS jw_products_barcode_unique
               ON jw_products(barcode)
               WHERE barcode IS NOT NULL AND barcode != ''"""
        )
    except Exception:
        pass
    conn.commit()
    conn.close()

    _ensure_default_payment_methods()
    _ensure_default_user()


def _ensure_default_payment_methods() -> None:
    defaults = [
        ("نقدًا", "Cash"),
        ("إنستاباي", "Instapay"),
        ("فودافون كاش", "Vodafone Cash"),
    ]
    conn = get_conn()
    cur = conn.cursor()
    for name_ar, name_en in defaults:
        cur.execute(
            """INSERT OR IGNORE INTO jw_payment_methods(name_ar, name_en, active)
               VALUES (?, ?, 1)""",
            (name_ar, name_en),
        )
    conn.commit()
    conn.close()


def _ensure_default_user() -> None:
    from .auth import ensure_default_admin, get_default_admin_warning
    from .session import set_bootstrap_warning

    ensure_default_admin()
    warning = get_default_admin_warning()
    if warning:
        set_bootstrap_warning(warning)


def _ensure_column(cur, table: str, column: str, column_type: str) -> None:
    cur.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cur.fetchall()}
    if column not in columns:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def list_payment_methods() -> List[Tuple[int, str, str]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name_ar, name_en FROM jw_payment_methods WHERE active = 1 ORDER BY id"
    )
    rows = cur.fetchall()
    conn.close()
    return [(row[0], row[1], row[2]) for row in rows]


def add_payment_method(name_ar: str, name_en: str) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT OR IGNORE INTO jw_payment_methods(name_ar, name_en, active)
           VALUES (?, ?, 1)""",
        (name_ar.strip(), name_en.strip()),
    )
    conn.commit()
    conn.close()


def list_products(search: Optional[str] = None) -> List[JewelryProduct]:
    conn = get_conn()
    cur = conn.cursor()
    params: Tuple[str, ...] = ()
    query = """SELECT id, name_ar, name_en, sku, COALESCE(barcode, ''), COALESCE(barcode_type, ''),
                      price, qty_on_hand, min_qty, category, handmade_flag, stone_type, color
               FROM jw_products"""
    if search:
        query += " WHERE name_ar LIKE ? OR name_en LIKE ? OR sku LIKE ? OR barcode LIKE ?"
        like = f"%{search}%"
        params = (like, like, like, like)
    query += " ORDER BY id DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryProduct(
            id=row[0],
            name_ar=row[1],
            name_en=row[2],
            sku=row[3],
            barcode=row[4] or "",
            barcode_type=row[5] or "",
            price=row[6],
            qty_on_hand=row[7],
            min_qty=row[8],
            category=row[9],
            handmade_flag=bool(row[10]),
            stone_type=row[11],
            color=row[12],
        )
        for row in rows
    ]


def save_product(
    product_id: Optional[int],
    name_ar: str,
    name_en: str,
    sku: str,
    barcode: str,
    barcode_type: str,
    price: float,
    qty_on_hand: float,
    min_qty: float,
    category: str,
    handmade_flag: bool,
    stone_type: str,
    color: str,
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    if product_id:
        cur.execute(
            """UPDATE jw_products
               SET name_ar=?, name_en=?, sku=?, barcode=?, barcode_type=?, price=?,
                   qty_on_hand=?, min_qty=?, category=?, handmade_flag=?,
                   stone_type=?, color=?
               WHERE id=?""",
            (
                name_ar,
                name_en,
                sku,
                barcode,
                barcode_type,
                price,
                qty_on_hand,
                min_qty,
                category,
                1 if handmade_flag else 0,
                stone_type,
                color,
                product_id,
            ),
        )
    else:
        cur.execute(
            """INSERT INTO jw_products
               (name_ar, name_en, sku, barcode, barcode_type, price, qty_on_hand,
                min_qty, category, handmade_flag, stone_type, color)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name_ar,
                name_en,
                sku,
                barcode,
                barcode_type,
                price,
                qty_on_hand,
                min_qty,
                category,
                1 if handmade_flag else 0,
                stone_type,
                color,
            ),
        )
    conn.commit()
    conn.close()


def barcode_exists(barcode: str, *, exclude_product_id: Optional[int] = None) -> bool:
    if not barcode:
        return False
    conn = get_conn()
    cur = conn.cursor()
    if exclude_product_id:
        cur.execute(
            "SELECT 1 FROM jw_products WHERE barcode = ? AND id != ? LIMIT 1",
            (barcode, exclude_product_id),
        )
    else:
        cur.execute("SELECT 1 FROM jw_products WHERE barcode = ? LIMIT 1", (barcode,))
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def find_product_by_code(code: str) -> Optional[JewelryProduct]:
    if not code:
        return None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, name_ar, name_en, sku, COALESCE(barcode, ''), COALESCE(barcode_type, ''),
                  price, qty_on_hand, min_qty, category, handmade_flag, stone_type, color
           FROM jw_products
           WHERE sku = ? OR barcode = ?
           LIMIT 1""",
        (code, code),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return JewelryProduct(
        id=row[0],
        name_ar=row[1],
        name_en=row[2],
        sku=row[3],
        barcode=row[4] or "",
        barcode_type=row[5] or "",
        price=row[6],
        qty_on_hand=row[7],
        min_qty=row[8],
        category=row[9],
        handmade_flag=bool(row[10]),
        stone_type=row[11],
        color=row[12],
    )


def delete_product(product_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM jw_products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def list_materials() -> List[JewelryMaterial]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, name_ar, name_en, code, qty_on_hand, unit, min_qty, cost_per_unit
           FROM jw_materials ORDER BY id DESC"""
    )
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryMaterial(
            id=row[0],
            name_ar=row[1],
            name_en=row[2],
            code=row[3],
            qty_on_hand=row[4],
            unit=row[5],
            min_qty=row[6],
            cost_per_unit=row[7],
        )
        for row in rows
    ]


def save_material(
    material_id: Optional[int],
    name_ar: str,
    name_en: str,
    code: str,
    qty_on_hand: float,
    unit: str,
    min_qty: float,
    cost_per_unit: float,
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    if material_id:
        cur.execute(
            """UPDATE jw_materials
               SET name_ar=?, name_en=?, code=?, qty_on_hand=?, unit=?, min_qty=?, cost_per_unit=?
               WHERE id=?""",
            (
                name_ar,
                name_en,
                code,
                qty_on_hand,
                unit,
                min_qty,
                cost_per_unit,
                material_id,
            ),
        )
    else:
        cur.execute(
            """INSERT INTO jw_materials
               (name_ar, name_en, code, qty_on_hand, unit, min_qty, cost_per_unit)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                name_ar,
                name_en,
                code,
                qty_on_hand,
                unit,
                min_qty,
                cost_per_unit,
            ),
        )
    conn.commit()
    conn.close()


def delete_material(material_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM jw_materials WHERE id = ?", (material_id,))
    conn.commit()
    conn.close()


def list_boms() -> List[JewelryBom]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, product_id, name, active
           FROM jw_boms ORDER BY id DESC"""
    )
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryBom(
            id=row[0],
            product_id=row[1],
            name=row[2],
            active=bool(row[3]),
        )
        for row in rows
    ]


def list_bom_lines(bom_id: int) -> List[JewelryBomLine]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, bom_id, material_id, qty_required
           FROM jw_bom_lines WHERE bom_id = ? ORDER BY id""",
        (bom_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryBomLine(
            id=row[0],
            bom_id=row[1],
            material_id=row[2],
            qty_required=row[3],
        )
        for row in rows
    ]


def save_bom(
    bom_id: Optional[int],
    product_id: int,
    name: str,
    active: bool,
    lines: Iterable[Tuple[int, float]],
) -> int:
    conn = get_conn()
    cur = conn.cursor()
    if bom_id:
        cur.execute(
            """UPDATE jw_boms
               SET product_id=?, name=?, active=?
               WHERE id=?""",
            (product_id, name, 1 if active else 0, bom_id),
        )
        cur.execute("DELETE FROM jw_bom_lines WHERE bom_id = ?", (bom_id,))
        bom_row_id = bom_id
    else:
        cur.execute(
            """INSERT INTO jw_boms(product_id, name, active)
               VALUES (?, ?, ?)""",
            (product_id, name, 1 if active else 0),
        )
        bom_row_id = cur.lastrowid
    for material_id, qty_required in lines:
        cur.execute(
            """INSERT INTO jw_bom_lines(bom_id, material_id, qty_required)
               VALUES (?, ?, ?)""",
            (bom_row_id, material_id, qty_required),
        )
    conn.commit()
    conn.close()
    return int(bom_row_id)


def delete_bom(bom_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM jw_bom_lines WHERE bom_id = ?", (bom_id,))
    cur.execute("DELETE FROM jw_boms WHERE id = ?", (bom_id,))
    conn.commit()
    conn.close()


def _next_production_order_no(cur) -> str:
    cur.execute("SELECT MAX(id) FROM jw_production_orders")
    max_id = cur.fetchone()[0] or 0
    return f"JWO-{max_id + 1:05d}"


def create_production_order(
    product_id: int,
    qty_to_produce: float,
    labor_cost: float,
    overhead_cost: float,
    notes: str,
    bom_id: Optional[int],
) -> JewelryProductionOrder:
    conn = get_conn()
    cur = conn.cursor()
    order_no = _next_production_order_no(cur)
    order_datetime = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO jw_production_orders
           (order_no, datetime, status, product_id, qty_to_produce, qty_produced,
            labor_cost, overhead_cost, notes, bom_id)
           VALUES (?, ?, 'draft', ?, ?, 0, ?, ?, ?, ?)""",
        (
            order_no,
            order_datetime,
            product_id,
            qty_to_produce,
            labor_cost,
            overhead_cost,
            notes,
            bom_id,
        ),
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return JewelryProductionOrder(
        id=order_id,
        order_no=order_no,
        datetime=order_datetime,
        status="draft",
        product_id=product_id,
        qty_to_produce=qty_to_produce,
        qty_produced=0.0,
        labor_cost=labor_cost,
        overhead_cost=overhead_cost,
        notes=notes,
        bom_id=bom_id,
    )


def list_production_orders(
    start_iso: Optional[str] = None,
    end_iso: Optional[str] = None,
    status: Optional[str] = None,
    product_id: Optional[int] = None,
) -> List[JewelryProductionOrder]:
    conn = get_conn()
    cur = conn.cursor()
    query = """SELECT id, order_no, datetime, status, product_id, qty_to_produce,
                      qty_produced, labor_cost, overhead_cost, notes, bom_id
               FROM jw_production_orders"""
    params: List = []
    conditions = []
    if start_iso and end_iso:
        conditions.append("datetime BETWEEN ? AND ?")
        params.extend([start_iso, end_iso])
    if status and status != "all":
        conditions.append("status = ?")
        params.append(status)
    if product_id:
        conditions.append("product_id = ?")
        params.append(product_id)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY datetime DESC"
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryProductionOrder(
            id=row[0],
            order_no=row[1],
            datetime=row[2],
            status=row[3],
            product_id=row[4],
            qty_to_produce=row[5],
            qty_produced=row[6],
            labor_cost=row[7],
            overhead_cost=row[8],
            notes=row[9],
            bom_id=row[10],
        )
        for row in rows
    ]


def fetch_production_order(order_id: int) -> Optional[JewelryProductionOrder]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, order_no, datetime, status, product_id, qty_to_produce,
                  qty_produced, labor_cost, overhead_cost, notes, bom_id
           FROM jw_production_orders WHERE id = ?""",
        (order_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return JewelryProductionOrder(
        id=row[0],
        order_no=row[1],
        datetime=row[2],
        status=row[3],
        product_id=row[4],
        qty_to_produce=row[5],
        qty_produced=row[6],
        labor_cost=row[7],
        overhead_cost=row[8],
        notes=row[9],
        bom_id=row[10],
    )


def check_material_availability(bom_id: int, qty_multiplier: float) -> List[Tuple[str, float, float]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT m.name_en, m.qty_on_hand, l.qty_required
           FROM jw_bom_lines l
           JOIN jw_materials m ON m.id = l.material_id
           WHERE l.bom_id = ?""",
        (bom_id,),
    )
    rows = cur.fetchall()
    conn.close()
    shortages = []
    for name_en, qty_on_hand, qty_required in rows:
        required_total = qty_required * qty_multiplier
        if qty_on_hand < required_total:
            shortages.append((name_en, qty_on_hand, required_total))
    return shortages


def confirm_production_order(order_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT status, bom_id, qty_to_produce FROM jw_production_orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError("Order not found")
    status, bom_id, qty_to_produce = row
    if status != "draft":
        conn.close()
        return
    if bom_id:
        shortages = check_material_availability(bom_id, qty_to_produce)
        if shortages:
            conn.close()
            raise ValueError("Insufficient materials")
    cur.execute(
        "UPDATE jw_production_orders SET status = 'confirmed' WHERE id = ?",
        (order_id,),
    )
    conn.commit()
    conn.close()


def mark_production_done(order_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT status, product_id, qty_to_produce, bom_id, labor_cost, overhead_cost
           FROM jw_production_orders WHERE id = ?""",
        (order_id,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError("Order not found")
    status, product_id, qty_to_produce, bom_id, labor_cost, overhead_cost = row
    if status == "done":
        conn.close()
        return
    if bom_id:
        cur.execute(
            """SELECT material_id, qty_required
               FROM jw_bom_lines WHERE bom_id = ?""",
            (bom_id,),
        )
        lines = cur.fetchall()
        for material_id, qty_required in lines:
            cur.execute(
                "SELECT qty_on_hand, cost_per_unit FROM jw_materials WHERE id = ?",
                (material_id,),
            )
            material_row = cur.fetchone()
            if not material_row:
                conn.close()
                raise ValueError("Material missing")
            qty_on_hand, cost_per_unit = material_row
            total_required = qty_required * qty_to_produce
            if qty_on_hand < total_required:
                conn.close()
                raise ValueError("Insufficient materials")
            cur.execute(
                "UPDATE jw_materials SET qty_on_hand = qty_on_hand - ? WHERE id = ?",
                (total_required, material_id),
            )
            cur.execute(
                """INSERT INTO jw_production_consumption
                   (production_order_id, material_id, qty_consumed, cost_at_time)
                   VALUES (?, ?, ?, ?)""",
                (order_id, material_id, total_required, cost_per_unit),
            )
    cur.execute(
        "UPDATE jw_products SET qty_on_hand = qty_on_hand + ? WHERE id = ?",
        (qty_to_produce, product_id),
    )
    cur.execute(
        """UPDATE jw_production_orders
           SET status = 'done', qty_produced = ?, labor_cost = ?, overhead_cost = ?
           WHERE id = ?""",
        (qty_to_produce, labor_cost, overhead_cost, order_id),
    )
    conn.commit()
    conn.close()


def _next_invoice_no(cur) -> str:
    cur.execute("SELECT MAX(id) FROM jw_invoices")
    max_id = cur.fetchone()[0] or 0
    return f"JINV-{max_id + 1:05d}"


def create_invoice(
    cashier_name: str,
    txn_type: str,
    subtotal: float,
    discount: float,
    total: float,
    payment_method: str,
    notes: str,
    return_reason: str,
    items: Iterable[JewelryInvoiceItem],
) -> str:
    invoice_datetime = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    cur = conn.cursor()
    invoice_no = _next_invoice_no(cur)
    cur.execute(
        """INSERT INTO jw_invoices
           (invoice_no, datetime, cashier_name, txn_type, subtotal, discount,
            total, payment_method, notes, return_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            invoice_no,
            invoice_datetime,
            cashier_name,
            txn_type,
            subtotal,
            discount,
            total,
            payment_method,
            notes,
            return_reason,
        ),
    )
    invoice_id = cur.lastrowid
    for item in items:
        cur.execute(
            """INSERT INTO jw_invoice_items
               (invoice_id, product_id, product_name, product_code, qty, unit_price, line_total)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                invoice_id,
                item.product_id,
                item.product_name,
                item.product_code,
                item.qty,
                item.unit_price,
                item.line_total,
            ),
        )
        _apply_stock_adjustment(cur, item.product_id, item.qty, txn_type)
    conn.commit()
    conn.close()
    return invoice_no


def _apply_stock_adjustment(cur, product_id: int, qty: float, txn_type: str) -> None:
    if not product_id:
        return
    if txn_type == "sale":
        cur.execute(
            "UPDATE jw_products SET qty_on_hand = qty_on_hand - ? WHERE id = ?",
            (qty, product_id),
        )
    else:
        cur.execute(
            "UPDATE jw_products SET qty_on_hand = qty_on_hand + ? WHERE id = ?",
            (qty, product_id),
        )


def list_return_invoices(date_iso: Optional[str] = None) -> List[JewelryInvoice]:
    conn = get_conn()
    cur = conn.cursor()
    params: Tuple[str, ...] = ()
    query = """SELECT invoice_no, datetime, cashier_name, txn_type, subtotal,
                      discount, total, payment_method, notes, return_reason
               FROM jw_invoices WHERE txn_type = 'return'"""
    if date_iso:
        query += " AND date(datetime) = date(?)"
        params = (date_iso,)
    query += " ORDER BY datetime DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryInvoice(
            invoice_no=row[0],
            datetime=row[1],
            cashier_name=row[2],
            txn_type=row[3],
            subtotal=row[4],
            discount=row[5],
            total=row[6],
            payment_method=row[7],
            notes=row[8],
            return_reason=row[9],
        )
        for row in rows
    ]


def fetch_invoice_details(invoice_no: str) -> Tuple[JewelryInvoice, List[JewelryInvoiceItem]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT invoice_no, datetime, cashier_name, txn_type, subtotal,
                  discount, total, payment_method, notes, return_reason
           FROM jw_invoices WHERE invoice_no = ?""",
        (invoice_no,),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError("Invoice not found")
    invoice = JewelryInvoice(
        invoice_no=row[0],
        datetime=row[1],
        cashier_name=row[2],
        txn_type=row[3],
        subtotal=row[4],
        discount=row[5],
        total=row[6],
        payment_method=row[7],
        notes=row[8],
        return_reason=row[9],
    )
    cur.execute(
        """SELECT product_id, product_name, product_code, qty, unit_price, line_total
           FROM jw_invoice_items
           WHERE invoice_id = (SELECT id FROM jw_invoices WHERE invoice_no = ?)
           ORDER BY id""",
        (invoice_no,),
    )
    items_rows = cur.fetchall()
    conn.close()
    items = [
        JewelryInvoiceItem(
            product_id=row[0],
            product_name=row[1],
            product_code=row[2],
            qty=row[3],
            unit_price=row[4],
            line_total=row[5],
        )
        for row in items_rows
    ]
    return invoice, items


def save_shift_session(
    cashier: str,
    open_time: str,
    close_time: str,
    opening_cash: float,
    closing_cash_actual: float,
    notes: str,
) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO jw_shift_sessions
           (cashier, open_time, close_time, opening_cash, closing_cash_actual, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (cashier, open_time, close_time, opening_cash, closing_cash_actual, notes),
    )
    conn.commit()
    conn.close()


def fetch_shift_session_for_date(date_iso: str) -> Optional[Tuple]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT cashier, open_time, close_time, opening_cash, closing_cash_actual, notes
           FROM jw_shift_sessions
           WHERE date(open_time) = date(?)
           ORDER BY id DESC LIMIT 1""",
        (date_iso,),
    )
    row = cur.fetchone()
    conn.close()
    return row
