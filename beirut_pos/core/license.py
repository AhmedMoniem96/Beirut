"""Local license verification utilities for Beirut POS."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import platform
import json
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .db import setting_get, setting_set
from .paths import LICENSE_CACHE_FILE, ensure_storage_dirs

_PREFIX = "BRT1"
_SECRET = "BeirutPOS-license-seed-2024"


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _machine_fingerprint_components() -> str:
    node = platform.node() or ""
    system = platform.system() or ""
    machine = platform.machine() or ""
    version = platform.version() or ""
    mac = f"{uuid.getnode():012x}"
    parts = "|".join(part.lower() for part in (node, system, machine, version, mac))
    return parts


def machine_fingerprint() -> str:
    """Return a stable fingerprint for the current host."""

    raw = _machine_fingerprint_components()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class LicenseStatus:
    valid: bool
    message: str
    holder: str = ""
    fingerprint: str = ""
    issued_at: str | None = None
    expires_at: str | None = None


def _parse_license_blob(license_blob: str) -> Dict[str, Any]:
    if not license_blob:
        raise ValueError("empty license")

    cleaned = "".join(license_blob.strip().split())
    if "." not in cleaned or "-" not in cleaned:
        raise ValueError("format")

    prefix_payload, signature_part = cleaned.split(".", 1)
    prefix, payload_part = prefix_payload.split("-", 1)
    if prefix != _PREFIX:
        raise ValueError("prefix")

    payload_bytes = _b64decode(payload_part)
    signature_bytes = _b64decode(signature_part)
    expected = hmac.new(_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature_bytes, expected):
        raise ValueError("signature")

    data = json.loads(payload_bytes.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("payload")
    return data


def _build_status(valid: bool, message: str, data: Dict[str, Any] | None = None) -> LicenseStatus:
    holder = ""
    issued = None
    expires = None
    fingerprint = machine_fingerprint()
    if data:
        holder = str(data.get("holder", ""))
        issued = data.get("issued")
        expires = data.get("expires")
        fp = data.get("fingerprint", "")
        if isinstance(fp, str) and fp:
            fingerprint = fp

    return LicenseStatus(
        valid=valid,
        message=message,
        holder=holder,
        fingerprint=fingerprint,
        issued_at=issued,
        expires_at=expires,
    )


def verify_license(license_blob: str) -> LicenseStatus:
    try:
        data = _parse_license_blob(license_blob)
    except ValueError:
        return _build_status(False, "مفتاح الترخيص غير صالح. تأكد من نسخه بالكامل.")

    current_fp = machine_fingerprint()
    payload_fp = str(data.get("fingerprint", ""))
    if payload_fp != current_fp:
        return _build_status(
            False,
            "مفتاح الترخيص مربوط بجهاز مختلف. اطلب مفتاحًا جديدًا لهذا الجهاز.",
            data,
        )

    expires_raw = data.get("expires")
    if expires_raw:
        try:
            expires_dt = datetime.fromisoformat(expires_raw)
        except ValueError:
            return _build_status(False, "تاريخ انتهاء الترخيص غير مفهوم.", data)
        now = datetime.now(timezone.utc)
        if expires_dt.tzinfo is None:
            expires_dt = expires_dt.replace(tzinfo=timezone.utc)
        if expires_dt < now:
            return _build_status(
                False,
                f"انتهت صلاحية الترخيص بتاريخ {expires_dt.date().isoformat()}.",
                data,
            )

    return _build_status(True, "تم تفعيل الترخيص بنجاح.", data)


def issue_license(
    holder: str,
    fingerprint: str | None = None,
    *,
    expires: datetime | str | None = None,
    issued_at: datetime | None = None,
) -> str:
    """Generate a signed license string (for vendor tooling)."""

    payload_fp = fingerprint or machine_fingerprint()
    issued_dt = issued_at or datetime.now(timezone.utc)
    if issued_dt.tzinfo is None:
        issued_dt = issued_dt.replace(tzinfo=timezone.utc)

    expires_value: str | None
    if isinstance(expires, datetime):
        exp = expires
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        expires_value = exp.astimezone(timezone.utc).isoformat()
    else:
        expires_value = expires

    payload: Dict[str, Any] = {
        "holder": holder,
        "fingerprint": payload_fp,
        "issued": issued_dt.astimezone(timezone.utc).isoformat(),
    }
    if expires_value:
        payload["expires"] = expires_value

    payload_bytes = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    signature = hmac.new(_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return f"{_PREFIX}-{_b64encode(payload_bytes)}.{_b64encode(signature)}"


def activate_license(license_blob: str) -> LicenseStatus:
    status = verify_license(license_blob)
    if status.valid:
        setting_set("license_key", license_blob.strip())
        setting_set("license_holder", status.holder)
        setting_set("license_validated_at", datetime.utcnow().isoformat())
        _write_license_cache(license_blob)
    return status


def license_status() -> LicenseStatus:
    stored_key = setting_get("license_key", "").strip()
    if not stored_key:
        stored_key = _read_license_cache().strip()
    if not stored_key:
        return LicenseStatus(
            valid=False,
            message="لم يتم تفعيل البرنامج بعد. أدخل مفتاح الترخيص للمتابعة.",
            holder=setting_get("license_holder", ""),
            fingerprint=machine_fingerprint(),
            issued_at=None,
            expires_at=None,
        )

    status = verify_license(stored_key)
    if status.valid:
        # Prefer the stored holder if operator renamed the outlet in settings.
        holder = setting_get("license_holder", status.holder)
        status.holder = holder or status.holder
    return status


__all__ = [
    "LicenseStatus",
    "issue_license",
    "activate_license",
    "license_status",
    "machine_fingerprint",
    "verify_license",
]
def _write_license_cache(license_blob: str) -> None:
    ensure_storage_dirs()
    LICENSE_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"license_key": license_blob.strip()}
    tmp = LICENSE_CACHE_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=True)
    os.replace(tmp, LICENSE_CACHE_FILE)


def _read_license_cache() -> str:
    if not LICENSE_CACHE_FILE.exists():
        return ""
    try:
        with LICENSE_CACHE_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            cached = data.get("license_key", "")
            return str(cached or "")
    except (OSError, json.JSONDecodeError):
        return ""
    return ""
