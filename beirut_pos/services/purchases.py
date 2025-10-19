"""Services for recording and reviewing stock purchases/expenses."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from ..core.db import db_transaction, get_conn, log_action


@dataclass(slots=True)
class PurchaseRecord:
    """Typed representation of a purchase row for rich UI rendering."""

    id: int
    purchased_at: datetime
    supplier: str
    invoice_no: str
    amount_cents: int
    notes: str
    recorded_by: str | None

    @property
    def display_notes(self) -> str:
        return (self.notes or "").strip()


def _parse_timestamp(raw: str) -> datetime:
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        # SQLite might return a space separated format if inserted differently.
        try:
            return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return datetime.utcnow()


def _rows_to_records(rows: Sequence[dict]) -> list[PurchaseRecord]:
    records: list[PurchaseRecord] = []
    for row in rows:
        records.append(
            PurchaseRecord(
                id=row["id"],
                purchased_at=_parse_timestamp(row["purchased_at"]),
                supplier=row["supplier"],
                invoice_no=row["invoice_no"] or "",
                amount_cents=int(row["amount_cents"]),
                notes=row["notes"] or "",
                recorded_by=row["recorded_by"],
            )
        )
    return records


def list_purchases(limit: int = 250) -> list[PurchaseRecord]:
    """Return the most recent purchases, newest first."""

    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, purchased_at, supplier, invoice_no, amount_cents, notes, recorded_by "
            "FROM purchases ORDER BY datetime(purchased_at) DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return _rows_to_records(rows)


def create_purchase(
    *,
    supplier: str,
    amount_cents: int,
    recorded_by: str,
    purchased_at: datetime | None = None,
    invoice_no: str = "",
    notes: str = "",
) -> PurchaseRecord:
    """Persist a new purchase entry and return the resulting record."""

    supplier = (supplier or "").strip()
    if not supplier:
        raise ValueError("supplier is required")

    try:
        amount_cents = int(amount_cents)
    except (TypeError, ValueError) as exc:
        raise ValueError("amount_cents must be an integer") from exc

    if amount_cents <= 0:
        raise ValueError("amount must be positive")

    when = purchased_at or datetime.utcnow()
    stamp = when.replace(microsecond=0).isoformat(sep=" ")
    invoice_no = (invoice_no or "").strip()
    notes = (notes or "").strip()
    recorded_by = (recorded_by or "").strip() or "system"

    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO purchases(purchased_at, supplier, invoice_no, amount_cents, notes, recorded_by)
            VALUES(?,?,?,?,?,?)
            """,
            (stamp, supplier, invoice_no, amount_cents, notes, recorded_by),
        )
        purchase_id = cur.lastrowid

    log_action(
        recorded_by,
        "create_purchase",
        entity_type="purchase",
        entity_name=supplier,
        new_value=str(amount_cents),
        extra=invoice_no or notes,
    )

    return get_purchase(purchase_id)


def get_purchase(purchase_id: int) -> PurchaseRecord:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, purchased_at, supplier, invoice_no, amount_cents, notes, recorded_by "
            "FROM purchases WHERE id=?",
            (purchase_id,),
        )
        row = cur.fetchone()
        if not row:
            raise LookupError(f"purchase {purchase_id} not found")
    finally:
        conn.close()
    return _rows_to_records([row])[0]

