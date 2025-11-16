"""Utility helpers for destructive maintenance actions (data purges, etc.)."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List

from ..core.db import db_transaction


def _delete_between(cur, table: str, column: str, start_iso: str, end_iso: str) -> int:
    cur.execute(f"DELETE FROM {table} WHERE {column} BETWEEN ? AND ?", (start_iso, end_iso))
    return max(int(cur.rowcount or 0), 0)


def _select_ids_between(cur, table: str, column: str, start_iso: str, end_iso: str) -> List[int]:
    cur.execute(f"SELECT id FROM {table} WHERE {column} BETWEEN ? AND ?", (start_iso, end_iso))
    return [int(row[0]) for row in cur.fetchall()]


def _delete_in_chunks(cur, table: str, column: str, values: Iterable[int], chunk_size: int = 200) -> int:
    total = 0
    chunk: List[int] = []
    for value in values:
        chunk.append(int(value))
        if len(chunk) >= chunk_size:
            placeholders = ",".join(["?"] * len(chunk))
            cur.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", chunk)
            total += int(cur.rowcount or 0)
            chunk.clear()
    if chunk:
        placeholders = ",".join(["?"] * len(chunk))
        cur.execute(f"DELETE FROM {table} WHERE {column} IN ({placeholders})", chunk)
        total += int(cur.rowcount or 0)
    return total


def purge_activity_between(start_dt: datetime, end_dt: datetime) -> Dict[str, int]:
    """Delete operational data that falls between two datetimes.

    Returns a dictionary with the count of deleted rows for each table.
    """

    if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime):
        raise ValueError("start_dt and end_dt must be datetime instances")
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt

    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    summary: Dict[str, int] = {
        "orders": 0,
        "order_items": 0,
        "order_payments": 0,
        "payments": 0,
        "purchases": 0,
        "expenses": 0,
        "reservations": 0,
        "audit_log": 0,
        "user_sessions": 0,
    }

    with db_transaction() as conn:
        cur = conn.cursor()

        order_ids = _select_ids_between(cur, "orders", "opened_at", start_iso, end_iso)
        if order_ids:
            summary["order_items"] = _delete_in_chunks(cur, "order_items", "order_id", order_ids)
            summary["order_payments"] = _delete_in_chunks(cur, "payments", "order_id", order_ids)
            summary["orders"] = _delete_in_chunks(cur, "orders", "id", order_ids)

        summary["payments"] = _delete_between(cur, "payments", "paid_at", start_iso, end_iso)
        summary["purchases"] = _delete_between(cur, "purchases", "purchased_at", start_iso, end_iso)
        summary["expenses"] = _delete_between(cur, "expenses", "ts", start_iso, end_iso)
        summary["reservations"] = _delete_between(cur, "reservations", "created_at", start_iso, end_iso)
        summary["audit_log"] = _delete_between(cur, "audit_log", "ts", start_iso, end_iso)
        summary["user_sessions"] = _delete_between(cur, "user_sessions", "login_at", start_iso, end_iso)

    return summary
