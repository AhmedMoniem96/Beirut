"""
Dynamic UI texts registry.

- Use texts.get(key, default=None, lang=None, **tpl_vars) to retrieve text values.
- Supports safe formatting with tpl_vars (missing placeholders preserved).
- Tries to load texts from DB table 'ui_texts' if available (expects columns key, value).
- Falls back to DEFAULT_TEXTS when DB or table not available.
- Provides simple set/invalidate helpers for admin UI to update texts.
"""

from __future__ import annotations
import json
import sqlite3
from collections import ChainMap
from datetime import datetime
from typing import Optional, Dict, Any

# Minimal defaults (add keys your app expects here)
DEFAULT_TEXTS: Dict[str, str] = {
    # License block
    "license.block.cancel": "إلغاء",
    "license.block.error": "خطأ في الترخيص",
    "license.block.input": "أدخل مفتاح الترخيص",
    "license.block.message": "الرجاء إدخال مفتاح ترخيص صالح",
    "license.block.submit": "تفعيل",
    "license.block.title": "تفعيل الترخيص",

    # Login window
    "login.window_title": "{client_name} - تسجيل الدخول",
    "login.brand_title": "Beirut POS",
    "login.create_success": "تم إنشاء المستخدم بنجاح",
    "login.create_user": "إنشاء مستخدم جديد",
    "login.error": "خطأ في تسجيل الدخول",
    "login.forgot": "نسيت كلمة المرور؟",
    "login.form_hint": "أدخل بيانات الدخول",
    "login.form_title": "تسجيل الدخول",
    "login.hero": "مرحباً بك",
    "login.hero_hint": "نظام إدارة المطاعم",
    "login.password_placeholder": "كلمة المرور",
    "login.submit": "دخول",
    "login.username_placeholder": "اسم المستخدم",

    # Main window titles
    "app.window_title": "{client_name} - {username} ({role})",
    "app.window_title_fallback": "{client_name}",

    # Main window toolbar
    "main.toolbar.back": "رجوع",
    "main.toolbar.switch": "تبديل المستخدم",
    "main.toolbar.manage_products": "إدارة المنتجات",
    "main.toolbar.users": "المستخدمين",
    "main.toolbar.reports": "التقارير",
    "main.toolbar.tables": "الطاولات",
    "main.toolbar.purchases": "المشتريات",
    "main.toolbar.settings": "الإعدادات",
    "main.toolbar.reservations": "الحجوزات",

    # Main window sections
    "main.banner.close": "إغلاق",
    "main.tables.title": "الطاولات",
    "main.order.header": "الطلب",
    "main.order.print_bar": "طباعة البار",
    "main.order.print_cashier": "طباعة الكاشير",

    # Orders
    "orders.cancel_button": "إلغاء",
    "orders.pay_button": "دفع",
    "orders.subtotal_label": "المجموع الفرعي",
    "orders.total_label": "الإجمالي",
    "orders.total_before_discount": "المجموع قبل الخصم",
    "orders.total_after_discount": "المجموع بعد الخصم",
    "orders.edit_locked": "انتهت مدة التعديل",

    # Orders - Discount
    "orders.discount_button": "خصم",
    "orders.discount_dialog_title": "تطبيق خصم",
    "orders.discount_label_percent": "% نسبة",
    "orders.discount_label_amount": "جنيه مبلغ",
    "orders.discount_percent_suffix": "%",
    "orders.discount_amount_suffix": "ج.م",
    "orders.discount_value_label": "قيمة الخصم",
    "orders.discount_reason_label": "سبب الخصم",
    "orders.discount_reason_placeholder": "اختياري: سبب الخصم",
    "orders.discount_username_label": "اسم المستخدم",
    "orders.discount_username_placeholder": "أدخل اسم المستخدم",
    "orders.discount_password_label": "كلمة المرور",
    "orders.discount_summary_label": "الخصم",
    "orders.discount_apply_button": "تطبيق",
    "orders.discount_invalid_credentials": "بيانات دخول غير صحيحة",
    "orders.discount_invalid_title": "خطأ في المصادقة",

    # Payment methods
    "orders.payment_method_cash": "نقدي",
    "orders.payment_method_card": "بطاقة",

    # Receipts - Bar
    "receipt.bar.header": "طلب البار",
    "receipt.bar.table": "الطاولة: {table_code}",
    "receipt.bar.issued_at": "التاريخ: {timestamp}",

    # Receipts - Cashier
    "receipt.cashier.header": "{client_name}",
    "receipt.cashier.meta": "الطاولة: {table_code} | الكاشير: {cashier}",
    "receipt.cashier.subtotal": "المجموع الفرعي: {amount}",
    "receipt.cashier.discount": "الخصم: {amount}",
    "receipt.cashier.service": "الخدمة: {amount}",
    "receipt.cashier.tax": "الضريبة: {amount}",
    "receipt.cashier.total": "الصافي: {amount}",
    "receipt.cashier.method": "طريقة الدفع: {method}",
    "receipt.footer": "شكراً لزيارتكم",
    "receipt.note": "ملاحظة: {note}",

    # Tables
    "tables.history.button": "الطلبات السابقة للطاولة",
    "tables.history.export_filename": "table_history_{table}_{date}.csv",

    # Reports
    "reports.order_changes": "سجل التغييرات",
    "reports.order_changes.title": "سجل التغييرات على الطلبات",

    # Settings - Branding
    "settings.branding.tab": "العلامة التجارية",
    "settings.branding.client_name": "اسم العميل",
    "settings.branding.logo": "الشعار",
    "settings.branding.browse": "استعراض",
    "settings.branding.primary_color": "اللون الأساسي",
    "settings.branding.table_key": "المفتاح",
    "settings.branding.table_value": "القيمة",
    "settings.branding.add_row": "إضافة صف",
    "settings.branding.reset_selected": "إعادة تعيين المحدد",
    "settings.branding.reset_all": "إعادة تعيين الكل",
    "settings.branding.search_placeholder": "بحث...",
    "settings.branding.export": "تصدير",
    "settings.branding.import": "استيراد",
    "settings.branding.import_success": "تم الاستيراد بنجاح",
    "settings.branding.import_error": "خطأ في الاستيراد",
    "settings.branding.duplicate_key": "مفتاح مكرر",
}

