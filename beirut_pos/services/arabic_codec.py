from __future__ import annotations

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
    _AR_OK = True
except Exception:
    _AR_OK = False

# Map emojis / unsupported glyphs to ASCII
REPLACEMENTS = {
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


def sanitize_line(s: str) -> str:
    """Replace unsupported glyphs/emojis with ASCII-friendly alternatives."""
    for src, dst in REPLACEMENTS.items():
        s = s.replace(src, dst)
    allowed_symbols = '-_=+/\\()[]{}.,:;*<>!?"\' '
    return "".join(
        ch
        for ch in s
        if ord(ch) < 0x2500
        or (0x2500 <= ord(ch) <= 0x257F)
        or ch in allowed_symbols
    )

def shape_bidi_arabic(s: str) -> str:
    if not s:
        return s
    if not _AR_OK:
        return s
    try:
        reshaped = arabic_reshaper.reshape(s)
        return get_display(reshaped)
    except Exception:
        return s


def encode_for_printer(s: str, encoding: str = "cp1256") -> bytes:
    return s.encode(encoding, errors="replace")
