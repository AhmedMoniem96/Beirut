# beirut_pos/services/orders.py
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Tuple, Optional

from ..core.bus import bus

from ..core.db import db_transaction, get_conn, init_db, log_action, setting_get, setting_set

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


def _ensure_order_item_notes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(order_items)")
    cols = {r[1] for r in cur.fetchall()}
    if "note" not in cols:
        cur.execute("ALTER TABLE order_items ADD COLUMN note TEXT DEFAULT ''")
    conn.commit()
    conn.close()


_ensure_order_item_notes()

_CATEGORY_ORDER_KEY = "category_order"
_TABLE_CODES_KEY = "table_codes"


def _load_category_order() -> list[str]:
    raw = setting_get(_CATEGORY_ORDER_KEY, "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[str] = []
    for item in data:
        if isinstance(item, str):
            name = item.strip()
            if name and name not in out:
                out.append(name)
    return out


def _store_category_order(names: list[str]) -> None:
    cleaned: list[str] = []
    seen: set[str] = set()
    for name in names:
        if not isinstance(name, str):
            continue
        name = name.strip()
        if not name or name in seen:
            continue
        cleaned.append(name)
        seen.add(name)
    setting_set(_CATEGORY_ORDER_KEY, json.dumps(cleaned, ensure_ascii=False))


def get_category_order() -> list[str]:
    """Expose the persisted order for UI consumers (settings dialog)."""
    return _load_category_order()


def set_category_order(order: list[str]) -> None:
    _store_category_order(order)
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
        rows = cur.fetchall()
        preferred = _load_category_order()
        order_map = {name: idx for idx, name in enumerate(preferred)}
        if rows:
            missing = [r["name"] for r in rows if r["name"] not in order_map]
            if missing:
                preferred.extend(missing)
                _store_category_order(preferred)
                order_map = {name: idx for idx, name in enumerate(preferred)}

        rows.sort(key=lambda r: (order_map.get(r["name"], len(order_map)), r["id"]))

        out: List[Tuple[str, List[Tuple[str, int, int, Optional[float]]]]] = []
        for cat in rows:
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
            """SELECT p.id, p.name, p.price_cents, p.track_stock, p.stock_qty, p.min_stock, c.name as category
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
            "track_stock": int(row["track_stock"]),
            "stock_qty": row["stock_qty"],
            "min_stock": row["min_stock"],
            "category": row["category"],
        }

    def add_category(self, name: str):
        with db_transaction() as conn:
            conn.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)", (name,))
        bus.emit("catalog_changed")
        preferred = _load_category_order()
        if name not in preferred:
            preferred.append(name)
            _store_category_order(preferred)

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
        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM categories WHERE name=?", (category,))
            row = cur.fetchone()
            if row is None:
                cur.execute("INSERT INTO categories(name) VALUES(?)", (category,))
                cur.execute("SELECT id FROM categories WHERE name=?", (category,))
                row = cur.fetchone()
            cid = row["id"] if row else None
            if cid is None:
                raise RuntimeError("فشل إنشاء القسم الجديد")
            cur.execute(
                """INSERT INTO products(category_id, name, price_cents, stock_qty, min_stock, track_stock)
                   VALUES(?,?,?,?,?,?)""",
                (cid, label, price_cents, stock_qty, min_stock, track_stock),
            )
        log_action(username, "add_product", "product", f"{category}/{label}", None, str(price_cents))
        bus.emit("catalog_changed")

    def update_product_price(self, category: str, label: str, new_price_cents: int, username: str):
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT p.id, p.price_cents FROM products p
                   JOIN categories c ON c.id=p.category_id
                   WHERE c.name=? AND p.name=?""",
                (category, label),
            )
            row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return False
        old = row["price_cents"]
        with db_transaction() as write_conn:
            write_conn.execute(
                "UPDATE products SET price_cents=? WHERE id=?",
                (new_price_cents, row["id"]),
            )
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

    def dec_stock(self, label: str, qty: float = 1.0, conn=None) -> Optional[StockState]:
        """Decrement tracked items and return the new stock/min_stock."""
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
        """Return stock when removing a line, for tracked items."""
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
    note: str = ""

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
    __slots__ = ("catalog", "orders", "ps_sessions", "table_codes")

    def __init__(self):
        self.catalog = ProductCatalog()
        self.orders: Dict[str, Order] = {}          # table_code -> current open order
        self.ps_sessions: Dict[str, PSSession] = {} # table_code -> session
        self.table_codes: List[str] = _load_table_codes()
        self._load_open_orders()
        self._load_ps_sessions()
        self._sync_open_tables()

    def _load_open_orders(self):
        # Rehydrate open orders on startup
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM orders WHERE status='open'")
        for o in cur.fetchall():
            order = Order(id=o["id"], table_code=o["table_code"], status=o["status"], opened_by=o["opened_by"])
            cur.execute(
                "SELECT product_name, price_cents, qty, note FROM order_items WHERE order_id=?",
                (order.id,),
            )
            order.items = [
                OrderItem(
                    product=r["product_name"],
                    unit_price_cents=r["price_cents"],
                    qty=r["qty"],
                    note=r["note"] or "",
                )
                for r in cur.fetchall()
            ]
            self.orders[order.table_code] = order
            bus.emit("table_state_changed", order.table_code, "occupied")
            bus.emit("table_total_changed", order.table_code, order.total_cents)
        conn.close()

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

    def _sync_open_tables(self) -> None:
        missing = [code for code in self.orders.keys() if code not in self.table_codes]
        if not missing:
            return
        self.table_codes.extend(missing)
        _store_table_codes(self.table_codes)
        bus.emit("tables_changed", list(self.table_codes))

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
            """INSERT INTO orders(table_code, opened_at, status, opened_by)
               VALUES(?,?,?,?)""",
            (table_code, datetime.utcnow().isoformat(), "open", opened_by),
        )
        order = Order(id=cur.lastrowid, table_code=table_code, opened_by=opened_by)
        self.orders[table_code] = order
        return order, True

    # ----- add/remove items + inventory -----
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
                state = self.catalog.dec_stock(product, qty, conn=conn)
                _check_state(state)
                order.items.append(OrderItem(product, price_cents, qty, note=note))
                conn.execute(
                    "INSERT INTO order_items(order_id, product_name, price_cents, qty, note) VALUES(?,?,?,?,?)",
                    (order.id, product, price_cents, qty, note),
                )
            if created:
                bus.emit("table_state_changed", table_code, "occupied")
        else:
            with db_transaction() as conn:
                order, created = self._ensure_db_order_tx(conn, table_code, opened_by=cashier)
                order.items.append(OrderItem(product, price_cents, qty, note=note))
                conn.execute(
                    "INSERT INTO order_items(order_id, product_name, price_cents, qty, note) VALUES(?,?,?,?,?)",
                    (order.id, product, price_cents, qty, note),
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
            now = datetime.utcnow()
            elapsed = sess.total_seconds + max(0, int((now - sess.started_at).total_seconds()))
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
            with db_transaction() as conn:
                conn.execute("DELETE FROM ps_sessions WHERE table_code=?", (table_code,))
            bus.emit("ps_state_changed", table_code, False)

    def ps_start(self, table_code: str, mode: str):
        # if there’s an open session, bill it first
        self._close_session_and_bill(table_code)
        now = datetime.utcnow()
        self.ps_sessions[table_code] = PSSession(mode=mode, started_at=now)
        with db_transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ps_sessions(table_code, mode, started_at, total_seconds) VALUES(?,?,?,?)",
                (table_code, mode, now.isoformat(), 0),
            )
        bus.emit("ps_state_changed", table_code, True)

    def ps_switch(self, table_code: str, new_mode: str):
        self._close_session_and_bill(table_code)
        now = datetime.utcnow()
        self.ps_sessions[table_code] = PSSession(mode=new_mode, started_at=now)
        with db_transaction() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ps_sessions(table_code, mode, started_at, total_seconds) VALUES(?,?,?,?)",
                (table_code, new_mode, now.isoformat(), 0),
            )
        bus.emit("ps_state_changed", table_code, True)

    def ps_stop(self, table_code: str):
        self._close_session_and_bill(table_code)

    def snapshot_ps_sessions(self) -> None:
        if not self.ps_sessions:
            return
        with db_transaction() as conn:
            for table_code, sess in list(self.ps_sessions.items()):
                now = datetime.utcnow()
                elapsed = max(0, int((now - sess.started_at).total_seconds()))
                sess.total_seconds += elapsed
                sess.started_at = now
                conn.execute(
                    "INSERT OR REPLACE INTO ps_sessions(table_code, mode, started_at, total_seconds) VALUES(?,?,?,?)",
                    (table_code, sess.mode, sess.started_at.isoformat(), sess.total_seconds),
                )

    # ----- Payment / settle (persist and clear table) -----
    def settle(self, table_code: str, method: str = "cash", cashier: str = "cashier"):
        # Close any running PS session and bill it first
        self._close_session_and_bill(table_code)

        o = self.orders.get(table_code)
        if not o:
            return False

        amount = o.total_cents

        # Persist payment & close order in DB
        paid_at = datetime.utcnow().isoformat()
        with db_transaction() as conn:
            conn.execute(
                """INSERT INTO payments(order_id, method, amount_cents, paid_at, cashier)
                   VALUES(?,?,?,?,?)""",
                (o.id, method, amount, paid_at, cashier),
            )
            conn.execute(
                """UPDATE orders
                   SET status='paid', closed_at=?, closed_by=?
                   WHERE id=?""",
                (paid_at, cashier, o.id),
            )

        # Clear in-memory + update UI
        o.status = "paid"
        self.orders.pop(table_code, None)
        bus.emit("table_state_changed", table_code, "free")
        bus.emit("table_total_changed", table_code, 0)
        bus.emit("ps_state_changed", table_code, False)
        return True


# --- keep this at the VERY END of the file ---
order_manager = OrderManager()


def default_table_codes() -> List[str]:
    return _default_table_codes()


def get_table_codes() -> List[str]:
    return order_manager.get_table_codes()


def set_table_codes(codes: List[str], *, actor: str = "system") -> List[str]:
    return order_manager.set_table_codes(codes, actor=actor)
