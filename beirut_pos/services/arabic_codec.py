from __future__ import annotations

import os
from typing import Final

# Optional Arabic shaping libs
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _AR_OK: Final[bool] = True
except Exception:
    _AR_OK = False

# Map emojis / unsupported glyphs to ASCII-safe tokens (printer-friendly)
REPLACEMENTS: Final[dict[str, str]] = {
    "📅": "[DATE]",
    "🪑": "[TABLE]",
    "👤": "[CASHIER]",
    "💰": "[TOTAL]",
    "★": "*",
    "⭐": "*",
    "↳": "->",
    "•": "*",
    "🕐": "[TIME]",
    "✅": "[OK]",
    "❌": "[X]",
    "🔄": "[~]",
    "🔍": "[?]",
    "ℹ️": "[i]",
}

_ALLOWED_PUNCT: Final[str] = '-_=+/\\()[]{}.,:;*<>!?"\' '


def sanitize_line(s: str) -> str:
    """
    Replace emojis & unprintable glyphs with ASCII-friendly alternatives and
    keep only characters likely to render on ESC/POS devices or in our bitmap path.
    """
    if not s:
        return s
    for src, dst in REPLACEMENTS.items():
        s = s.replace(src, dst)

    # Keep:
    # - BMP chars before box-drawing range
    # - Box-drawing block U+2500..U+257F (we use lines/boxes)
    # - A small whitelist of punctuation/symbols
    return "".join(
        ch
        for ch in s
        if (ord(ch) < 0x2500) or (0x2500 <= ord(ch) <= 0x257F) or (ch in _ALLOWED_PUNCT)
    )


def contains_arabic(s: str) -> bool:
    """Quick heuristic: does the string include Arabic code points?"""
    if not s:
        return False
    for ch in s:
        cp = ord(ch)
        # Arabic + Arabic Supplement + Arabic Presentation Forms A/B (coarse but effective)
        if (0x0600 <= cp <= 0x06FF) or (0x0750 <= cp <= 0x077F) or (0x08A0 <= cp <= 0x08FF) \
           or (0xFB50 <= cp <= 0xFDFF) or (0xFE70 <= cp <= 0xFEFF):
            return True
    return False


def smart_shape(s: str) -> str:
    """
    Single, configurable shaping step.

    Controlled by env BEIRUT_POS_AR_MODE:
      - 'reshape' : reshape only (no bidi reordering) - DEFAULT NOW
      - 'bidi'    : reshape + bidi reordering
      - 'none'    : do not shape (returns input)

    Notes:
    - If shaping libs are missing, returns the input unchanged.
    - Call this exactly once at the emission layer (e.g., RawUsbEscpos.text_or_bitmap).
    - DEFAULT CHANGED TO 'reshape' because BiDi causes reversed text on most printers
    """
    if not s or not _AR_OK:
        return s

    mode = os.getenv("BEIRUT_POS_AR_MODE", "reshape").lower()  # CHANGED DEFAULT
    try:
        if mode == "none":
            return s

        reshaped = arabic_reshaper.reshape(s)

        if mode == "reshape":
            return reshaped

        # bidi mode: reshape + display order
        return get_display(reshaped)
    except Exception:
        return s


# Back-compat wrapper: respect current env mode but defaults to bidi behavior.
def shape_bidi_arabic(s: str) -> str:
    """
    Legacy API. Prefer smart_shape().
    Equivalent to smart_shape(s) with default 'bidi' behavior.
    """
    return smart_shape(s)


def encode_for_printer(s: str, encoding: str = "cp1256") -> bytes:
    """
    Encode text for ESC/POS text mode. If you are using the bitmap path,
    you likely do not need this; use rasterized bytes instead.
    """
    try:
        return s.encode(encoding, errors="replace")
    except LookupError:
        # Extreme fallback; most devices will not accept UTF-8 directly.
        return s.encode("utf-8", errors="replace")