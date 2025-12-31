"""Authentication helpers for Jewelry app."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from beirut_pos.core.db import get_conn

from .session import SessionUser


PBKDF2_ITERATIONS = 120_000


@dataclass(frozen=True)
class AuthResult:
    user: Optional[SessionUser]
    message: str


def ensure_default_admin() -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jw_users")
    count = cur.fetchone()[0] or 0
    if count == 0:
        now = datetime.now().isoformat(timespec="seconds")
        password_hash = hash_password("admin123")
        cur.execute(
            """INSERT INTO jw_users
               (username, password_hash, full_name, role, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("admin", password_hash, "Administrator", "Admin", 1, now),
        )
        conn.commit()
        conn.close()
        return True
    conn.close()
    return False


def get_default_admin_warning() -> Optional[str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM jw_users")
    count = cur.fetchone()[0] or 0
    warning = None
    if count == 1:
        cur.execute("SELECT username FROM jw_users LIMIT 1")
        username = cur.fetchone()[0]
        if username == "admin":
            warning = (
                "Default admin account is active (admin/admin123). "
                "Please change the password and create a new user."
            )
    conn.close()
    return warning


def authenticate_user(username: str, password: str) -> AuthResult:
    if not username or not password:
        return AuthResult(None, "Enter username and password.")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, username, password_hash, full_name, role, is_active
           FROM jw_users WHERE username = ?""",
        (username,),
    )
    row = cur.fetchone()
    if not row:
        _record_login_attempt(cur, username, False)
        conn.commit()
        conn.close()
        return AuthResult(None, "Invalid username or password.")
    user_id, username, password_hash, full_name, role, is_active = row
    if not is_active:
        _record_login_attempt(cur, username, False)
        conn.commit()
        conn.close()
        return AuthResult(None, "User is inactive. Contact admin.")
    if not verify_password(password, password_hash):
        _record_login_attempt(cur, username, False)
        conn.commit()
        conn.close()
        return AuthResult(None, "Invalid username or password.")
    _record_login_attempt(cur, username, True)
    conn.commit()
    conn.close()
    return AuthResult(
        SessionUser(
            id=user_id,
            username=username,
            full_name=full_name,
            role=role,
        ),
        "",
    )


def hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash or "$" not in stored_hash:
        return False
    salt_hex, digest_hex = stored_hash.split("$", 1)
    try:
        salt = bytes.fromhex(salt_hex)
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    ).hex()
    return hmac.compare_digest(digest, digest_hex)


def _record_login_attempt(cur, username: str, success: bool) -> None:
    cur.execute(
        """INSERT INTO jw_login_audit(username, success, timestamp)
           VALUES (?, ?, ?)""",
        (username, 1 if success else 0, datetime.now().isoformat(timespec="seconds")),
    )
