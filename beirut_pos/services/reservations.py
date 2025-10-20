"""Persistence helpers for reservations management."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from ..core.bus import bus
from ..core.db import db_transaction, get_conn

logger = logging.getLogger(__name__)

_VALID_STATUS = {"pending", "seated", "cancelled"}
_MAX_PARTY_SIZE = 100


class ReservationError(Exception):
    """Base exception for reservation-related errors"""
    pass


def _normalize_status(status: str | None) -> str:
    """Normalize reservation status to valid value"""
    if not status:
        return "pending"
    normalized = str(status).strip().lower()
    return normalized if normalized in _VALID_STATUS else "pending"


def _normalize_table_codes(table_codes: str | list[str] | None) -> list[str]:
    """
    Normalize table codes to a list of uppercase strings.
    Accepts: "T01", "T01,T02", ["T01", "T02"], or None
    Returns: ["T01", "T02"] or []
    """
    if not table_codes:
        return []

    # If it's a string, split by comma
    if isinstance(table_codes, str):
        codes = [c.strip().upper() for c in table_codes.split(",") if c.strip()]
    # If it's a list, process each item
    elif isinstance(table_codes, list):
        codes = [str(c).strip().upper() for c in table_codes if str(c).strip()]
    else:
        return []

    # Remove duplicates while preserving order
    seen = set()
    result = []
    for code in codes:
        if code and code not in seen:
            seen.add(code)
            result.append(code)

    return result


def _serialize_table_codes(table_codes: list[str]) -> str:
    """Convert list of table codes to comma-separated string"""
    return ",".join(table_codes) if table_codes else ""


def _deserialize_table_codes(raw: str | None) -> list[str]:
    """Parse comma-separated table codes from database"""
    if not raw:
        return []
    return [c.strip().upper() for c in str(raw).split(",") if c.strip()]


def list_reservations() -> list[dict]:
    """Get all reservations with table codes as list"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, name, phone, party_size, reserved_for, table_code, status, notes
                   FROM reservations
                   ORDER BY reserved_for, id"""
        )
        rows = []
        for row in cur.fetchall():
            rows.append({
                "id": row["id"],
                "name": row["name"],
                "phone": row["phone"],
                "party_size": row["party_size"],
                "reserved_for": row["reserved_for"],
                "table_codes": _deserialize_table_codes(row["table_code"]),  # Returns list
                "table_code": row["table_code"],  # Keep for backward compatibility
                "status": row["status"],
                "notes": row["notes"],
            })
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Failed to list reservations: {e}")
        return []


def create_reservation(
    *,
    name: str,
    reserved_for: str,
    phone: str = "",
    party_size: int = 1,
    table_code: str | list[str] = "",  # Now accepts string or list
    notes: str = "",
    status: str = "pending",
    created_by: str = "system",
) -> int:
    """
    Create a new reservation.

    Args:
        name: Guest name (required)
        reserved_for: ISO datetime string (required)
        phone: Contact phone
        party_size: Number of people (1-100)
        table_code: Single table "T01" or multiple "T01,T02" or ["T01", "T02"]
        notes: Additional notes
        status: pending/seated/cancelled
        created_by: Username creating the reservation

    Returns:
        reservation_id

    Raises:
        ReservationError: If validation fails
    """
    try:
        # Validate name
        cleaned_name = name.strip()
        if not cleaned_name:
            raise ReservationError("اسم العميل مطلوب")

        # Validate party size
        party = int(party_size or 1)
        if party < 1:
            raise ReservationError("عدد الأشخاص يجب أن يكون على الأقل 1")
        if party > _MAX_PARTY_SIZE:
            raise ReservationError(f"عدد الأشخاص لا يمكن أن يتجاوز {_MAX_PARTY_SIZE}")

        # Validate reserved_for datetime
        if not reserved_for:
            raise ReservationError("وقت الحجز مطلوب")
        try:
            datetime.fromisoformat(reserved_for)
        except Exception:
            raise ReservationError("صيغة وقت الحجز غير صالحة")

        # Normalize table codes
        table_codes_list = _normalize_table_codes(table_code)
        table_codes_str = _serialize_table_codes(table_codes_list)

        with db_transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO reservations(name, phone, party_size, reserved_for, table_code, notes, status, created_at, created_by)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    cleaned_name,
                    phone.strip(),
                    party,
                    reserved_for,
                    table_codes_str,
                    notes.strip(),
                    _normalize_status(status),
                    datetime.utcnow().isoformat(),
                    created_by,
                ),
            )
            reservation_id = int(cur.lastrowid)

        bus.emit("reservations_changed")
        logger.info(f"Created reservation #{reservation_id} for '{cleaned_name}' - {party} people on tables {table_codes_str}")
        return reservation_id

    except ReservationError:
        raise
    except Exception as e:
        logger.error(f"Failed to create reservation: {e}")
        raise ReservationError(f"فشل إنشاء الحجز: {e}")


def update_reservation(
    reservation_id: int,
    *,
    name: str | None = None,
    phone: str | None = None,
    party_size: int | None = None,
    reserved_for: str | None = None,
    table_code: str | list[str] | None = None,
    notes: str | None = None,
    status: str | None = None,
) -> bool:
    """
    Update an existing reservation.
    Only provided fields will be updated.

    Returns:
        True if reservation was found and updated

    Raises:
        ReservationError: If validation fails
    """
    try:
        with db_transaction() as conn:
            cur = conn.cursor()

            # Check if reservation exists
            cur.execute("SELECT id FROM reservations WHERE id=?", (int(reservation_id),))
            if not cur.fetchone():
                return False

            updates = []
            params = []

            if name is not None:
                cleaned_name = name.strip()
                if not cleaned_name:
                    raise ReservationError("اسم العميل مطلوب")
                updates.append("name=?")
                params.append(cleaned_name)

            if phone is not None:
                updates.append("phone=?")
                params.append(phone.strip())

            if party_size is not None:
                party = int(party_size)
                if party < 1:
                    raise ReservationError("عدد الأشخاص يجب أن يكون على الأقل 1")
                if party > _MAX_PARTY_SIZE:
                    raise ReservationError(f"عدد الأشخاص لا يمكن أن يتجاوز {_MAX_PARTY_SIZE}")
                updates.append("party_size=?")
                params.append(party)

            if reserved_for is not None:
                try:
                    datetime.fromisoformat(reserved_for)
                except Exception:
                    raise ReservationError("صيغة وقت الحجز غير صالحة")
                updates.append("reserved_for=?")
                params.append(reserved_for)

            if table_code is not None:
                table_codes_list = _normalize_table_codes(table_code)
                table_codes_str = _serialize_table_codes(table_codes_list)
                updates.append("table_code=?")
                params.append(table_codes_str)

            if notes is not None:
                updates.append("notes=?")
                params.append(notes.strip())

            if status is not None:
                updates.append("status=?")
                params.append(_normalize_status(status))

            if not updates:
                return True  # Nothing to update

            params.append(int(reservation_id))
            sql = f"UPDATE reservations SET {', '.join(updates)} WHERE id=?"
            cur.execute(sql, params)

        bus.emit("reservations_changed")
        logger.info(f"Updated reservation #{reservation_id}")
        return True

    except ReservationError:
        raise
    except Exception as e:
        logger.error(f"Failed to update reservation #{reservation_id}: {e}")
        raise ReservationError(f"فشل تحديث الحجز: {e}")


def update_status(reservation_id: int, status: str) -> None:
    """Update reservation status (backward compatibility wrapper)"""
    try:
        normalized = _normalize_status(status)
        with db_transaction() as conn:
            conn.execute(
                "UPDATE reservations SET status=? WHERE id=?",
                (normalized, int(reservation_id)),
            )
        bus.emit("reservations_changed")
    except Exception as e:
        logger.error(f"Failed to update status for reservation #{reservation_id}: {e}")
        raise ReservationError(f"فشل تحديث حالة الحجز: {e}")


def delete_reservation(reservation_id: int) -> None:
    """Delete a reservation"""
    try:
        with db_transaction() as conn:
            conn.execute("DELETE FROM reservations WHERE id=?", (int(reservation_id),))
        bus.emit("reservations_changed")
        logger.info(f"Deleted reservation #{reservation_id}")
    except Exception as e:
        logger.error(f"Failed to delete reservation #{reservation_id}: {e}")
        raise ReservationError(f"فشل حذف الحجز: {e}")


def get_active_reservations_map(now: datetime | None = None) -> dict[str, str]:
    """
    Return upcoming reservations keyed by table code.

    Now supports multiple tables - each table code gets its own entry.
    Example: {"T01": "2025-01-20T19:00:00", "T02": "2025-01-20T19:00:00"}

    Only reservations that are still pending and have tables assigned are
    included. We keep reservations scheduled in the near future (or recent
    past) so the floor map can highlight them until seated or cancelled.
    """
    try:
        reference = now or datetime.now()
        cutoff = reference - timedelta(hours=4)

        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT table_code, reserved_for
            FROM reservations
            WHERE status='pending' AND TRIM(COALESCE(table_code, '')) <> ''
            ORDER BY reserved_for
            """
        )
        mapping: dict[str, str] = {}
        rows = cur.fetchall()
        conn.close()

        for row in rows:
            raw_tables = row["table_code"] or ""
            table_codes = _deserialize_table_codes(raw_tables)

            if not table_codes:
                continue

            reserved_raw = row["reserved_for"]
            if not reserved_raw:
                continue

            try:
                reserved_dt = datetime.fromisoformat(reserved_raw)
                if reserved_dt < cutoff:
                    continue
                reserved_str = reserved_dt.isoformat()
            except Exception:
                # If parsing fails, use raw value
                reserved_str = str(reserved_raw)

            # Add entry for EACH table code
            for table_code in table_codes:
                if table_code:
                    mapping[table_code] = reserved_str

        return mapping

    except Exception as e:
        logger.error(f"Failed to get active reservations map: {e}")
        return {}


def get_reservation(reservation_id: int) -> dict | None:
    """Get a single reservation by ID"""
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute(
            """SELECT id, name, phone, party_size, reserved_for, table_code, status, notes, created_at, created_by
                   FROM reservations
                   WHERE id=?""",
            (int(reservation_id),)
        )
        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row["id"],
            "name": row["name"],
            "phone": row["phone"],
            "party_size": row["party_size"],
            "reserved_for": row["reserved_for"],
            "table_codes": _deserialize_table_codes(row["table_code"]),
            "table_code": row["table_code"],  # Backward compatibility
            "status": row["status"],
            "notes": row["notes"],
            "created_at": row["created_at"],
            "created_by": row["created_by"],
        }
    except Exception as e:
        logger.error(f"Failed to get reservation #{reservation_id}: {e}")
        return None