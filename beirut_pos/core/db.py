# beirut_pos/core/db.py
import os
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# Allow overriding DB path via env if you want (optional)
_ENV_DB_PATH = os.getenv("BEIRUT_DB_PATH")
DB_PATH = Path(_ENV_DB_PATH) if _ENV_DB_PATH else Path(__file__).resolve().parent.parent / "beirut.db"
BACKUP_DIR = DB_PATH.parent / "backups"

# ----------------------------- Connection -----------------------------------
def get_conn():
    """
    Short-lived connections with WAL+journal pragmas to reduce 'database is locked'
    on Windows and during concurrent reads/writes.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        # WAL is persistent per database file; leaving here is harmless and helpful
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        # Slight perf wins on Windows
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA mmap_size = 134217728;")  # 128MB
    except Exception:
        # Pragmas are best-effort; never fail connection because of them
        pass
    return conn

# ------------------------------ Migrations ----------------------------------
def _ensure_inventory_columns():
    """
    Add columns to 'products' table if this DB was created before inventory features:
      - stock_qty REAL DEFAULT 0
      - min_stock REAL DEFAULT 0
      - track_stock INTEGER NOT NULL DEFAULT 1
    """
    conn = get_conn()
    c = conn.cursor()
    c.execute("PRAGMA table_info(products)")
    cols = {r[1] for r in c.fetchall()}

    if "stock_qty" not in cols:
        c.execute("ALTER TABLE products ADD COLUMN stock_qty REAL DEFAULT 0")
    if "min_stock" not in cols:
        c.execute("ALTER TABLE products ADD COLUMN min_stock REAL DEFAULT 0")
    if "track_stock" not in cols:
        c.execute("ALTER TABLE products ADD COLUMN track_stock INTEGER NOT NULL DEFAULT 1")

    conn.commit()
    conn.close()

def _prime_default_settings(c):
    # Add any defaults you want to exist on a fresh DB
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('logo_path','')")
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('background_path','')")
    c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('accent_color','#C89A5B')")
    c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('category_order','')")
    c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('bar_printer','')")
    c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('cashier_printer','')")
    # You can add more defaults later (currency, service_pct, printers, etc.)
    # c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('currency','EGP')")
    # c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('service_pct','0')")

# -------------------------------- Schema ------------------------------------
def init_db():
    first_time = not os.path.exists(DB_PATH)
    # Ensure parent dir exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = get_conn()
    c = conn.cursor()

    # --- settings (e.g., logo path, printers, currency, etc.) ---
    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY, value TEXT
    )""")

    # --- users (NOTE: plaintext for now; switch to hashed later) ---
    c.execute("""CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role in ('admin','cashier')),
        secret_key TEXT
    )""")

    # --- catalog ---
    c.execute("""CREATE TABLE IF NOT EXISTS categories(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )""")
    # Include track_stock in the fresh schema
    c.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        price_cents INTEGER NOT NULL,
        stock_qty REAL DEFAULT 0,          -- inventory
        min_stock REAL DEFAULT 0,          -- low stock threshold
        track_stock INTEGER NOT NULL DEFAULT 1, -- 1 tracked, 0 unlimited/service
        FOREIGN KEY(category_id) REFERENCES categories(id),
        UNIQUE(category_id,name)
    )""")

    # --- orders & items & payments ---
    c.execute("""CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        table_code TEXT NOT NULL,
        opened_at TEXT NOT NULL,
        closed_at TEXT,
        status TEXT NOT NULL CHECK(status in ('open','paid','void')),
        opened_by TEXT NOT NULL,
        closed_by TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        price_cents INTEGER NOT NULL,
        qty REAL NOT NULL DEFAULT 1,
        note TEXT DEFAULT '',
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        method TEXT NOT NULL,        -- cash/visa
        amount_cents INTEGER NOT NULL,
        paid_at TEXT NOT NULL,
        cashier TEXT NOT NULL,
        FOREIGN KEY(order_id) REFERENCES orders(id)
    )""")

    # --- expenses (for monthly reports) ---
    c.execute("""CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        category TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        notes TEXT
    )""")

    # --- shifts (optional daily close) ---
    c.execute("""CREATE TABLE IF NOT EXISTS shifts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opened_at TEXT NOT NULL,
        closed_at TEXT,
        opened_by TEXT NOT NULL,
        closed_by TEXT,
        notes TEXT
    )""")

    # --- audit log (immutable) ---
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        username TEXT NOT NULL,
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_name TEXT,
        old_value TEXT,
        new_value TEXT,
        extra TEXT
    )""")

    conn.commit()

    # Fresh seeds on first run
    if first_time:
        _prime_default_settings(c)

        # default users (NOTE: plaintext just for seed; move to hashed soon)
        c.execute("INSERT OR REPLACE INTO users VALUES('admin','admin123','admin','ADMIN-DEFAULT-CHANGE-ME')")
        c.execute("INSERT OR REPLACE INTO users VALUES('cashier1','1234','cashier','C1-0000')")
        c.execute("INSERT OR REPLACE INTO users VALUES('cashier2','1234','cashier','C2-0000')")

        # seed catalog
        seed = {
            "Food": [("Chicken Plate",12000),("Burger",9500)],
            "Fresh Drinks":[("Fresh Orange",7000),("Lemon Mint",8000)],
            "Smoothies":[("Berry Smoothie",11000),("Mango Smoothie",11000)],
            "Coffee Corner":[("Espresso",4000),("Iced Latte",9000),("Cappuccino",8000)],
            "Hot Drinks":[("Tea",3000),("Hot Chocolate",8000)],
            "Desserts":[("Cheesecake",10000),("Brownie",8000)],
            "Soda Drinks":[("Coca-Cola",4000),("Sprite",4000)],
            "PlayStation 2 Players":[("PS 2P / hour",5000)],
            "PlayStation 4 Players":[("PS 4P / hour",8000)],
            "Sheshaaaa":[("Normal Single",8000),("Normal Double",12000),("Iced Single",9000),("Iced Double",13000),("Special Mix",15000)],
            "Cocktails":[("Pina Colada (virgin)",12000),("Strawberry Mojito",12000)],
            "Ice Cream":[("2 Scoops",6000),("3 Scoops",8000)],
            "Mixes":[("Energy Mix",14000)],
            "Shakes / Milk":[("Chocolate Shake",11000),("Vanilla Milkshake",10000),("Strawberry Milkshake",10000)],
        }
        for cat, items in seed.items():
            c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)",(cat,))
            c.execute("SELECT id FROM categories WHERE name=?",(cat,))
            cid = c.fetchone()["id"]
            for n,p in items:
                # Seed tracked items with stock=100, min=5, track_stock=1
                c.execute("""INSERT OR IGNORE INTO products(category_id,name,price_cents,stock_qty,min_stock,track_stock)
                             VALUES(?,?,?,?,?,1)""",(cid,n,p,100,5))
        conn.commit()

    # For existing DBs created before inventory/track flags, ensure columns exist
    _ensure_inventory_columns()

    conn.close()

