# beirut_pos/services/orders.py
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from ..core.bus import bus
from ..core.db import get_conn, init_db, log_action

init_db()

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

    conn.commit()
    conn.close()

_ensure_inventory_columns()
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------


StockState = Tuple[Optional[float], Optional[float]]


class StockError(Exception):
    __slots__ = ()
    pass


class ProductCatalog:
    __slots__ = ()
    """
    Products table is assumed:
      id, category_id, name, price_cents, stock_qty, min_stock, track_stock
    - track_stock=1 → enforce stock (block when stock_qty <= 0, decrement/increment on add/remove)
    - track_stock=0 → services/unlimited (ignore stock)
    - stock_qty may be NULL for non-tracked items
    """

    def categories(self) -> List[Tuple[str, List[Tuple[str, int, int, Optional[float]]]]]:
        """
        Returns: [(cat_name, [(name, price_cents, track_stock, stock_qty), ...]), ...]
        Kept backward-compatible for your UI (it can ignore extra tuple fields).
        """
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM categories ORDER BY id")
        out: List[Tuple[str, List[Tuple[str, int, int, Optional[float]]]]] = []
        for cat in cur.fetchall():
            cur.execute(
                "SELECT name, price_cents, track_stock, stock_qty "
                "FROM products WHERE category_id=? ORDER BY id",
                (cat["id"],),
            )
            items = [
                (r["name"], r["price_cents"], int(r["track_stock"]), r["stock_qty"])
                for r in cur.fetchall()
            ]
            out.append((cat["name"], items))
        conn.close()
        return out

    def get_product(self, name: str) -> Optional[dict]:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, price_cents, track_stock, stock_qty, min_stock FROM products WHERE name=?",
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
            "track_stock": int(row["track_stock"]),
            "stock_qty": row["stock_qty"],
            "min_stock": row["min_stock"],
        }

    def add_category(self, name: str):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (name,))
        conn.commit()
        conn.close()
        bus.emit("catalog_changed")

    def add_product(
        self,
        category: str,
        label: str,
        price_cents: int,
        username: str = "admin",
        *,
        track_stock: int = 1,
        stock_qty: Optional[float] = 0,
        min_stock: Optional[float] = 0,
    ):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE name=?", (category,))
        row = cur.fetchone()
        if row is None:
            cur.execute("INSERT INTO categories(name) VALUES(?)", (category,))
            conn.commit()
            cur.execute("SELECT id FROM categories WHERE name=?", (category,))
            row = cur.fetchone()
        cid = row["id"]
        cur.execute(
            """INSERT INTO products(category_id, name, price_cents, stock_qty, min_stock, track_stock)
               VALUES(?,?,?,?,?,?)""",
            (cid, label, price_cents, stock_qty, min_stock, track_stock),
        )
        conn.commit()
        conn.close()
        log_action(username, "add_product", "product", f"{category}/{label}", None, str(price_cents))
        bus.emit("catalog_changed")

    def update_product_price(self, category: str, label: str, new_price_cents: int, username: str):
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT p.id, p.price_cents FROM products p
               JOIN categories c ON c.id=p.category_id
               WHERE c.name=? AND p.name=?""",
            (category, label),
        )
        row = cur.fetchone()
        if not row:
            conn.close()
            return False
        old = row["price_cents"]
        cur.execute("UPDATE products SET price_cents=? WHERE id=?", (new_price_cents, row["id"]))
        conn.commit()
        conn.close()
        log_action(
            username,
            "price_change",
            "product",
            f"{category}/{label}",
            str(old),
            str(new_price_cents),
        )
        bus.emit("catalog_changed")
        return True

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

    def dec_stock(self, label: str, qty: float = 1.0) -> Optional[StockState]:
        """Decrement tracked items and return the new stock/min_stock."""
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE products SET stock_qty = MAX(0, COALESCE(stock_qty,0) - ?) "
            "WHERE name=? AND track_stock=1",
            (qty, label),
        )
        state = self._fetch_stock_state(cur, label)
        conn.commit()
        conn.close()
        return state

    def inc_stock(self, label: str, qty: float = 1.0) -> Optional[StockState]:
        """Return stock when removing a line, for tracked items."""
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE products SET stock_qty = COALESCE(stock_qty,0) + ? "
            "WHERE name=? AND track_stock=1",
            (qty, label),
        )
        state = self._fetch_stock_state(cur, label)
        conn.commit()
        conn.close()
        return state

    def get_low_stock(self) -> List[Tuple[str, Optional[float], Optional[float]]]:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT name, stock_qty, min_stock FROM products WHERE track_stock=1 AND stock_qty <= min_stock")
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
               WHERE c.name=? ORDER BY p.id LIMIT 1""",
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

    @property
    def total_cents(self) -> int:
        return int(self.unit_price_cents * self.qty)


