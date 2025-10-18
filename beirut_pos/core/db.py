"""SQLite helpers wired for durable Windows storage."""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Iterator, Tuple

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from .config_store import get_config_value, set_config_value
from .paths import BACKUP_DIR, DB_PATH, ensure_storage_dirs

_VALID_SYNC = {"OFF", "NORMAL", "FULL", "EXTRA"}
_DEFAULT_SYNC = "FULL"

ensure_storage_dirs()

_ENGINE = create_engine(
    f"sqlite:///{DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=_ENGINE, expire_on_commit=False)


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
    ensure_storage_dirs()
    first_time = not DB_PATH.exists()
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
        """CREATE TABLE IF NOT EXISTS categories(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                order_index INTEGER NOT NULL DEFAULT 0
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
                closed_by TEXT
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
        """CREATE TABLE IF NOT EXISTS purchases(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                supplier TEXT,
                description TEXT NOT NULL,
                payment_method TEXT CHECK(payment_method IN ('cash','card','transfer')),
                amount_le NUMERIC(12,2) NOT NULL,
                attachment_path TEXT,
                linked_order_id INTEGER,
                deleted_at TEXT,
                deleted_by TEXT,
                delete_reason TEXT,
                FOREIGN KEY(linked_order_id) REFERENCES orders(id)
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
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_purchases_created ON purchases(created_at)"
    )

    _ensure_product_columns(cur)
    _ensure_product_options_table(cur)
    _ensure_catalog_order_columns(cur)
    _ensure_default_settings(cur)

    conn.commit()

    if first_time:
        _seed_defaults(cur)
        conn.commit()

    conn.close()


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


def _ensure_catalog_order_columns(cur) -> None:
    cur.execute("PRAGMA table_info(categories)")
    cat_cols = {row[1] for row in cur.fetchall()}
    if "order_index" not in cat_cols:
        cur.execute("ALTER TABLE categories ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0")
        cur.execute("SELECT id FROM categories ORDER BY id")
        cat_ids = [row[0] for row in cur.fetchall()]
        for idx, cat_id in enumerate(cat_ids):
            cur.execute("UPDATE categories SET order_index=? WHERE id=?", (idx, cat_id))

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
        "category_order": "",
        "bar_printer": "",
        "cashier_printer": "",
        "company_name": "Beirut Coffee",
        "currency": "EGP",
        "service_pct": "0",
        "ps_rate_p2": "5000",
        "ps_rate_p4": "8000",
        "table_codes": json.dumps([f"T{i:02d}" for i in range(1, 31)], ensure_ascii=False),
        "voucher_activated": "0",
        "voucher_activated_at": "",
        "voucher_hash": "",
        "voucher_suffix": "",
        "voucher_migrated": "0",
    }
    for key, value in defaults.items():
        cur.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",
            (key, value),
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
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
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


def iter_backups() -> Iterator[Path]:
    if not BACKUP_DIR.exists():
        return
    for day_dir in sorted(BACKUP_DIR.iterdir()):
        if not day_dir.is_dir():
            continue
        candidate = day_dir / "beirut_pos.db"
        if candidate.exists():
            yield candidate
