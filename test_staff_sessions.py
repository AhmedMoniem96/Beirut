import importlib
import sys


def _reload_staff_modules(monkeypatch, data_dir):
    monkeypatch.setenv("BEIRUTPOS_DATA_DIR", str(data_dir))

    existing_db = sys.modules.get("beirut_pos.core.db")
    if existing_db:
        try:
            existing_db.close_engine()
        except Exception:
            pass

    for mod in (
        "beirut_pos.core.paths",
        "beirut_pos.core.db",
        "beirut_pos.services.staff",
    ):
        sys.modules.pop(mod, None)

    import beirut_pos.core.db as db
    import beirut_pos.services.staff as staff

    importlib.reload(db)
    importlib.reload(staff)
    return db, staff


def _prepare_users(conn):
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users(username, password, role) VALUES(?, ?, ?)",
        ("alice", "x", "admin"),
    )
    cur.execute(
        "INSERT OR IGNORE INTO users(username, password, role) VALUES(?, ?, ?)",
        ("bob", "x", "cashier"),
    )
    conn.commit()


def test_end_session_sets_logout_at(tmp_path, monkeypatch):
    db, staff = _reload_staff_modules(monkeypatch, tmp_path / "beirut_data")
    db.safe_migrations()

    conn = db.get_conn()
    _prepare_users(conn)

    session_id = staff.start_session("alice", workstation="ps-1")
    assert session_id is not None

    staff.end_session(session_id)

    cur = conn.cursor()
    cur.execute("SELECT logout_at, duration_seconds FROM user_sessions WHERE id=?", (session_id,))
    row = cur.fetchone()

    assert row is not None
    assert row["logout_at"] is not None
    assert int(row["duration_seconds"] or 0) >= 0

    conn.close()
    db.close_engine()


def test_start_session_closes_stale_for_same_user_and_workstation(tmp_path, monkeypatch):
    db, staff = _reload_staff_modules(monkeypatch, tmp_path / "beirut_data")
    db.safe_migrations()

    conn = db.get_conn()
    _prepare_users(conn)

    first = staff.start_session("alice", workstation="ps-1")
    second = staff.start_session("alice", workstation="ps-1")

    cur = conn.cursor()
    cur.execute("SELECT logout_at FROM user_sessions WHERE id=?", (first,))
    first_row = cur.fetchone()
    cur.execute("SELECT logout_at FROM user_sessions WHERE id=?", (second,))
    second_row = cur.fetchone()

    assert first_row["logout_at"] is not None
    assert second_row["logout_at"] is None

    conn.close()
    db.close_engine()


def test_switch_user_flow_writes_logout_at_for_previous_session(tmp_path, monkeypatch):
    db, staff = _reload_staff_modules(monkeypatch, tmp_path / "beirut_data")
    db.safe_migrations()

    conn = db.get_conn()
    _prepare_users(conn)

    previous_session = staff.start_session("alice", workstation="playstation-main-window")
    staff.end_session(previous_session)

    new_session = staff.start_session("bob", workstation="playstation-main-window")

    cur = conn.cursor()
    cur.execute("SELECT logout_at FROM user_sessions WHERE id=?", (previous_session,))
    previous_row = cur.fetchone()
    cur.execute("SELECT logout_at FROM user_sessions WHERE id=?", (new_session,))
    new_row = cur.fetchone()

    assert previous_row["logout_at"] is not None
    assert new_row["logout_at"] is None

    conn.close()
    db.close_engine()


def test_close_stale_open_sessions_closes_duplicates(tmp_path, monkeypatch):
    db, staff = _reload_staff_modules(monkeypatch, tmp_path / "beirut_data")
    db.safe_migrations()

    conn = db.get_conn()
    _prepare_users(conn)

    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_sessions(username, login_at, workstation) VALUES(?, datetime('now'), ?)",
        ("alice", "ps-2"),
    )
    first = cur.lastrowid
    cur.execute(
        "INSERT INTO user_sessions(username, login_at, workstation) VALUES(?, datetime('now'), ?)",
        ("alice", "ps-2"),
    )
    second = cur.lastrowid
    conn.commit()

    closed = staff.close_stale_open_sessions("alice", workstation="ps-2", exclude_session_id=second)
    assert first in closed
    assert second not in closed

    cur.execute("SELECT logout_at FROM user_sessions WHERE id=?", (first,))
    assert cur.fetchone()["logout_at"] is not None
    cur.execute("SELECT logout_at FROM user_sessions WHERE id=?", (second,))
    assert cur.fetchone()["logout_at"] is None

    conn.close()
    db.close_engine()
