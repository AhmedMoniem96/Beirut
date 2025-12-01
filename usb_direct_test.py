from beirut_pos.services import printer as printer_module


def test_try_usb_printer_gracefully_handles_missing_backend(monkeypatch):
    monkeypatch.setattr(printer_module, "_ESCPOS_OK", False)
    monkeypatch.setattr(printer_module, "Usb", None, raising=False)
    assert printer_module._try_usb_printer() is None
