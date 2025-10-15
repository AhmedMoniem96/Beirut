"""Simple offline voucher activation for Beirut POS."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .db import setting_get, setting_set
from .paths import LICENSE_CACHE_FILE

_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_PREFIX = "BEIRUT"
_PAYLOAD_LEN = 12  # three blocks of four characters

_ACTIVATED_KEY = "voucher_activated"
_ACTIVATED_AT_KEY = "voucher_activated_at"
_HASH_KEY = "voucher_hash"


@dataclass(slots=True)
class VoucherStatus:
    activated: bool
    message: str
    activated_at: str | None = None


def _normalize(code: str) -> str:
    if not code:
        return ""
    cleaned = "".join(ch for ch in code.upper() if ch.isalnum())
    if not cleaned.startswith(_PREFIX):
        return cleaned
    return cleaned


def _payload_and_check(normalized: str) -> tuple[str, str]:
    if not normalized.startswith(_PREFIX):
        return "", ""
    body = normalized[len(_PREFIX) :]
    if len(body) != _PAYLOAD_LEN + 1:
        return "", ""
    payload, check_char = body[:-1], body[-1]
    return payload, check_char


def _luhn_mod_n(payload: str) -> str:
    factor = 2
    total = 0
    n = len(_ALPHABET)
    for char in reversed(payload):
        try:
            code_point = _ALPHABET.index(char)
        except ValueError:
            return ""
        addend = factor * code_point
        addend = (addend // n) + (addend % n)
        total += addend
        factor = 1 if factor == 2 else 2
    remainder = total % n
    check_code = (n - remainder) % n
    return _ALPHABET[check_code]


def _format(payload: str, check: str) -> str:
    groups = [payload[i : i + 4] for i in range(0, _PAYLOAD_LEN, 4)]
    return "-".join([_PREFIX, *groups, check])


def is_valid(code: str) -> bool:
    normalized = _normalize(code)
    if len(normalized) != len(_PREFIX) + _PAYLOAD_LEN + 1:
        return False
    payload, check_char = _payload_and_check(normalized)
    if not payload or not check_char:
        return False
    expected = _luhn_mod_n(payload)
    return expected == check_char


def normalize_for_storage(code: str) -> str:
    """Return the canonical uppercase string without hyphens."""

    normalized = _normalize(code)
    if len(normalized) != len(_PREFIX) + _PAYLOAD_LEN + 1:
        return ""
    return normalized


def format_voucher(code: str) -> str:
    normalized = normalize_for_storage(code)
    if not normalized:
        return code.strip().upper() if code else ""
    payload, check_char = _payload_and_check(normalized)
    return _format(payload, check_char)


def _hash_voucher(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _clear_legacy_license_cache() -> None:
    try:
        Path(LICENSE_CACHE_FILE).unlink(missing_ok=True)  # type: ignore[arg-type]
    except TypeError:
        cache_path = Path(LICENSE_CACHE_FILE)
        if cache_path.exists():
            try:
                cache_path.unlink()
            except OSError:
                pass
    except OSError:
        pass

    for key in ("license_key", "license_holder", "license_validated_at"):
        if setting_get(key, ""):
            setting_set(key, "")


def ensure_migrated() -> None:
    """Ensure legacy license values are cleared once after upgrade."""

    migrated = setting_get("voucher_migrated", "0") == "1"
    if migrated:
        return
    _clear_legacy_license_cache()
    setting_set("voucher_migrated", "1")


def activation_status() -> VoucherStatus:
    ensure_migrated()
    active = setting_get(_ACTIVATED_KEY, "0") == "1"
    if not active:
        return VoucherStatus(False, "❌ لم يتم تفعيل النسخة بعد.")
    activated_at = setting_get(_ACTIVATED_AT_KEY, "") or None
    return VoucherStatus(True, "✅ البرنامج مفعل بقسيمة صالحة.", activated_at)


def is_activated() -> bool:
    return activation_status().activated


def activate(code: str) -> VoucherStatus:
    ensure_migrated()
    normalized = normalize_for_storage(code)
    if not is_valid(code) or not normalized:
        return VoucherStatus(False, "❌ رمز القسيمة غير صالح. تأكد من كتابته بالشكل الصحيح.")

    payload_hash = _hash_voucher(normalized)
    setting_set(_HASH_KEY, payload_hash)
    setting_set(_ACTIVATED_KEY, "1")
    activated_at = datetime.now(timezone.utc).isoformat()
    setting_set(_ACTIVATED_AT_KEY, activated_at)
    return VoucherStatus(True, "✅ تم تفعيل البرنامج بنجاح.", activated_at)


def deactivate() -> VoucherStatus:
    setting_set(_HASH_KEY, "")
    setting_set(_ACTIVATED_KEY, "0")
    setting_set(_ACTIVATED_AT_KEY, "")
    return VoucherStatus(False, "تم تعطيل التفعيل الحالي.")


def generate_payload() -> str:
    rng = random.SystemRandom()
    return "".join(rng.choice(_ALPHABET) for _ in range(_PAYLOAD_LEN))


def generate_voucher() -> str:
    payload = generate_payload()
    check_char = _luhn_mod_n(payload)
    return _format(payload, check_char)


def generate_many(count: int) -> list[str]:
    seen: set[str] = set()
    vouchers: list[str] = []
    while len(vouchers) < max(count, 0):
        code = generate_voucher()
        if code in seen:
            continue
        seen.add(code)
        vouchers.append(code)
    return vouchers


def validate_batch(codes: Iterable[str]) -> bool:
    return all(is_valid(code) for code in codes)
