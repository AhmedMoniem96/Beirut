"""Lightweight text lookup helper for UI and service messages."""
from __future__ import annotations

from typing import Dict

_TRANSLATIONS: Dict[str, str] = {
    "orders.edit_locked": "تم إيقاف التعديل بعد انتهاء نافذة الخمس دقائق.",
    "orders.discount_label_percent": "الخصم (٪)",
    "orders.discount_label_amount": "الخصم",  # default label for fixed discounts
    "orders.discount_type_percent": "خصم بنسبة مئوية",
    "orders.discount_type_amount": "خصم بقيمة ثابتة",
    "orders.discount_value_label": "قيمة الخصم",
    "orders.discount_reason_label": "سبب الخصم",
    "orders.discount_reason_placeholder": "مثال: موافقة المدير على خصم خاص",
    "orders.discount_username_label": "اسم مستخدم المدير",
    "orders.discount_username_placeholder": "admin",
    "orders.discount_password_label": "كلمة مرور المدير",
    "orders.discount_dialog_title": "تطبيق خصم (موافقة مدير)",
    "orders.discount_apply_button": "تطبيق",
    "orders.cancel_button": "إلغاء",
    "orders.discount_invalid_title": "مرفوض",
    "orders.discount_invalid_credentials": "بيانات المدير غير صحيحة.",
    "orders.discount_amount_suffix": "ج.م",
    "orders.discount_percent_suffix": "٪",
    "orders.total_before_discount": "المجموع قبل الخصم",
    "orders.discount_summary_label": "الخصم",
    "orders.total_after_discount": "المجموع النهائي",
    "orders.payment_method_cash": "نقدي",
    "orders.payment_method_card": "فيزا",
    "orders.discount_button": "تطبيق خصم (مدير)",
    "orders.pay_button": "تحصيل / دفع",
    "orders.subtotal_label": "المجموع",
    "orders.total_label": "الإجمالي",
    "main.toolbar.inventory": "المخزون",
}


def get(key: str, default: str | None = None) -> str:
    """Return translated text for ``key`` or the key/default if missing."""

    if key in _TRANSLATIONS:
        return _TRANSLATIONS[key]
    if default is not None:
        return default
    return key


class _TextsProxy:
    """Expose dict-like access with ``get`` to mimic mapping semantics."""

    def get(self, key: str, default: str | None = None) -> str:  # pragma: no cover - trivial
        return get(key, default)


texts = _TextsProxy()