class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


class _TextsProxy:
    def __init__(self):
        # in-memory cache, key -> value
        self._cache: Dict[str, str] = {}
        self._last_loaded: Optional[str] = None

        # Start with defaults in cache
        self._cache.update(DEFAULT_TEXTS)

        # Try to warm cache from DB at init (best-effort; fails silently)
        try:
            self.reload_from_db()
        except Exception:
            # if DB or table not present, defaults are already in cache
            pass

    # --- DB access helpers (defensive) ---
    def _get_db_conn(self) -> Optional[sqlite3.Connection]:
        """
        Try to obtain a DB connection from core.db.get_conn() if present.
        Falls back to None if unavailable.
        """
        try:
            # prefer a project helper if available
            from beirut_pos.core.db import get_conn  # type: ignore
            return get_conn()
        except Exception:
            # try common alternative name 'get_connection' or direct path
            try:
                from beirut_pos.core.db import get_connection  # type: ignore
                return get_connection()
            except Exception:
                return None

    def reload_from_db(self) -> None:
        """
        Reload cache from DB table 'ui_texts' (columns: key, value).
        If table not present, do nothing (caller falls back to DEFAULT_TEXTS).
        """
        conn = self._get_db_conn()
        if conn is None:
            # Nothing to load
            return

        try:
            cur = conn.cursor()
            # check if ui_texts table exists
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ui_texts' LIMIT 1"
            )
            if not cur.fetchone():
                return

            cur.execute("SELECT key, value FROM ui_texts")
            rows = cur.fetchall()
            for k, v in rows:
                # store value as string
                if v is None:
                    continue
                self._cache[k] = str(v)
            # update last loaded timestamp (human-readable)
            self._last_loaded = datetime.utcnow().isoformat()
        except Exception:
            # do not propagate DB errors here (keep defaults)
            return

    def _lookup_raw(self, key: str, lang: Optional[str] = None) -> Optional[str]:
        """
        Lookup raw value without templating. Order:
          1) in-memory cache
          2) DB 'ui_texts' table (if available)
          3) DEFAULT_TEXTS fallback
        """
        # 1) cache
        if key in self._cache:
            return self._cache[key]

        # 2) DB lookup
        conn = self._get_db_conn()
        if conn:
            try:
                cur = conn.cursor()
                # try exact key first
                cur.execute("SELECT value FROM ui_texts WHERE key = ? LIMIT 1", (key,))
                row = cur.fetchone()
                if row and row[0] is not None:
                    self._cache[key] = str(row[0])
                    return self._cache[key]
                # optionally attempt language-specific key like "key:ar" if lang provided
                if lang:
                    lang_key = f"{key}:{lang}"
                    cur.execute("SELECT value FROM ui_texts WHERE key = ? LIMIT 1", (lang_key,))
                    row = cur.fetchone()
                    if row and row[0] is not None:
                        self._cache[key] = str(row[0])
                        return self._cache[key]
            except Exception:
                # DB read failure -> ignore and continue to defaults
                pass

        # 3) default fallbacks
        if key in DEFAULT_TEXTS:
            return DEFAULT_TEXTS[key]

        return None

    # --- Public API ---
    def get(self, key: str, default: Optional[str] = None, lang: Optional[str] = None, **tpl_vars) -> str:
        """
        Retrieve a text by key and safely format with tpl_vars.

        Example:
            texts.get("login.window_title", client_name="Beirut POS")

        Args:
            key: The text key to lookup
            default: Default value if key not found (optional)
            lang: Language code for localized lookup (optional)
            **tpl_vars: Template variables for string formatting

        Returns:
            Formatted text string, or empty string if not found and no default
        """
        # Get raw value
        value = None
        try:
            value = self._lookup_raw(key, lang=lang)
        except Exception:
            value = None

        if value is None:
            value = default

        if value is None:
            # Return empty string (never None to avoid UI errors)
            return ""

        # Optionally supply client_name by default (deferred import to avoid circular import)
        if "client_name" not in tpl_vars:
            try:
                from beirut_pos.services.settings import get_client_name  # type: ignore
                client = get_client_name()
                if client:
                    tpl_vars["client_name"] = client
            except Exception:
                # ignore any failure here
                pass

        # If no template vars, return raw value
        if not tpl_vars:
            return value

        # Format safely
        try:
            safe_map = ChainMap(tpl_vars, _SafeDict())
            return str(value).format_map(safe_map)
        except Exception:
            # formatting failed; return raw value
            return value

    def set(self, key: str, value: str) -> None:
        """
        Set a text value in memory and try to persist to DB if possible.
        Admin UI should call this to update texts.
        """
        self._cache[key] = value
        # try to persist
        try:
            conn = self._get_db_conn()
            if conn:
                cur = conn.cursor()
                # ensure table exists
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ui_texts' LIMIT 1")
                if not cur.fetchone():
                    # create basic ui_texts table
                    cur.execute(
                        "CREATE TABLE IF NOT EXISTS ui_texts (key TEXT PRIMARY KEY, value TEXT)"
                    )
                # upsert pattern
                cur.execute(
                    "INSERT INTO ui_texts (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
                conn.commit()
        except Exception:
            # swallow DB errors to keep UI responsive; cache still contains the new value
            pass

    def invalidate_cache(self) -> None:
        """Clear in-memory cache to force reload from DB on next access."""
        self._cache.clear()
        self._cache.update(DEFAULT_TEXTS)
        try:
            self.reload_from_db()
        except Exception:
            # if reload fails, defaults are already in cache
            pass

    def keys(self) -> Dict[str, str]:
        """Return a snapshot of keys available (cache + defaults)."""
        snapshot = dict(DEFAULT_TEXTS)
        snapshot.update(self._cache)
        return snapshot

    def export_all(self) -> Dict[str, str]:
        """Return all texts for UI export (cache merged with defaults)."""
        return self.keys()

    def get_all(self) -> Dict[str, str]:
        """Alias for export_all() - return all texts for settings UI."""
        return self.export_all()


# Module-level instance - create once
texts = _TextsProxy()

# Expose at module level for easier imports
__all__ = ['texts', 'DEFAULT_TEXTS']