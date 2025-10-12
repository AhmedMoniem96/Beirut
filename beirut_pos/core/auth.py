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
