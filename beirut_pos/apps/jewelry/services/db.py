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
    conn.commit()
    conn.close()

    _ensure_default_payment_methods()


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


def list_products() -> List[JewelryProduct]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, name_ar, name_en, sku, price, qty_on_hand, min_qty, category,
                  handmade_flag, stone_type, color
           FROM jw_products ORDER BY id DESC"""
    )
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryProduct(
            id=row[0],
            name_ar=row[1],
            name_en=row[2],
            sku=row[3],
            price=row[4],
            qty_on_hand=row[5],
            min_qty=row[6],
            category=row[7],
            handmade_flag=bool(row[8]),
            stone_type=row[9],
            color=row[10],
        )
        for row in rows
    ]


def save_product(
    product_id: Optional[int],
    name_ar: str,
    name_en: str,
    sku: str,
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
               SET name_ar=?, name_en=?, sku=?, price=?, qty_on_hand=?, min_qty=?,
                   category=?, handmade_flag=?, stone_type=?, color=?
               WHERE id=?""",
            (
                name_ar,
                name_en,
                sku,
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
               (name_ar, name_en, sku, price, qty_on_hand, min_qty, category,
                handmade_flag, stone_type, color)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                name_ar,
                name_en,
                sku,
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


def delete_product(product_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM jw_products WHERE id = ?", (product_id,))
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