# ------------------------------ Utilities -----------------------------------
def log_action(username, action, entity_type=None, entity_name=None, old_value=None, new_value=None, extra=None):
    conn = get_conn(); c = conn.cursor()
    c.execute("""INSERT INTO audit_log(ts,username,action,entity_type,entity_name,old_value,new_value,extra)
                 VALUES(?,?,?,?,?,?,?,?)""",
              (datetime.utcnow().isoformat(), username, action, entity_type, entity_name, old_value, new_value, extra))
    conn.commit(); conn.close()

def setting_get(key, default=""):
    conn = get_conn(); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?",(key,))
    r = c.fetchone(); conn.close()
    return r["value"] if r else default

def setting_get_int(key, default=0):
    v = setting_get(key, None)
    try:
        return int(v)
    except Exception:
        return default

def setting_set(key, value):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(key,value))
    conn.commit(); conn.close()

# ------------------------------- Backups ------------------------------------
def backup_now() -> Path:
    """
    Make a timestamped SQLite backup using the online backup API.
    Returns the backup file path.
    """
    BACKUP_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dst = BACKUP_DIR / f"beirut-{ts}.db"

    src = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(dst)
    try:
        with dst_conn:
            src.backup(dst_conn)
    finally:
        src.close()
        dst_conn.close()
    return dst