@dataclass(slots=True)
class Order:
    id: int
    table_code: str
    items: List[OrderItem] = field(default_factory=list)
    status: str = "open"  # open/paid/void
    discount_cents: int = 0
    opened_by: str = ""

    @property
    def subtotal_cents(self) -> int:
        return sum(i.total_cents for i in self.items)

    @property
    def total_cents(self) -> int:
        return max(self.subtotal_cents - self.discount_cents, 0)


@dataclass(slots=True)
class PSSession:
    mode: str
    started_at: datetime
    total_seconds: int = 0


class OrderManager:
    __slots__ = ("catalog", "orders", "ps_sessions")

    def __init__(self):
        self.catalog = ProductCatalog()
        self.orders: Dict[str, Order] = {}          # table_code -> current open order
        self.ps_sessions: Dict[str, PSSession] = {} # table_code -> session
        self._load_open_orders()

    def _load_open_orders(self):
        # Rehydrate open orders on startup
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE status='open'")
        for o in cur.fetchall():
            order = Order(id=o["id"], table_code=o["table_code"], status=o["status"], opened_by=o["opened_by"])
            cur.execute("SELECT product_name, price_cents, qty FROM order_items WHERE order_id=?", (order.id,))
            order.items = [
                OrderItem(product=r["product_name"], unit_price_cents=r["price_cents"], qty=r["qty"])
                for r in cur.fetchall()
            ]
            self.orders[order.table_code] = order
            bus.emit("table_state_changed", order.table_code, "occupied")
            bus.emit("table_total_changed", order.table_code, order.total_cents)
        conn.close()

    @property
    def categories(self):
        return self.catalog.categories()

    def _ensure_db_order(self, table_code: str, opened_by: str) -> Order:
        if table_code in self.orders and self.orders[table_code].status == "open":
            return self.orders[table_code]
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO orders(table_code, opened_at, status, opened_by)
               VALUES(?,?,?,?)""",
            (table_code, datetime.utcnow().isoformat(), "open", opened_by),
        )
        conn.commit()
        oid = cur.lastrowid
        conn.close()
        order = Order(id=oid, table_code=table_code, opened_by=opened_by)
        self.orders[table_code] = order
        bus.emit("table_state_changed", table_code, "occupied")
        return order

    # ----- add/remove items + inventory -----
    def add_item(self, table_code: str, product: str, price_cents: int, qty: float = 1.0, cashier: str = "cashier"):
        """
        Enforces stock for tracked products; ignores stock for services/unlimited.
        If the 'product' is not found in DB (e.g., PS billing line), treat as non-tracked.
        """
        # Resolve product record (if exists)
        prod = self.catalog.get_product(product)

        if prod and prod["track_stock"] == 1:
            stock = float(prod["stock_qty"]) if prod["stock_qty"] is not None else 0.0
            if stock < qty:
                raise StockError(f"المنتج '{product}' غير متوفر في المخزون")
            # decrement immediately so UI reflects new stock
            state = self.catalog.dec_stock(product, qty)
            new_stock = state[0] if state else None
            min_stock = state[1] if state else None
            if new_stock is not None and stock > 0 and new_stock <= 0:
                bus.emit("catalog_changed")
            if (
                new_stock is not None
                and min_stock is not None
                and stock >= min_stock
                and new_stock <= min_stock
            ):
                bus.emit("inventory_low", product, stock, new_stock, min_stock)
                log_action(
                    cashier,
                    "inventory_low",
                    "product",
                    product,
                    str(stock),
                    str(new_stock),
                )

        # ensure order exists and persist line
        order = self._ensure_db_order(table_code, opened_by=cashier)
        order.items.append(OrderItem(product, price_cents, qty))

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO order_items(order_id, product_name, price_cents, qty) VALUES(?,?,?,?)",
            (order.id, product, price_cents, qty),
        )
        conn.commit()
        conn.close()

        # table total update
        bus.emit("table_total_changed", table_code, order.total_cents)

    def remove_item(self, table_code: str, index: int, username: str = "system"):
        order = self.orders.get(table_code)
        if not order:
            return
        if 0 <= index < len(order.items):
            item = order.items.pop(index)

            # return stock if tracked
            prod = self.catalog.get_product(item.product)
            if prod and prod["track_stock"] == 1:
                before = float(prod["stock_qty"]) if prod["stock_qty"] is not None else 0.0
                state = self.catalog.inc_stock(item.product, item.qty)
                new_stock = state[0] if state else None
                min_stock = state[1] if state else None
                if before <= 0 and new_stock is not None and new_stock > 0:
                    bus.emit("catalog_changed")
                if (
                    new_stock is not None
                    and min_stock is not None
                    and before <= min_stock < new_stock
                ):
                    bus.emit("inventory_recovered", item.product, before, new_stock, min_stock)
                    log_action(
                        username,
                        "inventory_recovered",
                        "product",
                        item.product,
                        str(before),
                        str(new_stock),
                    )

            # remove one matching row from DB
            conn = get_conn()
            cur = conn.cursor()
            cur.execute(
                """DELETE FROM order_items WHERE id IN (
                     SELECT id FROM order_items
                     WHERE order_id=? AND product_name=? AND price_cents=? AND qty=?
                     LIMIT 1
                   )""",
                (order.id, item.product, item.unit_price_cents, item.qty),
            )
            conn.commit()
            conn.close()
            bus.emit("table_total_changed", table_code, order.total_cents)

    def get_items(self, table_code: str):
        o = self.orders.get(table_code)
        return [] if not o else o.items

    def get_totals(self, table_code: str):
        o = self.orders.get(table_code)
        if not o:
            return 0, 0, 0
        return o.subtotal_cents, o.discount_cents, o.total_cents

    def apply_discount(self, table_code: str, amount_cents: int):
        o = self.orders.get(table_code)
        if not o:
            return
        o.discount_cents = max(amount_cents, 0)
        bus.emit("table_total_changed", table_code, o.total_cents)

    def clear_discount(self, table_code: str):
        o = self.orders.get(table_code)
        if not o:
            return
        o.discount_cents = 0
        bus.emit("table_total_changed", table_code, o.total_cents)

    # ----- PlayStation -----
    def _close_session_and_bill(self, table_code: str):
        sess = self.ps_sessions.get(table_code)
        if not sess:
            return
        try:
            elapsed = sess.total_seconds + max(0, int((datetime.now() - sess.started_at).total_seconds()))
            minutes = max(1, elapsed // 60)
            rate = self.catalog.get_ps_rate_hour_cents(sess.mode)
            if rate and rate > 0:
                per_min = rate / 60.0
                amount = int(round(per_min * minutes))
            else:
                amount = 0  # no configured rate => bill zero gracefully
            label = "PS ٢ لاعبين" if sess.mode == "P2" else "PS ٤ لاعبين"
            detail = f"{label} — {minutes} دقيقة"
            # PS line is NOT a DB product → non-tracked
            self.add_item(table_code, detail, amount)
        finally:
            self.ps_sessions.pop(table_code, None)
            bus.emit("ps_state_changed", table_code, False)

    def ps_start(self, table_code: str, mode: str):
        # if there’s an open session, bill it first
        self._close_session_and_bill(table_code)
        self.ps_sessions[table_code] = PSSession(mode=mode, started_at=datetime.now())
        bus.emit("ps_state_changed", table_code, True)

    def ps_switch(self, table_code: str, new_mode: str):
        self._close_session_and_bill(table_code)
        self.ps_sessions[table_code] = PSSession(mode=new_mode, started_at=datetime.now())
        bus.emit("ps_state_changed", table_code, True)

    def ps_stop(self, table_code: str):
        self._close_session_and_bill(table_code)

    # ----- Payment / settle (persist and clear table) -----
    def settle(self, table_code: str, method: str = "cash", cashier: str = "cashier"):
        # Close any running PS session and bill it first
        self._close_session_and_bill(table_code)

        o = self.orders.get(table_code)
        if not o:
            return False

        amount = o.total_cents

        # Persist payment & close order in DB
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO payments(order_id, method, amount_cents, paid_at, cashier)
               VALUES(?,?,?,?,?)""",
            (o.id, method, amount, datetime.utcnow().isoformat(), cashier),
        )
        cur.execute(
            """UPDATE orders
               SET status='paid', closed_at=?, closed_by=?
               WHERE id=?""",
            (datetime.utcnow().isoformat(), cashier, o.id),
        )
        conn.commit()
        conn.close()

        # Clear in-memory + update UI
        o.status = "paid"
        self.orders.pop(table_code, None)
        bus.emit("table_state_changed", table_code, "free")
        bus.emit("table_total_changed", table_code, 0)
        bus.emit("ps_state_changed", table_code, False)
        return True


# --- keep this at the VERY END of the file ---
order_manager = OrderManager()
