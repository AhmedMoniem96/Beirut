"""User authentication and admin user-management helpers."""

from dataclasses import dataclass

from .db import db_transaction, get_conn


class UsernameExistsError(Exception):
    """Raised when attempting to create a user with an existing username."""


def _user_exists(cur, username: str) -> bool:
    cur.execute("SELECT 1 FROM users WHERE username=?", (username,))
    return cur.fetchone() is not None

@dataclass(slots=True)
class User:
    username: str
    role: str  # 'admin' | 'cashier'

def authenticate(username: str, password: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT username, role FROM users WHERE username=? AND password=?", (username, password))
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return User(username=row["username"], role=row["role"])

def list_users() -> list[dict]:
    """Return all registered users with their role and secret key."""

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT username, role, COALESCE(secret_key, '') AS secret_key
        FROM users
        ORDER BY role DESC, username
        """
    )
    rows = [dict(row) for row in cur.fetchall()]
    conn.close()
    return rows


def update_user(
    username: str,
    *,
    password: str | None = None,
    role: str | None = None,
    secret_key: str | None = None,
) -> bool:
    """Update fields for an existing user."""

    username = (username or "").strip()
    if not username:
        raise ValueError("اسم المستخدم مطلوب.")

    assignments: list[str] = []
    params: list[str] = []

    if password is not None:
        password_clean = password.strip()
        if not password_clean:
            raise ValueError("كلمة المرور الجديدة مطلوبة.")
        assignments.append("password=?")
        params.append(password_clean)

    new_role: str | None = None
    if role is not None:
        role_clean = role.strip().lower()
        if role_clean not in {"admin", "cashier"}:
            raise ValueError("الدور يجب أن يكون 'admin' أو 'cashier'.")
        assignments.append("role=?")
        params.append(role_clean)
        new_role = role_clean

    if secret_key is not None:
        assignments.append("secret_key=?")
        params.append(secret_key.strip())

    if not assignments:
        return False

    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        if not row:
            raise ValueError("المستخدم غير موجود.")

        current_role = row["role"]
        if new_role is not None and current_role == "admin" and new_role != "admin":
            cur.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
            admin_count = int(cur.fetchone()[0])
            if admin_count <= 1:
                raise ValueError("لا يمكن إزالة آخر مدير في النظام.")

        sql = f"UPDATE users SET {', '.join(assignments)} WHERE username=?"
        params.append(username)
        cur.execute(sql, params)

    return True


def delete_user(username: str, *, force: bool = False) -> bool:
    """Delete the given username if it exists.

    When ``force`` is True, dependent session rows are removed first to
    prevent foreign key errors. The primary seeded admin account (``admin``)
    cannot be removed via the force path.
    """

    username = (username or "").strip()
    if not username:
        raise ValueError("اسم المستخدم مطلوب.")

    with db_transaction() as conn:
        cur = conn.cursor()
        cur.execute("SELECT role FROM users WHERE username=?", (username,))
        row = cur.fetchone()
        if not row:
            raise ValueError("المستخدم غير موجود.")

        if row["role"] == "admin":
            cur.execute("SELECT COUNT(*) FROM users WHERE role='admin'")
            admin_count = int(cur.fetchone()[0])
            if admin_count <= 1:
                raise ValueError("لا يمكن حذف آخر مدير في النظام.")

        if force:
            if username.lower() == "admin":
                raise ValueError("لا يمكن حذف المدير الرئيسي.")
            cur.execute("DELETE FROM user_sessions WHERE username=?", (username,))

        cur.execute("DELETE FROM users WHERE username=?", (username,))

    return True

def reset_password_with_secret(username: str, secret_key: str, new_password: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT secret_key FROM users WHERE username=?", (username,))
        row = cur.fetchone()
    finally:
        conn.close()

    if not row or (row["secret_key"] or "") != secret_key:
        return False

    with db_transaction() as write_conn:
        write_conn.execute(
            "UPDATE users SET password=? WHERE username=?",
            (new_password, username),
        )
    return True


def create_user(username: str, password: str, role: str = "cashier", secret_key: str = ""):
    """Insert a new user row, ensuring the username is unique."""

    role = (role or "cashier").strip().lower()
    if role not in {"admin", "cashier"}:
        raise ValueError("الدور يجب أن يكون 'admin' أو 'cashier'.")

    username = username.strip()
    if not username:
        raise ValueError("اسم المستخدم مطلوب.")

    password = password.strip()
    if not password:
        raise ValueError("كلمة المرور مطلوبة.")

    conn = get_conn()
    cur = conn.cursor()
    try:
        if _user_exists(cur, username):
            raise UsernameExistsError(f"المستخدم '{username}' موجود مسبقًا.")
    finally:
        conn.close()

    with db_transaction() as write_conn:
        write_conn.execute(
            "INSERT INTO users(username, password, role, secret_key) VALUES(?,?,?,?)",
            (username, password, role, secret_key.strip()),
        )

    return User(username=username, role=role)
