# beirut_pos/services/ps_sessions.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from ..core.db import get_conn


def _ensure_iso_with_tz(value: str | None) -> Optional[str]:
    """Return ISO string with timezone if possible, else None."""
    if not value:
        return None
    # assume value is an ISO string saved by backend; try to normalize to tz-aware ISO
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        # value might already be a plain string that isn't ISO; return as-is
        return str(value)


def load_ps_session_from_db(table_code: str) -> Optional[Dict[str, Any]]:
    """
    Load playstation session for `table_code` from DB.

    Returns either None (no session) or dict:
      {
        "mode": "P2" or "P4",
        "started_at": "2025-10-21T12:34:56+00:00",   # ISO string (tz-aware if possible)
        "total_seconds": 1234                         # persisted accumulated seconds
      }
    """
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT mode, started_at, total_seconds FROM ps_sessions WHERE table_code=?",
            (table_code,),
        ).fetchone()
        if not row:
            return None

        # row[...] is sqlite3.Row (mapping-like)
        mode = row["mode"] if "mode" in row.keys() else row[0]
        started_at = row["started_at"] if "started_at" in row.keys() else row[1]
        total_seconds = row["total_seconds"] if "total_seconds" in row.keys() else row[2]

        return {
            "mode": mode,
            "started_at": _ensure_iso_with_tz(started_at),
            "total_seconds": int(total_seconds or 0),
        }
    finally:
        conn.close()
