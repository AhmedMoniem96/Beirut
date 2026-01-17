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
    discount_type: str
    discount_value: float
    total: float
    payment_method: str
    notes: str
    return_reason: str
    loyalty_earned: float = 0.0
    loyalty_redeemed: float = 0.0
    order_source: str = "in_store"
    website_order_ref: str = ""
    customer_id: Optional[int] = None
    customer_name: str = ""
    customer_phone: str = ""


@dataclass
class JewelryCustomer:
    phone: str
    name: str
    email: str
    created_at: str


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


@dataclass
class JewelryPaymentRow:
    id: int
    invoice_id: int
    payment_method: str
    amount: float
    paid_at: str
    cashier_name: str
    notes: str


@dataclass
class JewelryDeliveryCompany:
    id: int
    name: str
    company_type: str
    phone: str
    active: bool


@dataclass
class JewelryStatusItem:
    id: int
    status_group: str
    name_ar: str
    name_en: str
    sort_order: int
    active: bool


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
        """CREATE TABLE IF NOT EXISTS jw_delivery_companies(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            company_type TEXT NOT NULL,
            phone TEXT DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_statuses(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status_group TEXT NOT NULL CHECK(status_group in ('DELIVERY', 'PAYMENT')),
            name_ar TEXT NOT NULL,
            name_en TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            UNIQUE(status_group, name_ar, name_en)
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL UNIQUE,
            datetime TEXT NOT NULL,
            cashier_name TEXT NOT NULL,
            txn_type TEXT NOT NULL CHECK(txn_type in ('sale','return')),
            customer_id TEXT,
            customer_name TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            subtotal REAL NOT NULL,
            discount REAL NOT NULL,
            discount_type TEXT NOT NULL DEFAULT 'amount',
            discount_value REAL NOT NULL DEFAULT 0,
            loyalty_earned REAL NOT NULL DEFAULT 0,
            loyalty_redeemed REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL,
            paid_total REAL NOT NULL DEFAULT 0,
            remaining_total REAL NOT NULL DEFAULT 0,
            payment_status TEXT DEFAULT '',
            payment_due_date TEXT,
            payment_order_status_id INTEGER,
            payment_method TEXT NOT NULL,
            order_source TEXT NOT NULL DEFAULT 'in_store',
            website_order_ref TEXT DEFAULT '',
            delivery_enabled INTEGER NOT NULL DEFAULT 0,
            delivery_company_id INTEGER,
            delivery_fee REAL NOT NULL DEFAULT 0,
            delivery_address TEXT DEFAULT '',
            delivery_status_id INTEGER,
            notes TEXT DEFAULT '',
            return_reason TEXT DEFAULT '',
            FOREIGN KEY(customer_id) REFERENCES jw_customers(phone),
            FOREIGN KEY(delivery_company_id) REFERENCES jw_delivery_companies(id),
            FOREIGN KEY(payment_order_status_id) REFERENCES jw_statuses(id),
            FOREIGN KEY(delivery_status_id) REFERENCES jw_statuses(id)
        )"""
    )
    _ensure_column(cur, "jw_invoices", "discount_type", "TEXT DEFAULT 'amount'")
    _ensure_column(cur, "jw_invoices", "discount_value", "REAL DEFAULT 0")
    _ensure_column(cur, "jw_invoices", "customer_id", "TEXT")
    _ensure_column(cur, "jw_invoices", "customer_name", "TEXT DEFAULT ''")
    _ensure_column(cur, "jw_invoices", "customer_phone", "TEXT DEFAULT ''")
    _ensure_column(cur, "jw_invoices", "loyalty_earned", "REAL NOT NULL DEFAULT 0")
    _ensure_column(cur, "jw_invoices", "loyalty_redeemed", "REAL NOT NULL DEFAULT 0")
    _ensure_column(cur, "jw_invoices", "order_source", "TEXT NOT NULL DEFAULT 'in_store'")
    _ensure_column(cur, "jw_invoices", "website_order_ref", "TEXT DEFAULT ''")
    _ensure_column(cur, "jw_invoices", "paid_total", "REAL NOT NULL DEFAULT 0")
    _ensure_column(cur, "jw_invoices", "remaining_total", "REAL NOT NULL DEFAULT 0")
    _ensure_column(cur, "jw_invoices", "payment_status", "TEXT DEFAULT ''")
    _ensure_column(cur, "jw_invoices", "payment_due_date", "TEXT")
    _ensure_column(cur, "jw_invoices", "payment_order_status_id", "INTEGER")
    _ensure_column(cur, "jw_invoices", "delivery_enabled", "INTEGER NOT NULL DEFAULT 0")
    _ensure_column(cur, "jw_invoices", "delivery_company_id", "INTEGER")
    _ensure_column(cur, "jw_invoices", "delivery_fee", "REAL NOT NULL DEFAULT 0")
    _ensure_column(cur, "jw_invoices", "delivery_address", "TEXT DEFAULT ''")
    _ensure_column(cur, "jw_invoices", "delivery_status_id", "INTEGER")
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_customers(
            phone TEXT NOT NULL PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        )"""
    )
    _ensure_column(cur, "jw_customers", "email", "TEXT NOT NULL DEFAULT ''")
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_loyalty_ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            invoice_id INTEGER,
            points_delta REAL NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES jw_customers(phone),
            FOREIGN KEY(invoice_id) REFERENCES jw_invoices(id)
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
    cur.execute(
        """CREATE TABLE IF NOT EXISTS jw_order_payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            payment_method TEXT NOT NULL,
            amount REAL NOT NULL,
            paid_at TEXT NOT NULL,
            cashier_name TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            FOREIGN KEY(invoice_id) REFERENCES jw_invoices(id)
        )"""
    )
    _ensure_column(cur, "jw_production_orders", "bom_id", "INTEGER")
    cur.execute(
        """UPDATE jw_invoices
           SET paid_total = COALESCE(paid_total, 0),
               remaining_total = CASE
                   WHEN total - COALESCE(paid_total, 0) < 0 THEN 0
                   ELSE total - COALESCE(paid_total, 0)
               END"""
    )
    try:
        cur.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS jw_products_barcode_unique
               ON jw_products(barcode)
               WHERE barcode IS NOT NULL AND barcode != ''"""
        )
    except Exception:
        pass
    _migrate_customer_tables(cur)
    conn.commit()
    conn.close()

    _ensure_default_payment_methods()
    _ensure_default_statuses()
    _ensure_default_delivery_companies()
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


