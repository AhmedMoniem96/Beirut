"""Authentication helpers for Jewelry app."""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Tuple

from beirut_pos.core.config_store import get_config_value
from beirut_pos.core.db import get_conn

from .session import SessionUser


PBKDF2_ITERATIONS = 120_000
ADMIN_ROLE = "Admin"


class UsernameExistsError(Exception):
    """Raised when attempting to create a user with an existing username."""


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


def create_user(
    username: str,
    password: str,
    *,
    full_name: str,
    role: str = "Cashier",
    is_active: bool = True,
) -> SessionUser:
    username = username.strip()
    if not username:
        raise ValueError("Username is required.")

    password = password.strip()
    if not password:
        raise ValueError("Password is required.")

    full_name = full_name.strip()
    if not full_name:
        raise ValueError("Full name is required.")

    role = role.strip() if role else "Cashier"
    if role not in {"Admin", "Cashier"}:
        raise ValueError("Role must be Admin or Cashier.")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM jw_users WHERE username = ?", (username,))
    if cur.fetchone():
        conn.close()
        raise UsernameExistsError(f"Username '{username}' already exists.")

    now = datetime.now().isoformat(timespec="seconds")
    password_hash = hash_password(password)
    cur.execute(
        """INSERT INTO jw_users
           (username, password_hash, full_name, role, is_active, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (username, password_hash, full_name, role, 1 if is_active else 0, now),
    )
    user_id = cur.lastrowid
    conn.commit()
    conn.close()
    return SessionUser(
        id=user_id,
        username=username,
        full_name=full_name,
        role=role,
    )


def reset_password(
    username: str,
    new_password: str,
    *,
    admin_username: str = "",
    admin_password: str = "",
    secret_key: str = "",
) -> Tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Enter the username to reset."

    new_password = new_password.strip()
    if not new_password:
        return False, "Enter a new password."

    secret_key = secret_key.strip()
    if secret_key:
        expected = str(get_config_value("jw_admin_secret_key", "")).strip()
        if not expected or secret_key != expected:
            return False, "Secret key is invalid."
    else:
        admin_username = admin_username.strip()
        admin_password = admin_password.strip()
        if not admin_username or not admin_password:
            return False, "Admin credentials or a secret key are required."
        admin_result = authenticate_user(admin_username, admin_password)
        if not admin_result.user or admin_result.user.role != ADMIN_ROLE:
            return False, "Admin credentials are invalid."

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id FROM jw_users WHERE username = ?", (username,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "User not found."
    password_hash = hash_password(new_password)
    cur.execute(
        "UPDATE jw_users SET password_hash = ? WHERE username = ?",
        (password_hash, username),
    )
    conn.commit()
    conn.close()
    return True, "Password updated successfully."


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
