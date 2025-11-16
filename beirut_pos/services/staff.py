"""Staff utilities: payroll management and attendance tracking."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable, List, Optional

from ..core.db import db_transaction, get_conn


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Payroll helpers
# ---------------------------------------------------------------------------

def list_payroll_rows() -> List[Dict[str, int | str]]:
    """Return payroll info for all registered staff members."""

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            u.username,
            u.role,
            COALESCE(p.salary_cents, 0)       AS salary_cents,
            COALESCE(p.deductions_cents, 0)  AS deductions_cents,
            COALESCE(p.loan_cents, 0)        AS loan_cents
        FROM users u
        LEFT JOIN staff_payroll p ON p.username = u.username
        ORDER BY u.role DESC, u.username
        """
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def save_payroll_rows(entries: Iterable[Dict[str, float | int | str]]) -> None:
    """Persist payroll values for each username provided."""

    with db_transaction() as conn:
        cur = conn.cursor()
        for entry in entries:
            username = str(entry.get("username", "")).strip()
            if not username:
                continue
            salary = int(round(float(entry.get("salary_cents", 0))))
            deductions = int(round(float(entry.get("deductions_cents", 0))))
            loan = int(round(float(entry.get("loan_cents", 0))))
            if salary <= 0 and deductions <= 0 and loan <= 0:
                cur.execute("DELETE FROM staff_payroll WHERE username=?", (username,))
                continue
            cur.execute(
                """
                INSERT INTO staff_payroll(username, salary_cents, deductions_cents, loan_cents)
                VALUES(?,?,?,?)
                ON CONFLICT(username) DO UPDATE SET
                    salary_cents=excluded.salary_cents,
                    deductions_cents=excluded.deductions_cents,
                    loan_cents=excluded.loan_cents
                """,
                (username, salary, deductions, loan),
            )


# ---------------------------------------------------------------------------
# Attendance helpers
# ---------------------------------------------------------------------------

def start_session(username: str) -> Optional[int]:
    """Create a login session row for *username* and return its id."""

    clean = (username or "").strip()
    if not clean:
        return None
    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO user_sessions(username, login_at) VALUES(?, ?)",
            (clean, _now_iso()),
        )
        return cur.lastrowid


def end_session(session_id: Optional[int]) -> None:
    """Mark the given session as finished if it is still open."""

    if not session_id:
        return
    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT login_at, logout_at FROM user_sessions WHERE id=?",
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            return
        if row["logout_at"]:
            return
        login_at = _parse_iso(row["login_at"])
        now = datetime.utcnow()
        duration = 0
        if login_at is not None:
            duration = max(int((now - login_at).total_seconds()), 0)
        cur.execute(
            "UPDATE user_sessions SET logout_at=?, duration_seconds=? WHERE id=?",
            (now.isoformat(), duration, session_id),
        )