def _ensure_default_statuses() -> None:
    defaults = [
        ("DELIVERY", "قيد الانتظار", "Pending", 1),
        ("DELIVERY", "خارج للتوصيل", "Out for Delivery", 2),
        ("DELIVERY", "تم التوصيل", "Delivered", 3),
        ("DELIVERY", "مرتجع", "Returned", 4),
        ("PAYMENT", "بانتظار الدفع", "Awaiting Payment", 1),
        ("PAYMENT", "دفع لاحق", "Pay Later", 2),
        ("PAYMENT", "تحت التحصيل", "Under Collection", 3),
    ]
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jw_statuses")
    if cur.fetchone()[0] == 0:
        for status_group, name_ar, name_en, sort_order in defaults:
            cur.execute(
                """INSERT INTO jw_statuses(
                       status_group, name_ar, name_en, sort_order, active
                   ) VALUES (?, ?, ?, ?, 1)""",
                (status_group, name_ar, name_en, sort_order),
            )
    conn.commit()
    conn.close()


def _ensure_default_delivery_companies() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jw_delivery_companies")
    if cur.fetchone()[0] == 0:
        cur.execute(
            """INSERT INTO jw_delivery_companies(
                   name, company_type, phone, active
               ) VALUES (?, ?, ?, 1)""",
            ("In-house Delivery", "SELF", ""),
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


def _migrate_customer_tables(cur) -> None:
    conn = cur.connection
    cur.execute("PRAGMA table_info(jw_customers)")
    customer_rows = cur.fetchall()
    if not customer_rows:
        return
    customer_columns = {row[1]: row for row in customer_rows}
    has_id = "id" in customer_columns
    phone_col = customer_columns.get("phone")
    phone_pk = bool(phone_col and phone_col[5] == 1)
    needs_customer_migration = has_id or not phone_pk
    if has_id:
        cur.execute("DROP TABLE IF EXISTS jw_customer_id_map")
        cur.execute(
            """CREATE TEMP TABLE jw_customer_id_map AS
               SELECT id, TRIM(phone) AS phone
               FROM jw_customers
               WHERE phone IS NOT NULL AND TRIM(phone) != ''"""
        )
    if needs_customer_migration:
        cur.execute("DROP TABLE IF EXISTS jw_customers_new")
        cur.execute(
            """CREATE TABLE jw_customers_new(
                phone TEXT NOT NULL PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )"""
        )
        cur.execute(
            """INSERT OR IGNORE INTO jw_customers_new(phone, name, email, created_at)
               SELECT TRIM(phone), name, COALESCE(email, ''), created_at
               FROM jw_customers
               WHERE phone IS NOT NULL AND TRIM(phone) != ''"""
        )
        cur.execute("DROP TABLE jw_customers")
        cur.execute("ALTER TABLE jw_customers_new RENAME TO jw_customers")

    conn.commit()
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        _migrate_invoice_customer_keys(cur, has_id)
        _migrate_loyalty_customer_keys(cur, has_id)
    finally:
        conn.commit()
        conn.execute("PRAGMA foreign_keys=ON")


def _migrate_invoice_customer_keys(cur, use_id_map: bool) -> None:
    cur.execute("PRAGMA table_info(jw_invoices)")
    rows = cur.fetchall()
    if not rows:
        return
    columns = {row[1]: row for row in rows}
    customer_col = columns.get("customer_id")
    customer_type = (customer_col[2] or "").upper() if customer_col else ""
    if customer_type == "TEXT":
        return
    def _column_expr(name: str, default: str) -> str:
        return name if name in columns else default

    customer_id_expr = "customer_id"
    if use_id_map:
        customer_id_expr = """CASE
            WHEN customer_phone IS NOT NULL AND TRIM(customer_phone) != '' THEN TRIM(customer_phone)
            WHEN customer_id IS NOT NULL THEN (SELECT phone FROM jw_customer_id_map WHERE id = customer_id)
            ELSE NULL
        END"""
    paid_total_expr = _column_expr("paid_total", "0")
    payment_status_expr = _column_expr("payment_status", "''")
    payment_due_date_expr = _column_expr("payment_due_date", "NULL")
    payment_order_status_id_expr = _column_expr("payment_order_status_id", "NULL")
    delivery_enabled_expr = _column_expr("delivery_enabled", "0")
    delivery_company_id_expr = _column_expr("delivery_company_id", "NULL")
    delivery_fee_expr = _column_expr("delivery_fee", "0")
    delivery_address_expr = _column_expr("delivery_address", "''")
    delivery_status_id_expr = _column_expr("delivery_status_id", "NULL")
    remaining_total_expr = (
        "CASE "
        f"WHEN total - COALESCE({paid_total_expr}, 0) < 0 THEN 0 "
        f"ELSE total - COALESCE({paid_total_expr}, 0) "
        "END"
    )
    cur.execute(
        """CREATE TABLE jw_invoices_new(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT NOT NULL UNIQUE,
            datetime TEXT NOT NULL,
            cashier_name TEXT NOT NULL,
            txn_type TEXT NOT NULL CHECK(txn_type in ('sale','return')),
            customer_id TEXT,
            customer_name TEXT DEFAULT '',
            customer_phone TEXT DEFAULT '',
            subtotal REAL NOT NULL,
            discount REAL NOT NULL,
            discount_type TEXT NOT NULL DEFAULT 'amount',
            discount_value REAL NOT NULL DEFAULT 0,
            loyalty_earned REAL NOT NULL DEFAULT 0,
            loyalty_redeemed REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL,
            paid_total REAL NOT NULL DEFAULT 0,
            remaining_total REAL NOT NULL DEFAULT 0,
            payment_status TEXT DEFAULT '',
            payment_due_date TEXT,
            payment_order_status_id INTEGER,
            payment_method TEXT NOT NULL,
            order_source TEXT NOT NULL DEFAULT 'in_store',
            website_order_ref TEXT DEFAULT '',
            delivery_enabled INTEGER NOT NULL DEFAULT 0,
            delivery_company_id INTEGER,
            delivery_fee REAL NOT NULL DEFAULT 0,
            delivery_address TEXT DEFAULT '',
            delivery_status_id INTEGER,
            notes TEXT DEFAULT '',
            return_reason TEXT DEFAULT '',
            FOREIGN KEY(customer_id) REFERENCES jw_customers(phone),
            FOREIGN KEY(delivery_company_id) REFERENCES jw_delivery_companies(id),
            FOREIGN KEY(payment_order_status_id) REFERENCES jw_statuses(id),
            FOREIGN KEY(delivery_status_id) REFERENCES jw_statuses(id)
        )"""
    )
    cur.execute(
        f"""INSERT INTO jw_invoices_new(
                id, invoice_no, datetime, cashier_name, txn_type, customer_id, customer_name, customer_phone,
                subtotal, discount, discount_type, discount_value, loyalty_earned, loyalty_redeemed,
                total, paid_total, remaining_total, payment_status, payment_due_date, payment_order_status_id,
                payment_method, order_source, website_order_ref, delivery_enabled, delivery_company_id,
                delivery_fee, delivery_address, delivery_status_id, notes, return_reason
            )
            SELECT id, invoice_no, datetime, cashier_name, txn_type, {customer_id_expr}, customer_name,
                   customer_phone, subtotal, discount, discount_type, discount_value, loyalty_earned,
                   loyalty_redeemed, total, COALESCE({paid_total_expr}, 0),
                   {remaining_total_expr},
                   COALESCE({payment_status_expr}, ''), {payment_due_date_expr}, {payment_order_status_id_expr},
                   payment_method, order_source, website_order_ref, COALESCE({delivery_enabled_expr}, 0),
                   {delivery_company_id_expr}, COALESCE({delivery_fee_expr}, 0),
                   COALESCE({delivery_address_expr}, ''),
                   {delivery_status_id_expr}, notes, return_reason
            FROM jw_invoices"""
    )
    cur.execute("DROP TABLE jw_invoices")
    cur.execute("ALTER TABLE jw_invoices_new RENAME TO jw_invoices")


def _migrate_loyalty_customer_keys(cur, use_id_map: bool) -> None:
    cur.execute("PRAGMA table_info(jw_loyalty_ledger)")
    rows = cur.fetchall()
    if not rows:
        return
    columns = {row[1]: row for row in rows}
    customer_col = columns.get("customer_id")
    customer_type = (customer_col[2] or "").upper() if customer_col else ""
    if customer_type == "TEXT":
        return
    customer_id_expr = "customer_id"
    if use_id_map:
        customer_id_expr = "(SELECT phone FROM jw_customer_id_map WHERE id = customer_id)"
    cur.execute(
        """CREATE TABLE jw_loyalty_ledger_new(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id TEXT NOT NULL,
            invoice_id INTEGER,
            points_delta REAL NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES jw_customers(phone),
            FOREIGN KEY(invoice_id) REFERENCES jw_invoices(id)
        )"""
    )
    cur.execute(
        f"""INSERT INTO jw_loyalty_ledger_new(
                id, customer_id, invoice_id, points_delta, reason, created_at
            )
            SELECT id, {customer_id_expr}, invoice_id, points_delta, reason, created_at
            FROM jw_loyalty_ledger
            WHERE {customer_id_expr} IS NOT NULL"""
    )
    cur.execute("DROP TABLE jw_loyalty_ledger")
    cur.execute("ALTER TABLE jw_loyalty_ledger_new RENAME TO jw_loyalty_ledger")


def list_payment_methods() -> List[Tuple[int, str, str]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, name_ar, name_en FROM jw_payment_methods WHERE active = 1 ORDER BY id"
    )
    rows = cur.fetchall()
    conn.close()
    return [(row[0], row[1], row[2]) for row in rows]


def list_delivery_companies(include_inactive: bool = True) -> List[JewelryDeliveryCompany]:
    conn = get_conn()
    cur = conn.cursor()
    query = """SELECT id, name, company_type, COALESCE(phone, ''), active
               FROM jw_delivery_companies"""
    params: Tuple = ()
    if not include_inactive:
        query += " WHERE active = 1"
    query += " ORDER BY id"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryDeliveryCompany(
            id=row[0],
            name=row[1],
            company_type=row[2],
            phone=row[3] or "",
            active=bool(row[4]),
        )
        for row in rows
    ]


