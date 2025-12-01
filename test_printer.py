from beirut_pos.services.printer import printer


def test_test_print_returns_boolean(monkeypatch):
    # Force the singleton to use an in-memory printer to avoid hardware access.
    monkeypatch.setattr(printer, "_escpos_printer", None, raising=False)
    assert printer.test_print() is True
