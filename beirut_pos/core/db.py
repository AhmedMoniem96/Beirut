import os, sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).resolve().parent.parent / "beirut.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    first_time = not os.path.exists(DB_PATH)
    conn = get_conn(); c = conn.cursor()

    # --- settings (e.g., logo path) ---
    c.execute("""CREATE TABLE IF NOT EXISTS settings(
        key TEXT PRIMARY KEY, value TEXT
    )""")

    # --- users ---
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
    c.execute("""CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        price_cents INTEGER NOT NULL,
        stock_qty REAL DEFAULT 0,          -- inventory
        min_stock REAL DEFAULT 0,          -- low stock threshold
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

    if first_time:
        # default settings
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('logo_path','')")
        # default users
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
                c.execute("""INSERT OR IGNORE INTO products(category_id,name,price_cents,stock_qty,min_stock)
                             VALUES(?,?,?,?,?)""",(cid,n,p,100,5))
        conn.commit()
    conn.close()

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

def setting_set(key, value):
    conn = get_conn(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",(key,value))
    conn.commit(); conn.close()
