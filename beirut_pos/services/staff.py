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
    """Return payroll info for system users and manual staff."""

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            u.username,
            u.role,
            COALESCE(p.salary_cents, 0)       AS salary_cents,
            COALESCE(p.deductions_cents, 0)  AS deductions_cents,
            COALESCE(p.loan_cents, 0)        AS loan_cents,
            COALESCE(p.salary_period, 'monthly') AS salary_period
        FROM users u
        LEFT JOIN staff_payroll p ON p.username = u.username
        ORDER BY u.role DESC, u.username
        """
    )
    rows = [
        {
            "username": row["username"],
            "display_name": row["username"],
            "role": row["role"],
            "salary_cents": row["salary_cents"],
            "deductions_cents": row["deductions_cents"],
            "loan_cents": row["loan_cents"],
            "salary_period": row["salary_period"],
            "source": "system",
            "manual_id": None,
        }
        for row in cur.fetchall()
    ]

    cur.execute(
        """
        SELECT id, display_name, role, salary_cents, deductions_cents, loan_cents, salary_period
        FROM staff_manual
        WHERE active=1
        ORDER BY display_name COLLATE NOCASE
        """
    )
    manual_rows = [
        {
            "username": "",
            "display_name": row["display_name"],
            "role": row["role"],
            "salary_cents": row["salary_cents"],
            "deductions_cents": row["deductions_cents"],
            "loan_cents": row["loan_cents"],
            "salary_period": row["salary_period"],
            "source": "manual",
            "manual_id": row["id"],
        }
        for row in cur.fetchall()
    ]
    conn.close()
    return rows + manual_rows


def daily_payroll_expense() -> int:
    """Return the net daily payroll amount for all active staff."""

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        WITH combined AS (
            SELECT salary_cents, deductions_cents, loan_cents
            FROM staff_payroll
            WHERE salary_period='daily'
            UNION ALL
            SELECT salary_cents, deductions_cents, loan_cents
            FROM staff_manual
            WHERE active=1 AND salary_period='daily'
        )
        SELECT COALESCE(SUM(salary_cents - deductions_cents - loan_cents), 0) AS net_total
        FROM combined
        """
    )
    row = cur.fetchone()
    conn.close()
    value = int(row[0] or 0)
    return max(value, 0)


def save_payroll_rows(entries: Iterable[Dict[str, float | int | str]]) -> None:
    """Persist payroll values for each username provided."""

    normalized: list[dict[str, object]] = []
    with db_transaction() as conn:
        cur = conn.cursor()
        timestamp = _now_iso()
        for entry in entries:
            source = (entry.get("source") or "system").strip() or "system"
            salary_period = str(entry.get("salary_period") or "monthly").strip() or "monthly"
            salary = int(round(float(entry.get("salary_cents", 0) or 0)))
            deductions = int(round(float(entry.get("deductions_cents", 0) or 0)))
            loan = int(round(float(entry.get("loan_cents", 0) or 0)))
            role = str(entry.get("role", ""))
            display_name = str(entry.get("display_name", "")).strip()

            if source == "manual":
                manual_id = entry.get("manual_id")
                try:
                    manual_id_int = int(manual_id)
                except (TypeError, ValueError):
                    continue
                if not display_name:
                    continue
                cur.execute(
                    """
                    UPDATE staff_manual
                    SET display_name=?, role=?, salary_cents=?, deductions_cents=?, loan_cents=?,
                        salary_period=?, updated_at=?
                    WHERE id=? AND active=1
                    """,
                    (
                        display_name,
                        role,
                        salary,
                        deductions,
                        loan,
                        salary_period,
                        timestamp,
                        manual_id_int,
                    ),
                )
                normalized.append(
                    {
                        "source": source,
                        "username": "",
                        "manual_id": manual_id_int,
                        "display_name": display_name,
                        "role": role,
                        "salary_cents": salary,
                        "deductions_cents": deductions,
                        "loan_cents": loan,
                        "salary_period": salary_period,
                    }
                )
                continue

            username = str(entry.get("username", "")).strip()
            if not username:
                continue
            if salary <= 0 and deductions <= 0 and loan <= 0:
                cur.execute("DELETE FROM staff_payroll WHERE username=?", (username,))
                continue
            cur.execute(
                """
                INSERT INTO staff_payroll(username, salary_cents, deductions_cents, loan_cents, salary_period)
                VALUES(?,?,?,?,?)
                ON CONFLICT(username) DO UPDATE SET
                    salary_cents=excluded.salary_cents,
                    deductions_cents=excluded.deductions_cents,
                    loan_cents=excluded.loan_cents,
                    salary_period=excluded.salary_period
                """,
                (username, salary, deductions, loan, salary_period),
            )
            normalized.append(
                {
                    "source": "system",
                    "username": username,
                    "manual_id": None,
                    "display_name": display_name or username,
                    "role": role,
                    "salary_cents": salary,
                    "deductions_cents": deductions,
                    "loan_cents": loan,
                    "salary_period": salary_period,
                }
            )

        _record_payroll_history(cur, normalized)