def create_delivery_company(name: str, company_type: str, phone: str) -> int:
    normalized_name = name.strip()
    normalized_company_type = company_type.strip()
    if not normalized_name or not normalized_company_type:
        raise ValueError("Delivery company name and type are required")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO jw_delivery_companies(name, company_type, phone, active)
           VALUES (?, ?, ?, 1)""",
        (normalized_name, normalized_company_type, (phone or "").strip()),
    )
    company_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return company_id


def update_delivery_company(
    company_id: int,
    name: str,
    company_type: str,
    phone: str,
) -> None:
    normalized_name = name.strip()
    normalized_company_type = company_type.strip()
    if not normalized_name or not normalized_company_type:
        raise ValueError("Delivery company name and type are required")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE jw_delivery_companies
           SET name = ?, company_type = ?, phone = ?
           WHERE id = ?""",
        (normalized_name, normalized_company_type, (phone or "").strip(), company_id),
    )
    conn.commit()
    conn.close()


def disable_delivery_company(company_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE jw_delivery_companies SET active = 0 WHERE id = ?",
        (company_id,),
    )
    conn.commit()
    conn.close()


def list_statuses(
    status_group: Optional[str] = None,
    include_inactive: bool = True,
) -> List[JewelryStatusItem]:
    conn = get_conn()
    cur = conn.cursor()
    query = """SELECT id, status_group, name_ar, name_en, sort_order, active
               FROM jw_statuses"""
    params: List = []
    conditions = []
    if status_group:
        conditions.append("status_group = ?")
        params.append(status_group)
    if not include_inactive:
        conditions.append("active = 1")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY status_group, sort_order, id"
    cur.execute(query, tuple(params))
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryStatusItem(
            id=row[0],
            status_group=row[1],
            name_ar=row[2],
            name_en=row[3],
            sort_order=row[4],
            active=bool(row[5]),
        )
        for row in rows
    ]


