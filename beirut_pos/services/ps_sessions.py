# beirut_pos/services/ps_sessions.py
from datetime import datetime
from typing import Optional
from .orders import PSSession


def load_ps_session_from_db(table_code: str) -> Optional[PSSession]:
    """Load PS session from database for a table."""
    from .core.db import get_conn

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT table_code, mode, started_at, total_seconds FROM ps_sessions WHERE table_code=?",
        (table_code,)
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    # Convert database row to PSSession object
    started_raw = row["started_at"] or ""
    try:
        started_at = datetime.fromisoformat(started_raw)
    except Exception:
        started_at = datetime.utcnow()

    return PSSession(
        mode=row["mode"],
        started_at=started_at,
        total_seconds=int(row["total_seconds"] or 0),
    )