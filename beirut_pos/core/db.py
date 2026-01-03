"""SQLite helpers wired for durable Windows storage."""
from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Tuple

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .config_store import get_config_value, set_config_value
from .paths import BACKUP_DIR, DATA_DIR, DB_PATH, ensure_storage_dirs

_VALID_SYNC = {"OFF", "NORMAL", "FULL", "EXTRA"}
_DEFAULT_SYNC = "FULL"

ensure_storage_dirs()

_ENGINE = create_engine(
    f"sqlite:///{DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=_ENGINE, expire_on_commit=False)


_SCHEMA_BACKUP_CREATED = False


def _ensure_schema_backup() -> None:
    """Create a one-time .bak copy before altering the schema."""

    global _SCHEMA_BACKUP_CREATED
    if _SCHEMA_BACKUP_CREATED or not DB_PATH.exists():
        return

    timestamp = datetime.utcnow().strftime("%Y%m%d-%I%M%S%p")
    backup_name = f"{DB_PATH.stem}.{timestamp}.bak"
    backup_path = DATA_DIR / backup_name
    try:
        ensure_storage_dirs()
        shutil.copy2(DB_PATH, backup_path)
    except Exception:
        return
    _SCHEMA_BACKUP_CREATED = True


def _current_sync() -> str:
    value = str(get_config_value("sqlite_synchronous", _DEFAULT_SYNC)).upper()
    if value not in _VALID_SYNC:
        value = _DEFAULT_SYNC
        set_config_value("sqlite_synchronous", value)
    return value


@event.listens_for(_ENGINE, "connect")
def _apply_pragmas(dbapi_conn, _):  # pragma: no cover - exercised via runtime
    dbapi_conn.row_factory = sqlite3.Row
    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute(f"PRAGMA synchronous={_current_sync()};")
        cursor.execute("PRAGMA temp_store=MEMORY;")
    finally:
        cursor.close()


def get_conn() -> sqlite3.Connection:
    conn = _ENGINE.raw_connection()
    conn.isolation_level = None  # explicit transactions via BEGIN
    return conn


@contextmanager
def db_transaction(begin_stmt: str = "BEGIN IMMEDIATE"):
    conn = get_conn()
    try:
        conn.execute(begin_stmt)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def close_engine() -> None:
    _ENGINE.dispose()


def get_synchronous_mode() -> str:
    return _current_sync()


def set_synchronous_mode(mode: str) -> str:
    desired = (mode or _DEFAULT_SYNC).upper()
    if desired not in _VALID_SYNC:
        desired = _DEFAULT_SYNC
    set_config_value("sqlite_synchronous", desired)
    conn = get_conn()
    try:
        conn.execute(f"PRAGMA synchronous={desired};")
    finally:
        conn.close()
    return desired


def init_db() -> None:
    safe_migrations()


def safe_migrations() -> None:
    ensure_storage_dirs()
    first_time = not DB_PATH.exists()
    if not first_time:
        _backup_database()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS users(
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role in ('admin','cashier')),
                secret_key TEXT
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS customers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT UNIQUE,
                email TEXT,
                birthday TEXT,
                notes TEXT,
                created_at TEXT NOT NULL
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS categories(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 0,
                color TEXT NOT NULL DEFAULT ''
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS products(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                price_cents INTEGER NOT NULL,
                customizable INTEGER NOT NULL DEFAULT 0,
                track_stock INTEGER NOT NULL DEFAULT 0,
                stock_qty REAL DEFAULT 0,
                min_stock REAL DEFAULT 0,
                package_size REAL NOT NULL DEFAULT 1,
                product_type TEXT DEFAULT '',
                sugar_levels TEXT NOT NULL DEFAULT '[]',
                order_index INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(category_id) REFERENCES categories(id),
                UNIQUE(category_id, name)
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS product_options(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                price_delta_cents INTEGER NOT NULL DEFAULT 0,
                order_index INTEGER NOT NULL DEFAULT 0,
                UNIQUE(product_id, label),
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS orders(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_code TEXT NOT NULL,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                status TEXT NOT NULL CHECK(status in ('open','paid','void')),
                opened_by TEXT NOT NULL,
                closed_by TEXT,
                customer_id INTEGER,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS order_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                price_cents INTEGER NOT NULL,
                qty REAL NOT NULL DEFAULT 1,
                note TEXT DEFAULT '',
                FOREIGN KEY(order_id) REFERENCES orders(id)
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS payments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                method TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                paid_at TEXT NOT NULL,
                cashier TEXT NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id)
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS loyalty_ledger(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                delta_points INTEGER NOT NULL,
                reason TEXT,
                order_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id),
                FOREIGN KEY(order_id) REFERENCES orders(id)
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS reservations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                party_size INTEGER NOT NULL DEFAULT 1,
                reserved_for TEXT NOT NULL,
                table_code TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                notes TEXT,
                created_at TEXT NOT NULL,
                created_by TEXT
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                category TEXT NOT NULL,
                amount_cents INTEGER NOT NULL,
                notes TEXT
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS purchases(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchased_at TEXT NOT NULL,
                supplier TEXT NOT NULL,
                invoice_no TEXT,
                amount_cents INTEGER NOT NULL,
                notes TEXT,
                recorded_by TEXT
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS shifts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                opened_at TEXT NOT NULL,
                closed_at TEXT,
                opened_by TEXT NOT NULL,
                closed_by TEXT,
                notes TEXT
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS staff_payroll(
                username TEXT PRIMARY KEY,
                salary_cents INTEGER NOT NULL DEFAULT 0,
                deductions_cents INTEGER NOT NULL DEFAULT 0,
                loan_cents INTEGER NOT NULL DEFAULT 0,
                salary_period TEXT NOT NULL DEFAULT 'monthly',
                FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS user_sessions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                login_at TEXT NOT NULL,
                logout_at TEXT,
                duration_seconds INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(username) REFERENCES users(username)
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS table_clients(
                table_code TEXT PRIMARY KEY,
                client_name TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS audit_log(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                username TEXT NOT NULL,
                action TEXT NOT NULL,
                entity_type TEXT,
                entity_name TEXT,
                old_value TEXT,
                new_value TEXT,
                extra TEXT
            )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS ps_sessions(
                table_code TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                started_at TEXT NOT NULL,
                total_seconds INTEGER NOT NULL DEFAULT 0
            )"""
    )

  
    # ensure/upgrade steps
    _ensure_product_columns(cur)
    _ensure_product_options_table(cur)
    _ensure_catalog_order_columns(cur)
    _ensure_orders_discount_columns(cur)        # add missing discount columns
    _ensure_orders_payment_window_columns(cur)  # add paid_at/editable_until columns
    _ensure_orders_client_name(cur)             # add client_name column for history
    _ensure_orders_customer_id(cur)             # add customer_id column for loyalty
    _ensure_currency_unit(cur)
    _ensure_ui_texts_table(cur)
    _ensure_default_settings(cur)
    _ensure_staff_payroll_period(cur)
    _ensure_manual_staff_table(cur)
    _ensure_payroll_history_table(cur)
    _normalize_payroll_units(cur)
    conn.commit()


    if first_time:
        _seed_defaults(cur)
        conn.commit()

    conn.close()


def _backup_database() -> None:
    if not DB_PATH.exists():
        return
    timestamp = datetime.utcnow().strftime("%Y%m%d-%I%M%S%p")
    target = DATA_DIR / f"{DB_PATH.stem}-{timestamp}.bak"
    try:
        shutil.copy2(DB_PATH, target)
    except Exception:
        # Best effort; ignore backup issues to avoid blocking migrations.
        pass


def _ensure_product_columns(cur) -> None:
    cur.execute("PRAGMA table_info(products)")
    cols = {row[1] for row in cur.fetchall()}
    if "customizable" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN customizable INTEGER NOT NULL DEFAULT 0")
    if "track_stock" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN track_stock INTEGER NOT NULL DEFAULT 0")
    if "stock_qty" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN stock_qty REAL DEFAULT 0")
    if "min_stock" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN min_stock REAL DEFAULT 0")
    if "package_size" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN package_size REAL NOT NULL DEFAULT 1")
    if "order_index" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0")
        cur.execute("SELECT id, category_id FROM products ORDER BY category_id, id")
        rows = cur.fetchall()
        current_cat = None
        idx = 0
        for row in rows:
            cat_id = row["category_id"]
            if cat_id != current_cat:
                current_cat = cat_id
                idx = 0
            cur.execute("UPDATE products SET order_index=? WHERE id=?", (idx, row["id"]))
            idx += 1
    if "product_type" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN product_type TEXT DEFAULT ''")
    if "sugar_levels" not in cols:
        cur.execute("ALTER TABLE products ADD COLUMN sugar_levels TEXT NOT NULL DEFAULT '[]'")
    cur.execute("UPDATE products SET product_type=COALESCE(product_type, '')")
    cur.execute("UPDATE products SET sugar_levels='[]' WHERE sugar_levels IS NULL OR sugar_levels=''")


def _ensure_product_options_table(cur) -> None:
    cur.execute(
        """CREATE TABLE IF NOT EXISTS product_options(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                label TEXT NOT NULL,
                price_delta_cents INTEGER NOT NULL DEFAULT 0,
                order_index INTEGER NOT NULL DEFAULT 0,
                UNIQUE(product_id, label),
                FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
            )"""
    )


def _ensure_ui_texts_table(cur) -> None:
    cur.execute(
        """CREATE TABLE IF NOT EXISTS ui_texts(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )"""
    )


def _ensure_catalog_order_columns(cur) -> None:
    cur.execute("PRAGMA table_info(categories)")
    cat_cols = {row[1] for row in cur.fetchall()}
    if "order_index" not in cat_cols:
        cur.execute("ALTER TABLE categories ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0")
        cur.execute("SELECT id FROM categories ORDER BY id")
        cat_ids = [row[0] for row in cur.fetchall()]
        for idx, cat_id in enumerate(cat_ids):
            cur.execute("UPDATE categories SET order_index=? WHERE id=?", (idx, cat_id))
    if "color" not in cat_cols:
        cur.execute("ALTER TABLE categories ADD COLUMN color TEXT NOT NULL DEFAULT ''")

    cur.execute("PRAGMA table_info(products)")
    prod_cols = {row[1] for row in cur.fetchall()}
    if "order_index" not in prod_cols:
        cur.execute("ALTER TABLE products ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0")
        cur.execute("SELECT id, category_id FROM products ORDER BY category_id, id")
        rows = cur.fetchall()
        current_cat = None
        idx = 0
        for row in rows:
            cat_id = row["category_id"]
            if cat_id != current_cat:
                current_cat = cat_id
                idx = 0
            cur.execute("UPDATE products SET order_index=? WHERE id=?", (idx, row["id"]))
            idx += 1


def _ensure_orders_discount_columns(cur) -> None:
    """Add discount columns to orders if they don't exist (idempotent)."""
    cur.execute("PRAGMA table_info(orders)")
    cols = {row[1] for row in cur.fetchall()}
    if "discount_cents" not in cols:
        _ensure_schema_backup()
        cur.execute("ALTER TABLE orders ADD COLUMN discount_cents INTEGER NOT NULL DEFAULT 0")
    if "discount_reason" not in cols:
        _ensure_schema_backup()
        cur.execute("ALTER TABLE orders ADD COLUMN discount_reason TEXT NOT NULL DEFAULT ''")
    if "discount_type" not in cols:
        _ensure_schema_backup()
        cur.execute("ALTER TABLE orders ADD COLUMN discount_type TEXT NOT NULL DEFAULT 'amount'")
    if "discount_value" not in cols:
        _ensure_schema_backup()
        cur.execute("ALTER TABLE orders ADD COLUMN discount_value REAL NOT NULL DEFAULT 0")
    cur.execute(
        "UPDATE orders SET discount_type='amount' WHERE discount_type IS NULL OR discount_type=''"
    )
    cur.execute(
        "UPDATE orders SET discount_value=0 WHERE discount_value IS NULL"
    )


def _ensure_orders_payment_window_columns(cur) -> None:
    cur.execute("PRAGMA table_info(orders)")
    cols = {row[1] for row in cur.fetchall()}
    if "paid_at" not in cols:
        _ensure_schema_backup()
        cur.execute("ALTER TABLE orders ADD COLUMN paid_at TEXT")
    if "editable_until" not in cols:
        _ensure_schema_backup()
        cur.execute("ALTER TABLE orders ADD COLUMN editable_until TEXT")


def _ensure_orders_client_name(cur) -> None:
    cur.execute("PRAGMA table_info(orders)")
    cols = {row[1] for row in cur.fetchall()}
    if "client_name" not in cols:
        _ensure_schema_backup()
        cur.execute("ALTER TABLE orders ADD COLUMN client_name TEXT NOT NULL DEFAULT ''")


def _ensure_orders_customer_id(cur) -> None:
    cur.execute("PRAGMA table_info(orders)")
    cols = {row[1] for row in cur.fetchall()}
    if "customer_id" not in cols:
        _ensure_schema_backup()
        cur.execute("ALTER TABLE orders ADD COLUMN customer_id INTEGER REFERENCES customers(id)")


def _ensure_currency_unit(cur) -> None:
    cur.execute("SELECT value FROM settings WHERE key='currency_unit'")
    row = cur.fetchone()
    if row and row["value"] == "pounds":
        return
    for table, column in (
        ("products", "price_cents"),
        ("product_options", "price_delta_cents"),
        ("order_items", "price_cents"),
        ("payments", "amount_cents"),
        ("purchases", "amount_cents"),
        ("expenses", "amount_cents"),
    ):
        try:
            cur.execute(
                f"UPDATE {table} SET {column} = CAST(ROUND({column} / 100.0) AS INTEGER)"
            )
        except sqlite3.OperationalError:
            continue
    cur.execute(
        "INSERT INTO settings(key,value) VALUES('currency_unit','pounds') "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
    )


def _ensure_default_settings(cur) -> None:
    defaults = {
        "logo_path": "",
        "background_path": "",
        "accent_color": "#C89A5B",
        "surface_color": "#23140C",
        "text_color": "#F8EFE4",
        "muted_text_color": "#D9C7B5",
        "menu_card_color": "#28160F",
        "menu_header_color": "#F1C58F",
        "menu_button_color": "#F5E1C8",
        "menu_button_text_color": "#2B130B",
        "menu_button_hover_color": "#E3C69F",
        "menu_button_height": "72",
        "toolbar_color": "#000000",
        "toolbar_text_color": "#FFFFFF",
        "category_order": "",
        "bar_printer": "",
        "cashier_printer": "",
        "company_name": "Beirut Coffee",
        "currency": "EGP",
        "service_pct": "0",
        "ps_rate_p2": "50",
        "ps_rate_p4": "80",
        "ps_vip_rate_p2": "50",
        "ps_vip_rate_p4": "80",
        "ps_vip_tables": json.dumps([], ensure_ascii=False),
        "currency_unit": "pounds",
        "table_codes": json.dumps([f"T{i:02d}" for i in range(1, 31)], ensure_ascii=False),
        "voucher_activated": "0",
        "voucher_activated_at": "",
        "voucher_hash": "",
        "voucher_suffix": "",
        "voucher_migrated": "0",
        "app_first_run_at": "",
        "activated": "0",
        "client_name": "My Client",
        "client_logo_path": "",
        "primary_color": "#C89A5B",
    }
    for key, value in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (key, value),
        )


def _ensure_staff_payroll_period(cur) -> None:
    cur.execute("PRAGMA table_info(staff_payroll)")
    cols = {row[1] for row in cur.fetchall()}
    if "salary_period" not in cols:
        cur.execute("ALTER TABLE staff_payroll ADD COLUMN salary_period TEXT NOT NULL DEFAULT 'monthly'")


def _ensure_manual_staff_table(cur) -> None:
    cur.execute(
        """CREATE TABLE IF NOT EXISTS staff_manual (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT '',
                salary_cents INTEGER NOT NULL DEFAULT 0,
                deductions_cents INTEGER NOT NULL DEFAULT 0,
                loan_cents INTEGER NOT NULL DEFAULT 0,
                salary_period TEXT NOT NULL DEFAULT 'monthly',
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )"""
    )


def _ensure_payroll_history_table(cur) -> None:
    cur.execute(
        """CREATE TABLE IF NOT EXISTS staff_payroll_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recorded_at TEXT NOT NULL,
                source TEXT NOT NULL,
                username TEXT,
                manual_id INTEGER,
                display_name TEXT NOT NULL,
                role TEXT,
                salary_period TEXT NOT NULL DEFAULT 'monthly',
                salary_cents INTEGER NOT NULL DEFAULT 0,
                deductions_cents INTEGER NOT NULL DEFAULT 0,
                loan_cents INTEGER NOT NULL DEFAULT 0,
                net_cents INTEGER NOT NULL DEFAULT 0
            )"""
    )


def _normalize_payroll_units(cur) -> None:
    cur.execute("SELECT value FROM settings WHERE key='payroll_units'")
    row = cur.fetchone()
    if row and row["value"] == "pounds":
        return

    tables = ("staff_payroll", "staff_manual")
    columns = ("salary_cents", "deductions_cents", "loan_cents")
    for table in tables:
        for column in columns:
            try:
                cur.execute(
                    f"UPDATE {table} SET {column} = CAST(ROUND({column} / 100.0) AS INTEGER)"
                )
            except sqlite3.OperationalError:
                continue

    try:
        cur.execute(
            """
            UPDATE staff_payroll_history
            SET salary_cents = CAST(ROUND(salary_cents / 100.0) AS INTEGER),
                deductions_cents = CAST(ROUND(deductions_cents / 100.0) AS INTEGER),
                loan_cents = CAST(ROUND(loan_cents / 100.0) AS INTEGER),
                net_cents = CAST(ROUND(net_cents / 100.0) AS INTEGER)
            """
        )
    except sqlite3.OperationalError:
        pass

    cur.execute(
        "INSERT INTO settings(key,value) VALUES('payroll_units','pounds') "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
    )


def _seed_defaults(cur) -> None:
    cur.execute(
        "INSERT OR REPLACE INTO users VALUES('admin','admin123','admin','ADMIN-DEFAULT-CHANGE-ME')"
    )
    cur.execute(
        "INSERT OR REPLACE INTO users VALUES('cashier1','1234','cashier','C1-0000')"
    )
    cur.execute(
        "INSERT OR REPLACE INTO users VALUES('cashier2','1234','cashier','C2-0000')"
    )


def log_action(username, action, entity_type=None, entity_name=None, old_value=None, new_value=None, extra=None):
    with db_transaction() as conn:
        conn.execute(
            """INSERT INTO audit_log(ts,username,action,entity_type,entity_name,old_value,new_value,extra)
                   VALUES(?,?,?,?,?,?,?,?)""",
            (
                datetime.utcnow().isoformat(),
                username,
                action,
                entity_type,
                entity_name,
                old_value,
                new_value,
                extra,
            ),
        )


def setting_get(key: str, default: str = "") -> str:
    conn = get_conn()
    try:
        cur = conn.cursor()
        try:
            cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        except sqlite3.OperationalError as exc:
            # Many tests exercise the service layer before the DB schema is
            # initialised.  Instead of propagating "no such table" errors,
            # gracefully fall back to the provided default value so the
            # application can continue running in preview-only mode.
            if "no such table" in str(exc).lower():
                return default
            raise
        row = cur.fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def setting_get_int(key: str, default: int = 0) -> int:
    value = setting_get(key, None)  # type: ignore[arg-type]
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def setting_set(key: str, value: str) -> None:
    with db_transaction() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
            (key, value),
        )


def run_integrity_check() -> str:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check;")
        row = cur.fetchone()
        return row[0] if row else "error"
    finally:
        conn.close()


def maybe_run_integrity_check(force: bool = False) -> Tuple[bool, str]:
    today = date.today()
    if not force:
        last = str(get_config_value("last_integrity_check", ""))
        if last:
            try:
                last_date = date.fromisoformat(last)
                if (today - last_date).days < 7:
                    return True, ""
            except ValueError:
                pass
    result = run_integrity_check()
    set_config_value("last_integrity_check", today.isoformat())
    ok = result.strip().lower() == "ok"
    return ok, result
#// while merging after moving the table product into another table , clean the first table ! :D

#on merging , when to merge a table , table iam inside , moves to the table i choosen in merge and resets its order cuz its already copied into another
#on reservation allow max 100 , also enable me to choose tables , not 1 single table ,
def iter_backups() -> Iterator[Path]:
    if not BACKUP_DIR.exists():
        return
    for day_dir in sorted(BACKUP_DIR.iterdir()):
        if not day_dir.is_dir():
            continue
        candidate = day_dir / "beirut_pos.db"
        if candidate.exists():
            yield candidate