def create_manual_staff(display_name: str, role: str = "") -> int:
    """Create a manual staff member entry for payroll tracking."""

    clean_name = (display_name or "").strip()
    if not clean_name:
        raise ValueError("display_name is required")
    role_text = (role or "").strip()
    now = _now_iso()
    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO staff_manual(display_name, role, created_at, updated_at)
            VALUES(?,?,?,?)
            """,
            (clean_name, role_text, now, now),
        )
        return cur.lastrowid


def list_payroll_history(start_iso: str, end_iso: str) -> List[Dict[str, object]]:
    """Return payroll snapshots recorded between *start_iso* and *end_iso*."""

    start = _parse_iso(start_iso) or datetime.min
    end = _parse_iso(end_iso) or datetime.utcnow()
    if end < start:
        start, end = end, start

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT recorded_at, source, username, manual_id, display_name, role, salary_period,
               salary_cents, deductions_cents, loan_cents, net_cents
        FROM staff_payroll_history
        WHERE recorded_at >= ? AND recorded_at <= ?
        ORDER BY recorded_at DESC, display_name COLLATE NOCASE
        """,
        (start.isoformat(), end.isoformat()),
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def _record_payroll_history(cur, rows: Iterable[Dict[str, object]]) -> None:
    """Persist a history snapshot for the given payroll rows."""

    payload = []
    recorded_at = _now_iso()
    for entry in rows:
        display_name = str(entry.get("display_name", "")).strip()
        if not display_name:
            continue
        salary = int(entry.get("salary_cents") or 0)
        deductions = int(entry.get("deductions_cents") or 0)
        loan = int(entry.get("loan_cents") or 0)
        payload.append(
            (
                recorded_at,
                entry.get("source") or "system",
                entry.get("username") or None,
                entry.get("manual_id") if entry.get("manual_id") else None,
                display_name,
                entry.get("role") or "",
                entry.get("salary_period") or "monthly",
                salary,
                deductions,
                loan,
                salary - deductions - loan,
            )
        )

    if not payload:
        return

    cur.executemany(
        """
        INSERT INTO staff_payroll_history(
            recorded_at, source, username, manual_id,
            display_name, role, salary_period,
            salary_cents, deductions_cents, loan_cents, net_cents
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        payload,
    )


def record_salary_payment(entry: Dict[str, object]) -> None:
    """Record a payroll payout snapshot for the provided employee entry."""

    display_name = str(entry.get("display_name", "")).strip()
    if not display_name:
        raise ValueError("display_name is required")

    normalized = {
        "source": entry.get("source") or "payout",
        "username": entry.get("username") or "",
        "manual_id": entry.get("manual_id"),
        "display_name": display_name,
        "role": entry.get("role") or "",
        "salary_period": entry.get("salary_period") or "monthly",
        "salary_cents": int(round(float(entry.get("salary_cents") or 0))),
        "deductions_cents": int(round(float(entry.get("deductions_cents") or 0))),
        "loan_cents": int(round(float(entry.get("loan_cents") or 0))),
    }

    with db_transaction() as conn:
        cur = conn.cursor()
        _record_payroll_history(cur, [normalized])


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
