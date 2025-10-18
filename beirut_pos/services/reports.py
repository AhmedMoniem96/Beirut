"""Daily summary helpers for Beirut POS."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List

from ..core.db import get_conn
from ..core.money import cents_to_le, fmt_le, to_le


@dataclass(slots=True)
class PaymentBreakdown:
    method: str
    amount_le: Decimal


@dataclass(slots=True)
class EndOfDaySummary:
    day: date
    total_sales: Decimal
    refunds: Decimal
    cash_in_drawer: Decimal
    total_purchases: Decimal
    by_method: List[PaymentBreakdown]

    def as_dict(self) -> Dict[str, str]:
        return {
            "day": self.day.isoformat(),
            "total_sales": fmt_le(self.total_sales),
            "refunds": fmt_le(self.refunds),
            "cash_in_drawer": fmt_le(self.cash_in_drawer),
            "total_purchases": fmt_le(self.total_purchases),
            "by_method": [
                {"method": b.method, "amount": fmt_le(b.amount_le)} for b in self.by_method
            ],
        }


def _range_for_day(day: date) -> tuple[str, str]:
    start = datetime.combine(day, datetime.min.time()).isoformat()
    end = datetime.combine(day, datetime.max.time()).isoformat()
    return start, end


def load_end_of_day(day: date | None = None) -> EndOfDaySummary:
    target = day or date.today()
    start, end = _range_for_day(target)
    conn = get_conn()
    cur = conn.cursor()

    by_method_rows = cur.execute(
        """
        SELECT method, SUM(amount_cents) AS amt
        FROM payments
        WHERE paid_at BETWEEN ? AND ?
        GROUP BY method
        ORDER BY method
        """,
        (start, end),
    ).fetchall()

    by_method = [
        PaymentBreakdown(method=row["method"], amount_le=cents_to_le(row["amt"]))
        for row in by_method_rows
    ]
    total_sales = sum((entry.amount_le for entry in by_method), Decimal("0"))

    cash_row = cur.execute(
        """
        SELECT SUM(amount_cents) AS cash_total
        FROM payments
        WHERE method='cash' AND paid_at BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()
    cash_in_drawer = cents_to_le(cash_row["cash_total"] or 0)

    # Refunds currently tracked as negative cash payments
    refunds_row = cur.execute(
        """
        SELECT SUM(amount_cents) AS refund_total
        FROM payments
        WHERE amount_cents < 0 AND paid_at BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()
    refunds = cents_to_le(abs(refunds_row["refund_total"] or 0))

    purchases_row = cur.execute(
        """
        SELECT SUM(amount_le) AS total
        FROM purchases
        WHERE deleted_at IS NULL AND created_at BETWEEN ? AND ?
        """,
        (start, end),
    ).fetchone()
    total_purchases = to_le(purchases_row["total"] or 0)

    conn.close()
    return EndOfDaySummary(
        day=target,
        total_sales=total_sales,
        refunds=refunds,
        cash_in_drawer=cash_in_drawer,
        total_purchases=total_purchases,
        by_method=by_method,
    )
