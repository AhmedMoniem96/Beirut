# beirut_pos/services/ps_sessions.py
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from ..core.db import get_conn

def _parse_iso(dt_iso: str | None) -> Optional[datetime]:
    if not dt_iso:
        return None
    try:
        dt = datetime.fromisoformat(dt_iso)
        # ensure timezone-awareness: consider naive stored times as UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def load_ps_session_from_db(table_code: str) -> Optional[Dict[str, Any]]:
    """
    Return a dict for a given table or None:
    {
      "table_code": "T10",
      "mode": "P2" or "P4",
      "started_at": "2025-10-22T13:00:00Z" (string as stored),
      "total_seconds": 123   # persisted accumulated seconds before current run
    }
    """
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT table_code, mode, started_at, total_seconds FROM ps_sessions WHERE table_code=?",
            (table_code.upper(),),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "table_code": r["table_code"],
            "mode": r["mode"],
            "started_at": r["started_at"],
            "total_seconds": int(r["total_seconds"] or 0),
        }
    finally:
        conn.close()

def load_all_ps_sessions_from_db() -> Dict[str, Dict[str, Any]]:
    """
    Return mapping table_code -> session dict (same shape as load_ps_session_from_db).
    """
    out: Dict[str, Dict[str, Any]] = {}
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT table_code, mode, started_at, total_seconds FROM ps_sessions")
        for r in cur.fetchall():
            out[r["table_code"]] = {
                "table_code": r["table_code"],
                "mode": r["mode"],
                "started_at": r["started_at"],
                "total_seconds": int(r["total_seconds"] or 0),
            }
    finally:
        conn.close()
    return out
