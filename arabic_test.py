from beirut_pos.services import arabic_codec


def test_sanitize_line_replaces_emojis():
    raw = "Hello ✅ Cafe"
    sanitized = arabic_codec.sanitize_line(raw)
    assert "✅" not in sanitized
    assert "[OK]" in sanitized


def test_encode_for_printer_falls_back_to_utf8():
    data = arabic_codec.encode_for_printer("مرحبا", encoding="cp9999")
    assert isinstance(data, bytes)
    assert data != b""