def create_status(
    status_group: str,
    name_ar: str,
    name_en: str,
    sort_order: int,
) -> int:
    normalized_group = status_group.strip().upper()
    normalized_name_ar = name_ar.strip()
    normalized_name_en = name_en.strip()
    if not normalized_group or not normalized_name_ar or not normalized_name_en:
        raise ValueError("Status group and names are required")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO jw_statuses(status_group, name_ar, name_en, sort_order, active)
           VALUES (?, ?, ?, ?, 1)""",
        (normalized_group, normalized_name_ar, normalized_name_en, int(sort_order)),
    )
    status_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return status_id


def update_status(
    status_id: int,
    status_group: str,
    name_ar: str,
    name_en: str,
    sort_order: int,
) -> None:
    normalized_group = status_group.strip().upper()
    normalized_name_ar = name_ar.strip()
    normalized_name_en = name_en.strip()
    if not normalized_group or not normalized_name_ar or not normalized_name_en:
        raise ValueError("Status group and names are required")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE jw_statuses
           SET status_group = ?, name_ar = ?, name_en = ?, sort_order = ?
           WHERE id = ?""",
        (normalized_group, normalized_name_ar, normalized_name_en, int(sort_order), status_id),
    )
    conn.commit()
    conn.close()


def disable_status(status_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE jw_statuses SET active = 0 WHERE id = ?", (status_id,))
    conn.commit()
    conn.close()


def list_active_statuses(status_group: str) -> List[JewelryStatusItem]:
    normalized_group = status_group.strip().upper()
    if not normalized_group:
        return []
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, status_group, name_ar, name_en, sort_order, active
           FROM jw_statuses
           WHERE status_group = ? AND active = 1
           ORDER BY sort_order, id""",
        (normalized_group,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryStatusItem(
            id=row[0],
            status_group=row[1],
            name_ar=row[2],
            name_en=row[3],
            sort_order=row[4],
            active=bool(row[5]),
        )
        for row in rows
    ]


def list_customers(search: Optional[str] = None) -> List[JewelryCustomer]:
    conn = get_conn()
    cur = conn.cursor()
    params: Tuple[str, ...] = ()
    query = """SELECT phone, name, COALESCE(email, ''), created_at
               FROM jw_customers"""
    if search:
        like = f"%{search}%"
        query += " WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?"
        params = (like, like, like)
    query += " ORDER BY created_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryCustomer(
            phone=row[0] or "",
            name=row[1],
            email=row[2] or "",
            created_at=row[3],
        )
        for row in rows
    ]


def find_customer_by_phone(phone: str) -> Optional[JewelryCustomer]:
    normalized = (phone or "").strip()
    if not normalized:
        return None
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT phone, name, COALESCE(email, ''), created_at
           FROM jw_customers WHERE phone = ? LIMIT 1""",
        (normalized,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return JewelryCustomer(
        phone=row[0] or "",
        name=row[1],
        email=row[2] or "",
        created_at=row[3],
    )


def save_customer(
    name: str,
    phone: str,
    email: str = "",
) -> str:
    normalized_phone = (phone or "").strip()
    normalized_name = name.strip()
    normalized_email = (email or "").strip()
    if not normalized_phone or not normalized_name:
        return ""
    conn = get_conn()
    cur = conn.cursor()
    created_at = datetime.now().isoformat(timespec="seconds")
    cur.execute(
        """INSERT INTO jw_customers(phone, name, email, created_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(phone) DO UPDATE SET name = excluded.name, email = excluded.email""",
        (normalized_phone, normalized_name, normalized_email, created_at),
    )
    conn.commit()
    conn.close()
    return normalized_phone


def search_customers(term: str, limit: int = 8) -> List[JewelryCustomer]:
    normalized = (term or "").strip()
    if not normalized:
        return []
    like_term = f"%{normalized}%"
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT phone, name, COALESCE(email, ''), created_at
           FROM jw_customers
           WHERE phone LIKE ? OR name LIKE ? OR email LIKE ?
           ORDER BY name
           LIMIT ?""",
        (like_term, like_term, like_term, int(limit)),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryCustomer(
            phone=row[0] or "",
            name=row[1],
            email=row[2] or "",
            created_at=row[3],
        )
        for row in rows
    ]


def get_loyalty_balance(customer_phone: str) -> float:
    normalized_phone = (customer_phone or "").strip()
    if not normalized_phone:
        return 0.0
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COALESCE(SUM(points_delta), 0) FROM jw_loyalty_ledger WHERE customer_id = ?",
        (normalized_phone,),
    )
    balance = float(cur.fetchone()[0] or 0)
    conn.close()
    return balance


def record_loyalty_entry(
    customer_phone: str,
    invoice_id: Optional[int],
    points_delta: float,
    reason: str,
) -> None:
    normalized_phone = (customer_phone or "").strip()
    if not normalized_phone or not points_delta:
        return
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO jw_loyalty_ledger
           (customer_id, invoice_id, points_delta, reason, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            normalized_phone,
            invoice_id,
            float(points_delta),
            reason.strip() or "invoice",
            datetime.now().isoformat(timespec="seconds"),
        ),
    )
    conn.commit()
    conn.close()


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
    customer_id: Optional[str],
    customer_name: str,
    customer_phone: str,
    subtotal: float,
    discount: float,
    discount_type: str,
    discount_value: float,
    loyalty_earned: float,
    loyalty_redeemed: float,
    total: float,
    payment_method: str,
    order_source: str,
    website_order_ref: str,
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
           (invoice_no, datetime, cashier_name, txn_type, customer_id, customer_name, customer_phone,
            subtotal, discount, discount_type, discount_value, loyalty_earned, loyalty_redeemed,
            total, payment_method, order_source, website_order_ref, notes, return_reason)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            invoice_no,
            invoice_datetime,
            cashier_name,
            txn_type,
            customer_id,
            customer_name,
            customer_phone,
            subtotal,
            discount,
            discount_type,
            discount_value,
            loyalty_earned,
            loyalty_redeemed,
            total,
            payment_method,
            order_source,
            website_order_ref,
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
    if customer_id:
        if txn_type == "return":
            points_delta = -abs(loyalty_earned)
        else:
            points_delta = float(loyalty_earned) - float(loyalty_redeemed)
        record_loyalty_entry(customer_id, invoice_id, points_delta, reason=f"invoice:{invoice_no}")
    return invoice_no


def list_order_payments(invoice_id: int) -> List[JewelryPaymentRow]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, invoice_id, payment_method, amount, paid_at,
                  COALESCE(cashier_name, ''), COALESCE(notes, '')
           FROM jw_order_payments
           WHERE invoice_id = ?
           ORDER BY paid_at, id""",
        (invoice_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return [
        JewelryPaymentRow(
            id=row[0],
            invoice_id=row[1],
            payment_method=row[2],
            amount=row[3],
            paid_at=row[4],
            cashier_name=row[5] or "",
            notes=row[6] or "",
        )
        for row in rows
    ]


def create_order_payment(
    invoice_id: int,
    payment_method: str,
    amount: float,
    cashier_name: str = "",
    notes: str = "",
    paid_at: Optional[str] = None,
) -> int:
    normalized_method = payment_method.strip()
    if not normalized_method:
        raise ValueError("Payment method is required")
    if amount <= 0:
        raise ValueError("Payment amount must be positive")
    paid_at_value = paid_at or datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO jw_order_payments
           (invoice_id, payment_method, amount, paid_at, cashier_name, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            invoice_id,
            normalized_method,
            float(amount),
            paid_at_value,
            cashier_name.strip(),
            (notes or "").strip(),
        ),
    )
    payment_id = int(cur.lastrowid)
    conn.commit()
    conn.close()
    recalculate_invoice_payment_totals(invoice_id)
    return payment_id


def recalculate_invoice_payment_totals(invoice_id: int) -> Tuple[float, float, str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT total
           FROM jw_invoices
           WHERE id = ?""",
        (invoice_id,),
    )
    invoice_row = cur.fetchone()
    if not invoice_row:
        conn.close()
        raise ValueError("Invoice not found")
    grand_total = float(invoice_row[0] or 0)
    if grand_total < 0:
        grand_total = 0.0
    cur.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM jw_order_payments WHERE invoice_id = ?",
        (invoice_id,),
    )
    raw_paid_total = float(cur.fetchone()[0] or 0)
    paid_total = min(raw_paid_total, grand_total)
    remaining_total = max(grand_total - paid_total, 0.0)
    if remaining_total <= 0 and grand_total >= 0:
        payment_status = "PAID"
    elif paid_total <= 0:
        payment_status = "UNPAID"
    else:
        payment_status = "PARTIAL"
    cur.execute(
        """UPDATE jw_invoices
           SET paid_total = ?, remaining_total = ?, payment_status = ?
           WHERE id = ?""",
        (paid_total, remaining_total, payment_status, invoice_id),
    )
    conn.commit()
    conn.close()
    return paid_total, remaining_total, payment_status


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
    query = """SELECT invoice_no, datetime, cashier_name, txn_type, customer_id, COALESCE(customer_name, ''),
                      COALESCE(customer_phone, ''), subtotal, discount, COALESCE(discount_type, 'amount'),
                      COALESCE(discount_value, 0), COALESCE(loyalty_earned, 0),
                      COALESCE(loyalty_redeemed, 0), total, payment_method,
                      COALESCE(order_source, 'in_store'), COALESCE(website_order_ref, ''),
                      notes, return_reason
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
            customer_id=row[4],
            customer_name=row[5],
            customer_phone=row[6],
            subtotal=row[7],
            discount=row[8],
            discount_type=row[9],
            discount_value=row[10],
            loyalty_earned=row[11],
            loyalty_redeemed=row[12],
            total=row[13],
            payment_method=row[14],
            order_source=row[15],
            website_order_ref=row[16],
            notes=row[17],
            return_reason=row[18],
        )
        for row in rows
    ]


def fetch_invoice_details(invoice_no: str) -> Tuple[JewelryInvoice, List[JewelryInvoiceItem]]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT invoice_no, datetime, cashier_name, txn_type, customer_id, COALESCE(customer_name, ''),
                  COALESCE(customer_phone, ''), subtotal, discount, COALESCE(discount_type, 'amount'),
                  COALESCE(discount_value, 0), COALESCE(loyalty_earned, 0),
                  COALESCE(loyalty_redeemed, 0), total, payment_method,
                  COALESCE(order_source, 'in_store'), COALESCE(website_order_ref, ''), notes, return_reason
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
        customer_id=row[4],
        customer_name=row[5],
        customer_phone=row[6],
        subtotal=row[7],
        discount=row[8],
        discount_type=row[9],
        discount_value=row[10],
        loyalty_earned=row[11],
        loyalty_redeemed=row[12],
        total=row[13],
        payment_method=row[14],
        order_source=row[15],
        website_order_ref=row[16],
        notes=row[17],
        return_reason=row[18],
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