def summarize_session_hours(start_iso: str, end_iso: str) -> List[Dict[str, object]]:
    """Aggregate login duration per user between *start_iso* and *end_iso*."""

    start = _parse_iso(start_iso) or datetime.min
    end = _parse_iso(end_iso) or datetime.utcnow()
    if end < start:
        start, end = end, start
    now = datetime.utcnow()

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT s.id, s.username, s.login_at, s.logout_at, s.duration_seconds, u.role
        FROM user_sessions s
        JOIN users u ON u.username = s.username
        WHERE (s.logout_at IS NULL OR s.logout_at >= ?) AND s.login_at <= ?
        ORDER BY s.login_at
        """,
        (start.isoformat(), end.isoformat()),
    )
    rows = cur.fetchall()
    conn.close()

    totals: Dict[str, Dict[str, object]] = {}
    for row in rows:
        login_at = _parse_iso(row["login_at"])
        logout_at = _parse_iso(row["logout_at"]) if row["logout_at"] else None
        if login_at is None:
            continue
        session_start = max(login_at, start)
        session_end = min(logout_at or now, end)
        if session_end <= session_start:
            continue
        seconds = int((session_end - session_start).total_seconds())
        if seconds <= 0:
            continue
        username = row["username"]
        bucket = totals.setdefault(
            username,
            {"username": username, "role": row["role"], "sessions": 0, "seconds": 0},
        )
        bucket["sessions"] = int(bucket["sessions"]) + 1
        bucket["seconds"] = int(bucket["seconds"]) + seconds

    summary = sorted(totals.values(), key=lambda entry: str(entry["username"]).lower())
    for entry in summary:
        seconds = int(entry["seconds"])
        entry["hours"] = round(seconds / 3600.0, 2)
        entry["minutes"] = seconds // 60
    return summary


def list_sessions_between(start_dt: datetime, end_dt: datetime) -> List[Dict[str, object]]:
    """Return individual user sessions overlapping the provided window."""

    start = start_dt if isinstance(start_dt, datetime) else datetime.min
    end = end_dt if isinstance(end_dt, datetime) else datetime.utcnow()
    if end < start:
        start, end = end, start

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, username, login_at, logout_at
        FROM user_sessions
        WHERE (logout_at IS NULL OR logout_at >= ?) AND login_at <= ?
        ORDER BY login_at
        """,
        (start.isoformat(), end.isoformat()),
    )
    rows = cur.fetchall()
    conn.close()

    sessions: List[Dict[str, object]] = []
    for row in rows:
        login_at = _parse_iso(row["login_at"])
        logout_at = _parse_iso(row["logout_at"]) if row["logout_at"] else None
        if login_at is None:
            continue
        sessions.append(
            {
                "id": int(row["id"]),
                "username": row["username"],
                "login_at": login_at,
                "logout_at": logout_at,
            }
        )
    return sessions


def summarize_shift_activity(
    username: str, start_dt: datetime, end_dt: Optional[datetime] = None
) -> Dict[str, int]:
    """Return per-shift KPIs for *username* between two datetimes."""

    clean = (username or "").strip()
    if not clean or not isinstance(start_dt, datetime):
        return {
            "orders_opened": 0,
            "orders_closed": 0,
            "voided_orders": 0,
            "payments_count": 0,
            "payments_total_cents": 0,
            "discount_cents": 0,
            "window_start": None,
            "window_end": None,
            "duration_seconds": 0,
        }

    end_dt = end_dt or datetime.utcnow()
    if end_dt < start_dt:
        start_dt, end_dt = end_dt, start_dt

    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    conn = get_conn()
    cur = conn.cursor()

    def _scalar(sql: str, params: tuple[str, str, str]) -> int:
        cur.execute(sql, params)
        row = cur.fetchone()
        if not row:
            return 0
        value = row[0] if isinstance(row, tuple) else row[0]
        return int(value or 0)

    opened = _scalar(
        "SELECT COUNT(*) FROM orders WHERE opened_by=? AND opened_at BETWEEN ? AND ?",
        (clean, start_iso, end_iso),
    )
    closed = _scalar(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE closed_by=? AND closed_at IS NOT NULL AND closed_at BETWEEN ? AND ?
        """,
        (clean, start_iso, end_iso),
    )
    voided = _scalar(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE status='void' AND closed_by=? AND closed_at BETWEEN ? AND ?
        """,
        (clean, start_iso, end_iso),
    )
    discounts = _scalar(
        """
        SELECT CAST(COALESCE(SUM(discount_cents), 0) AS INTEGER)
        FROM orders
        WHERE closed_by=? AND closed_at BETWEEN ? AND ?
        """,
        (clean, start_iso, end_iso),
    )

    cur.execute(
        """
        SELECT COUNT(*) AS cnt, CAST(COALESCE(SUM(amount_cents), 0) AS INTEGER) AS total
        FROM payments
        WHERE cashier=? AND paid_at BETWEEN ? AND ?
        """,
        (clean, start_iso, end_iso),
    )
    payment_row = cur.fetchone()
    conn.close()

    payments_count = int(payment_row["cnt"] if payment_row and payment_row["cnt"] else 0)
    payments_total = int(payment_row["total"] if payment_row and payment_row["total"] else 0)

    duration_seconds = max(int((end_dt - start_dt).total_seconds()), 0)
    return {
        "orders_opened": opened,
        "orders_closed": closed,
        "voided_orders": voided,
        "payments_count": payments_count,
        "payments_total_cents": payments_total,
        "discount_cents": discounts,
        "window_start": start_dt,
        "window_end": end_dt,
        "duration_seconds": duration_seconds,
    }
