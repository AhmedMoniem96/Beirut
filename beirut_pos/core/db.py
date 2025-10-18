"""SQLite helpers for Beirut POS — patched with dual timestamps (purchased_at & created_at)."""
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

# -----------------------------------------------------------------------------
# BASE CONFIG
# -----------------------------------------------------------------------------
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

def get_synchronous_mode() -> str:
    """Return current SQLite synchronous mode (OFF/NORMAL/FULL/EXTRA) from settings."""
    return _current_sync()

def set_synchronous_mode(mode: str) -> str:
    """Persist and apply SQLite synchronous mode immediately."""
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



@event.listens_for(_ENGINE, "connect")
def _apply_pragmas(dbapi_conn, _):
    dbapi_conn.row_factory = sqlite3.Row
    c = dbapi_conn.cursor()
    try:
        c.execute("PRAGMA foreign_keys=ON;")
        c.execute("PRAGMA journal_mode=WAL;")
        c.execute(f"PRAGMA synchronous={_current_sync()};")
        c.execute("PRAGMA temp_store=MEMORY;")
    finally:
        c.close()


def get_conn() -> sqlite3.Connection:
    conn = _ENGINE.raw_connection()
    conn.isolation_level = None
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


def close_engine(): _ENGINE.dispose()


# -----------------------------------------------------------------------------
# INIT
# -----------------------------------------------------------------------------
def init_db() -> None:
    ensure_storage_dirs()
    first_time = not DB_PATH.exists()
    conn = get_conn()
    cur = conn.cursor()

    # --- simplified core tables
    cur.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY, value TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role in ('admin','cashier')),
        secret_key TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        order_index INTEGER NOT NULL DEFAULT 0)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS products(
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
        UNIQUE(category_id, name))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_code TEXT NOT NULL,
        opened_at TEXT NOT NULL,
        closed_at TEXT,
        status TEXT NOT NULL CHECK(status IN ('open','paid','void')),
        opened_by TEXT NOT NULL,
        closed_by TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        price_cents INTEGER NOT NULL,
        qty REAL NOT NULL DEFAULT 1,
        note TEXT DEFAULT '',
        FOREIGN KEY(order_id) REFERENCES orders(id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        method TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        paid_at TEXT NOT NULL,
        cashier TEXT NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id))""")

    cur.execute("""CREATE TABLE IF NOT EXISTS reservations(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        party_size INTEGER NOT NULL DEFAULT 1,
        reserved_for TEXT NOT NULL,
        table_code TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        notes TEXT,
        created_at TEXT NOT NULL,
        created_by TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        category TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        notes TEXT)""")

    # ✅ Purchases: both purchased_at + created_at timestamps
    cur.execute("""CREATE TABLE IF NOT EXISTS purchases(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchased_at TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        supplier TEXT NOT NULL,
        invoice_no TEXT,
        amount_cents INTEGER NOT NULL,
        notes TEXT,
        recorded_by TEXT)""")

    # auto-migration if created_at missing
    cur.execute("PRAGMA table_info(purchases)")
    cols = {r[1] for r in cur.fetchall()}
    if "created_at" not in cols:
        cur.execute("ALTER TABLE purchases ADD COLUMN created_at TEXT NOT NULL DEFAULT (datetime('now'))")

    cur.execute("""CREATE TABLE IF NOT EXISTS shifts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opened_at TEXT NOT NULL,
        closed_at TEXT,
        opened_by TEXT NOT NULL,
        closed_by TEXT,
        notes TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_name TEXT,
        old_value TEXT,
        new_value TEXT,
        extra TEXT)""")

    cur.execute("""CREATE TABLE IF NOT EXISTS ps_sessions(
        table_code TEXT PRIMARY KEY,
        mode TEXT NOT NULL,
        started_at TEXT NOT NULL,
        total_seconds INTEGER NOT NULL DEFAULT 0)""")

    _ensure_default_settings(cur)
    conn.commit()
    if first_time:
        _seed_defaults(cur)
        conn.commit()
    conn.close()


# -----------------------------------------------------------------------------
# HELPERS
# -----------------------------------------------------------------------------
def _ensure_default_settings(cur):
    defaults = {
        "accent_color": "#C89A5B",
        "surface_color": "#23140C",
        "text_color": "#F8EFE4",
        "toolbar_color": "#000000",
        "toolbar_text_color": "#FFFFFF",
        "currency": "EGP",
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))


def _seed_defaults(cur):
    cur.execute("INSERT OR REPLACE INTO users VALUES('admin','admin123','admin','ADMIN')")
    cur.execute("INSERT OR REPLACE INTO users VALUES('cashier1','1234','cashier','C1')")
    cur.execute("INSERT OR REPLACE INTO users VALUES('cashier2','1234','cashier','C2')")


# -----------------------------------------------------------------------------
# UTILITIES
# -----------------------------------------------------------------------------
def log_action(username, action, entity_type=None, entity_name=None, old_value=None, new_value=None, extra=None):
    with db_transaction() as conn:
        conn.execute("""INSERT INTO audit_log(ts,username,action,entity_type,entity_name,old_value,new_value,extra)
                        VALUES(?,?,?,?,?,?,?,?)""",
                     (datetime.utcnow().isoformat(), username, action, entity_type,
                      entity_name, old_value, new_value, extra))


def setting_get(key: str, default=""):
    conn = get_conn(); cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


def setting_set(key: str, value: str):
    with db_transaction() as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", (key, value))


def run_integrity_check():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("PRAGMA integrity_check;")
    row = cur.fetchone()
    conn.close()
    return row[0] if row else "error"

def maybe_run_integrity_check(force: bool = False) -> tuple[bool, str]:
    """Run PRAGMA integrity_check at most once per 7 days (unless force=True)."""
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
    ok = (result or "").strip().lower() == "ok"
    return ok, result


def iter_backups() -> Iterator[Path]:
    if not BACKUP_DIR.exists(): return
    for d in sorted(BACKUP_DIR.iterdir()):
        if d.is_dir():
            p = d / "beirut_pos.db"
            if p.exists():
                yield p
