"""Dynamic UI text registry with database-backed overrides and caching."""

from __future__ import annotations

import json
import sqlite3
from typing import Dict, Iterable, Mapping

from ..core.bus import bus
from ..core.db import db_transaction, get_conn

# Default bundle of UI strings. Values may contain str.format placeholders
# which are expanded at call sites.
DEFAULT_TEXTS: Dict[str, str] = {
    # Application chrome -----------------------------------------------------
    "app.window_title": "{client_name} POS — {username} ({role})",
    "app.window_title_fallback": "{client_name} POS",

    # Login dialog -----------------------------------------------------------
    "login.window_title": "تسجيل الدخول — {client_name}",
    "login.brand_title": "{client_name}",
    "login.hero": "مرحباً بكم في نظام نقاط البيع الخاص بنا — ترتيب الطلبات أصبح أسهل",
    "login.hero_hint": "جهز فريقك، تابع الطاولات، وراقب الأداء في نظرة واحدة.",
    "login.form_title": "تسجيل الدخول",
    "login.form_hint": "أدخل بياناتك للمتابعة",
    "login.username_placeholder": "اسم المستخدم",
    "login.password_placeholder": "كلمة المرور",
    "login.submit": "تسجيل الدخول",
    "login.forgot": "هل نسيت كلمة المرور؟",
    "login.create_user": "إنشاء حساب موظف جديد",
    "login.error": "بيانات غير صحيحة. حاول مرة أخرى.",
    "login.create_success": "تم إنشاء الحساب. أدخل كلمة المرور وسجل الدخول.",

    # Main window toolbar ---------------------------------------------------
    "main.toolbar.back": "رجوع",
    "main.toolbar.switch": "تبديل المستخدم",
    "main.toolbar.manage_products": "إدارة الأصناف (مدير)",
    "main.toolbar.users": "إدارة المستخدمين",
    "main.toolbar.reports": "التقارير",
    "main.toolbar.tables": "إدارة الطاولات",
    "main.toolbar.purchases": "المشتريات",
    "main.toolbar.reservations": "الحجوزات",
    "main.toolbar.settings": "الإعدادات",
    "main.banner.close": "✕",
    "main.tables.title": "الطاولات — اختر طاولة",
    "main.order.header": "طلب:",
    "main.order.print_bar": "🧾 بار",
    "main.order.print_cashier": "🧾 كاشير",

    # License gate ----------------------------------------------------------
    "license.block.title": "تم حظر التطبيق",
    "license.block.message": "انتهت الفترة التجريبية لـ {client_name}. أدخل رمز التفعيل للمتابعة.",
    "license.block.input": "رمز التفعيل",
    "license.block.submit": "تأكيد",
    "license.block.cancel": "إغلاق",
    "license.block.error": "رمز غير صحيح. حاول مرة أخرى.",

    # Receipts --------------------------------------------------------------
    "receipt.bar.header": "تذكرة البار",
    "receipt.bar.table": "الطاولة: {table_code}",
    "receipt.bar.issued_at": "وقت الإصدار: {timestamp}",
    "receipt.note": "ملاحظة: {note}",
    "receipt.cashier.header": "{client_name}",
    "receipt.cashier.meta": "{table_code} : {cashier}",
    "receipt.cashier.method": "دفع: {method}",
    "receipt.cashier.subtotal": "المجموع: {amount}",
    "receipt.cashier.discount": "الخصم: {amount}",
    "receipt.cashier.service": "الخدمة: {amount}",
    "receipt.cashier.tax": "الضريبة: {amount}",
    "receipt.cashier.total": "الصافي: {amount}",
    "receipt.footer": "شكراً",

    # Settings – branding page ---------------------------------------------
    "settings.branding.tab": "الهوية والنصوص",
    "settings.branding.client_name": "اسم العميل",
    "settings.branding.logo": "شعار العميل",
    "settings.branding.primary_color": "اللون الرئيسي",
    "settings.branding.browse": "اختيار…",
    "settings.branding.search_placeholder": "بحث عن نص…",
    "settings.branding.reset_selected": "إرجاع المختار",
    "settings.branding.reset_all": "إرجاع الكل للوضع الافتراضي",
    "settings.branding.add_row": "إضافة سطر",
    "settings.branding.import": "استيراد JSON",
    "settings.branding.export": "تصدير JSON",
    "settings.branding.table_key": "المفتاح",
    "settings.branding.table_value": "النص",
    "settings.branding.import_success": "تم استيراد النصوص بنجاح (لم يتم الحفظ بعد).",
    "settings.branding.import_error": "تعذر قراءة ملف JSON المحدد.",
    "settings.branding.duplicate_key": "يوجد مفتاح مكرر: {key}",
}


