"""Dynamic UI text registry with database-backed overrides and caching."""

from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace
from typing import Dict, Iterable, Mapping, Optional

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
    "login.form_hint": "أدخل بياناتك للالمتابعة",
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

    # Tables history --------------------------------------------------------
    "tables.history.button": "الطلبات السابقة للطاولة",
    "tables.history.title": "سجل الطلبات للطاولة {table_code}",
    "tables.history.from": "من تاريخ",
    "tables.history.to": "إلى تاريخ",
    "tables.history.search_label": "بحث",
    "tables.history.search_placeholder": "رقم الطلب، اسم الكاشير، أو ملاحظة",
    "tables.history.apply": "تطبيق المرشحات",
    "tables.history.export": "تصدير CSV",
    "tables.history.export_filename": "table_history_{table}_{date}.csv",
    "tables.history.headers.order_id": "رقم الطلب",
    "tables.history.headers.client_name": "اسم العميل",
    "tables.history.headers.opened_at": "وقت الفتح",
    "tables.history.headers.paid_at": "وقت الدفع",
    "tables.history.headers.total": "الإجمالي",
    "tables.history.headers.discount": "الخصم",
    "tables.history.headers.cashier": "الكاشير",
    "tables.history.headers.items_count": "عدد العناصر",
    "tables.history.no_results": "لا توجد طلبات ضمن المعايير المحددة.",
    "tables.history.pagination.prev": "السابق",
    "tables.history.pagination.next": "التالي",
    "tables.history.pagination.page": "الصفحة {page}",
    "tables.history.page_size": "عدد النتائج",
    "tables.history.export.success": "تم تصدير السجل بنجاح.",
    "tables.history.export.empty": "لا توجد بيانات لتصديرها.",
    "tables.history.export.error": "تعذر تصدير السجل: {error}",
    "tables.history.details.title": "تفاصيل الطلب #{order_id}",
    "tables.history.details.table": "الطاولة",
    "tables.history.details.client_name": "اسم العميل",
    "tables.history.details.opened_at": "وقت الفتح",
    "tables.history.details.paid_at": "وقت الدفع",
    "tables.history.details.cashier": "الكاشير",
    "tables.history.details.subtotal": "الإجمالي قبل الخصم",
    "tables.history.details.discount": "الخصم",
    "tables.history.details.total": "الإجمالي بعد الخصم",
    "tables.history.details.note": "ملاحظة",
    "tables.history.details.discount_reason": "سبب الخصم",
    "tables.history.details.items_header.product": "الصنف",
    "tables.history.details.items_header.qty": "الكمية",
    "tables.history.details.items_header.price": "السعر",
    "tables.history.details.items_header.total": "الإجمالي",
    "tables.history.details.items_header.note": "ملاحظة",
    "tables.history.details.payments": "المدفوعات",
    "tables.history.details.payments_entry": "{method} — {amount} في {time}",
    "tables.history.details.no_payments": "لا يوجد مدفوعات مسجلة.",
    "tables.history.details.missing": "تعذر تحميل تفاصيل الطلب المحدد.",

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


_CACHE: Optional[Dict[str, str]] = None
_OVERRIDES_CACHE: Optional[Dict[str, str]] = None


def _load_overrides() -> Dict[str, str]:
    """
    Load overrides from 'ui_texts' table if available.
    Returns empty dict if DB/table missing or not ready.
    """
    try:
        conn = get_conn()
    except Exception:
        return {}

    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS ui_texts(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cur.execute("SELECT key, value FROM ui_texts")
        rows = cur.fetchall()
        # rows may be tuples or sqlite Row; index safely
        result: Dict[str, str] = {}
        for row in rows:
            try:
                k = row[0]
                v = row[1]
            except Exception:
                # fallback to dict-like access
                k = row.get("key") if isinstance(row, Mapping) else None
                v = row.get("value") if isinstance(row, Mapping) else None
            if k is not None and v is not None:
                result[str(k)] = str(v)
        return result
    except sqlite3.OperationalError:
        # The table may not exist yet if init_db() hasn't been executed.
        return {}
    except Exception:
        return {}
    finally:
        try:
            conn.close()
        except Exception:
            pass


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
    try:
        bus.emit("ui_texts_changed")
    except Exception:
        # ignore bus errors (best-effort notification)
        pass


def get(key: str, default: Optional[str] = None, **tpl_vars) -> str:
    """Return text for *key*, formatting with any provided template variables."""
    _ensure_cache()
    assert _CACHE is not None
    value = _CACHE.get(key, DEFAULT_TEXTS.get(key, default))
    if value is None:
        return "" if default is None else str(default)
    if not tpl_vars:
        return str(value)
    try:
        return str(value).format(**tpl_vars)
    except Exception:
        # If formatting fails, return the raw value (avoid crashing UI)
        return str(value)


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


# Backwards-compatibility: expose a module-level `texts` object with the common API
# so older code that does `from beirut_pos.services.texts import texts` keeps working.
_texts_ns = SimpleNamespace(
    get=get,
    get_all=get_all,
    get_overrides=get_overrides,
    calculate_overrides=calculate_overrides,
    replace_overrides=replace_overrides,
    reset_keys=reset_keys,
    export_json=export_json,
    import_json=import_json,
    invalidate=invalidate,
)
texts = _texts_ns
