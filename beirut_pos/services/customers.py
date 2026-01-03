"""Customer and loyalty ledger helpers."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Optional

from ..core.db import db_transaction, get_conn


def _normalize_phone(phone: str | None) -> str:
    if not phone:
        return ""
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("+"):
        return "+" + re.sub(r"\D", "", cleaned[1:])
    return re.sub(r"\D", "", cleaned)


def create_customer(
    name: str,
    *,
    phone: str | None = None,
    email: str | None = None,
    birthday: str | None = None,
    notes: str | None = None,
) -> int:
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise ValueError("Customer name is required.")
    normalized_phone = _normalize_phone(phone)
    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO customers(name, phone, email, birthday, notes, created_at)
               VALUES(?,?,?,?,?,?)""",
            (
                cleaned_name,
                normalized_phone or None,
                (email or "").strip() or None,
                (birthday or "").strip() or None,
                (notes or "").strip() or None,
                datetime.utcnow().isoformat(),
            ),
        )
        return int(cur.lastrowid)


def update_customer(
    customer_id: int,
    *,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    birthday: str | None = None,
    notes: str | None = None,
) -> None:
    fields = {}
    if name is not None:
        fields["name"] = (name or "").strip()
    if phone is not None:
        normalized = _normalize_phone(phone)
        fields["phone"] = normalized or None
    if email is not None:
        fields["email"] = (email or "").strip() or None
    if birthday is not None:
        fields["birthday"] = (birthday or "").strip() or None
    if notes is not None:
        fields["notes"] = (notes or "").strip() or None

    if not fields:
        return

    assignments = ", ".join(f"{key}=?" for key in fields)
    values = list(fields.values())
    values.append(customer_id)
    with db_transaction() as conn:
        conn.execute(f"UPDATE customers SET {assignments} WHERE id=?", values)


def get_customer(customer_id: int) -> Optional[dict[str, Any]]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, email, birthday, notes, created_at
            FROM customers
            WHERE id=?
            """,
            (customer_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_customer_by_phone(phone: str) -> Optional[dict[str, Any]]:
    normalized = _normalize_phone(phone)
    if not normalized:
        return None
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, phone, email, birthday, notes, created_at
            FROM customers
            WHERE phone=?
            """,
            (normalized,),
        )
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def record_loyalty_entry(
    customer_id: int,
    delta_points: int,
    *,
    reason: str | None = None,
    order_id: int | None = None,
    conn=None,
) -> None:
    if not delta_points:
        return
    created_at = datetime.utcnow().isoformat()
    if conn is not None:
        conn.execute(
            """INSERT INTO loyalty_ledger(customer_id, delta_points, reason, order_id, created_at)
               VALUES(?,?,?,?,?)""",
            (customer_id, int(delta_points), reason, order_id, created_at),
        )
        return
    with db_transaction() as tx:
        tx.execute(
            """INSERT INTO loyalty_ledger(customer_id, delta_points, reason, order_id, created_at)
               VALUES(?,?,?,?,?)""",
            (customer_id, int(delta_points), reason, order_id, created_at),
        )


def get_loyalty_balance(customer_id: int, *, conn=None) -> int:
    if conn is not None:
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(delta_points), 0) AS balance FROM loyalty_ledger WHERE customer_id=?",
            (customer_id,),
        )
        row = cur.fetchone()
        return int(row["balance"] if row else 0)
    conn_local = get_conn()
    try:
        cur = conn_local.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(delta_points), 0) AS balance FROM loyalty_ledger WHERE customer_id=?",
            (customer_id,),
        )
        row = cur.fetchone()
        return int(row["balance"] if row else 0)
    finally:
        conn_local.close()


def compute_accrual_points(total_cents: int) -> int:
    return max(int(total_cents) // 100, 0)
