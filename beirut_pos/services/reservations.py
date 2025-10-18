"""Persistence helpers for reservations management."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..core.bus import bus
from ..core.db import db_transaction, get_conn

_VALID_STATUS = {"pending", "seated", "cancelled"}


def _normalize_status(status: str | None) -> str:
    if not status:
        return "pending"
    normalized = str(status).strip().lower()
    return normalized if normalized in _VALID_STATUS else "pending"


def list_reservations() -> list[dict]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, name, phone, party_size, reserved_for, table_code, status, notes
               FROM reservations
               ORDER BY reserved_for, id"""
    )
    rows = [
        {
            "id": row["id"],
            "name": row["name"],
            "phone": row["phone"],
            "party_size": row["party_size"],
            "reserved_for": row["reserved_for"],
            "table_code": row["table_code"],
            "status": row["status"],
            "notes": row["notes"],
        }
        for row in cur.fetchall()
    ]
    conn.close()
    return rows


def create_reservation(
    *,
    name: str,
    reserved_for: str,
    phone: str = "",
    party_size: int = 1,
    table_code: str = "",
    notes: str = "",
    status: str = "pending",
    created_by: str = "system",
) -> int:
    cleaned_table = table_code.strip().upper() if table_code else ""
    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO reservations(name, phone, party_size, reserved_for, table_code, notes, status, created_at, created_by)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
            (
                name.strip(),
                phone.strip(),
                int(party_size or 1),
                reserved_for,
                cleaned_table,
                notes.strip(),
                _normalize_status(status),
                datetime.utcnow().isoformat(),
                created_by,
            ),
        )
        reservation_id = int(cur.lastrowid)
    bus.emit("reservations_changed")
    return reservation_id


def update_status(reservation_id: int, status: str) -> None:
    normalized = _normalize_status(status)
    with db_transaction() as conn:
        conn.execute(
            "UPDATE reservations SET status=? WHERE id=?",
            (normalized, int(reservation_id)),
        )
    bus.emit("reservations_changed")


def delete_reservation(reservation_id: int) -> None:
    with db_transaction() as conn:
        conn.execute("DELETE FROM reservations WHERE id=?", (int(reservation_id),))
    bus.emit("reservations_changed")


def get_active_reservations_map(now: datetime | None = None) -> dict[str, str]:
    """Return upcoming reservations keyed by table code.

    Only reservations that are still pending and have a table assigned are
    included. We keep reservations scheduled in the near future (or the recent
    past) so the floor map can highlight them until they are seated or
    cancelled.
    """

    reference = now or datetime.now()
    cutoff = reference - timedelta(hours=4)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT table_code, reserved_for
        FROM reservations
        WHERE status='pending' AND TRIM(table_code) <> ''
        ORDER BY reserved_for
        """
    )
    mapping: dict[str, str] = {}
    rows = cur.fetchall()
    conn.close()

    for row in rows:
        table_code = (row["table_code"] or "").strip().upper()
        if not table_code:
            continue
        reserved_raw = row["reserved_for"]
        if not reserved_raw:
            continue
        try:
            reserved_dt = datetime.fromisoformat(reserved_raw)
        except Exception:
            # If parsing fails, still expose the raw value so the UI can show it.
            mapping[table_code] = str(reserved_raw)
            continue
        if reserved_dt < cutoff:
            continue
        mapping[table_code] = reserved_dt.isoformat()

    return mapping

