"""Simple offline voucher activation for Beirut POS."""

from __future__ import annotations

import hashlib
import random
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
_SUFFIX_KEY = "voucher_suffix"
_MIGRATED_KEY = "voucher_migrated"


def _normalize(code: str) -> str:
    if not code:
        return ""
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _payload_and_check(normalized: str) -> tuple[str, str]:
    if not normalized.startswith(_PREFIX):
        return "", ""
    body = normalized[len(_PREFIX) :]
    if len(body) != _PAYLOAD_LEN + 1:
        return "", ""
    return body[:-1], body[-1]


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


def normalize_for_storage(code: str) -> str:
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


def is_valid(code: str) -> bool:
    normalized = normalize_for_storage(code)
    if not normalized:
        return False
    payload, check_char = _payload_and_check(normalized)
    if not payload or not check_char:
        return False
    return _luhn_mod_n(payload) == check_char


def _hash_voucher(normalized: str) -> str:
    digest = hashlib.sha256(f"{normalized}:beirut".encode("utf-8")).hexdigest()
    return digest[:16]


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
    if setting_get(_MIGRATED_KEY, "0") == "1":
        return
    _clear_legacy_license_cache()
    setting_set(_MIGRATED_KEY, "1")


def _status_dict(activated: bool, activated_at: str | None, suffix: str | None) -> dict:
    return {
        "activated": activated,
        "activated_at": activated_at,
        "voucher_suffix": suffix,
    }


def status() -> dict:
    ensure_migrated()
    active = setting_get(_ACTIVATED_KEY, "0") == "1"
    if not active:
        return _status_dict(False, None, None)
    return _status_dict(
        True,
        setting_get(_ACTIVATED_AT_KEY, "") or None,
        setting_get(_SUFFIX_KEY, "") or None,
    )


def is_activated() -> bool:
    return status()["activated"]


def activate(voucher: str) -> tuple[bool, str]:
    ensure_migrated()
    normalized = normalize_for_storage(voucher)
    if not normalized or not is_valid(normalized):
        return False, "❌ رمز القسيمة غير صالح. تأكد من كتابته بالشكل الصحيح."

    hash_value = _hash_voucher(normalized)
    activated_at = datetime.now(timezone.utc).isoformat()
    suffix = normalized[-4:]

    setting_set(_HASH_KEY, hash_value)
    setting_set(_ACTIVATED_KEY, "1")
    setting_set(_ACTIVATED_AT_KEY, activated_at)
    setting_set(_SUFFIX_KEY, suffix)
    return True, "✅ تم تفعيل البرنامج بنجاح."


def deactivate() -> None:
    setting_set(_HASH_KEY, "")
    setting_set(_ACTIVATED_KEY, "0")
    setting_set(_ACTIVATED_AT_KEY, "")
    setting_set(_SUFFIX_KEY, "")


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