_CACHE: Dict[str, str] | None = None
_OVERRIDES_CACHE: Dict[str, str] | None = None


def _load_overrides() -> Dict[str, str]:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS ui_texts(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cur.execute("SELECT key, value FROM ui_texts")
        rows = cur.fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}
    except sqlite3.OperationalError:
        # The table may not exist yet if init_db() hasn't been executed.
        return {}
    finally:
        conn.close()


def _ensure_cache() -> None:
    global _CACHE, _OVERRIDES_CACHE
    if _CACHE is not None and _OVERRIDES_CACHE is not None:
        return
    overrides = _load_overrides()
    combined = dict(DEFAULT_TEXTS)
    combined.update(overrides)
    _CACHE = combined
    _OVERRIDES_CACHE = overrides


def invalidate() -> None:
    """Clear caches and notify listeners that texts have changed."""

    global _CACHE, _OVERRIDES_CACHE
    _CACHE = None
    _OVERRIDES_CACHE = None
    bus.emit("ui_texts_changed")


def get(key: str, default: str | None = None, **vars) -> str:
    """Return text for *key*, formatting with any provided variables."""

    _ensure_cache()
    assert _CACHE is not None
    value = _CACHE.get(key, DEFAULT_TEXTS.get(key, default))
    if value is None:
        return ""
    try:
        return value.format(**vars)
    except Exception:
        return value


def get_overrides() -> Dict[str, str]:
    _ensure_cache()
    assert _OVERRIDES_CACHE is not None
    return dict(_OVERRIDES_CACHE)


def get_all() -> Dict[str, str]:
    _ensure_cache()
    assert _CACHE is not None
    return dict(_CACHE)


def calculate_overrides(all_values: Mapping[str, str]) -> Dict[str, str]:
    """Return the subset of *all_values* that differ from defaults."""

    overrides: Dict[str, str] = {}
    for key, value in all_values.items():
        value = value if value is not None else ""
        default = DEFAULT_TEXTS.get(key)
        if default is None or value != default:
            overrides[key] = value
    return overrides


def replace_overrides(new_overrides: Mapping[str, str]) -> None:
    """Replace all overrides with *new_overrides* in a transaction."""

    with db_transaction() as conn:
        conn.execute("DELETE FROM ui_texts")
        for key, value in new_overrides.items():
            conn.execute(
                "INSERT INTO ui_texts(key, value) VALUES(?, ?)",
                (str(key), str(value)),
            )
    invalidate()


def reset_keys(keys: Iterable[str]) -> None:
    keys = list(keys)
    if not keys:
        return
    with db_transaction() as conn:
        conn.executemany("DELETE FROM ui_texts WHERE key=?", ((key,) for key in keys))
    invalidate()


def export_json() -> str:
    overrides = get_overrides()
    return json.dumps(overrides, ensure_ascii=False, indent=2, sort_keys=True)


def import_json(raw: str) -> Dict[str, str]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON must describe an object of key/value pairs")
    clean: Dict[str, str] = {}
    for key, value in data.items():
        clean[str(key)] = "" if value is None else str(value)
    return clean

