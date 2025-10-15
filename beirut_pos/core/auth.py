from dataclasses import dataclass
from .db import get_conn

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

def set_secret_key(admin_user: str, target_username: str, secret_key: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET secret_key=? WHERE username=?", (secret_key, target_username))
    conn.commit()
    conn.close()

def reset_password_with_secret(username: str, secret_key: str, new_password: str) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT secret_key FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    if not row or (row["secret_key"] or "") != secret_key:
        conn.close()
        return False
    cur.execute("UPDATE users SET password=? WHERE username=?", (new_password, username))
    conn.commit()
    conn.close()
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
    if _user_exists(cur, username):
        conn.close()
        raise UsernameExistsError(f"المستخدم '{username}' موجود مسبقًا.")

    cur.execute(
        "INSERT INTO users(username, password, role, secret_key) VALUES(?,?,?,?)",
        (username, password, role, secret_key.strip()),
    )
    conn.commit()
    conn.close()

    return User(username=username, role=role)
