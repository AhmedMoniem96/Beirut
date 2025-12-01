from beirut_pos.services import printer as printer_module


def test_current_printer_accessor(monkeypatch):
    sentinel = printer_module.MockPrinter("sentinel")
    monkeypatch.setattr(printer_module, "_find_thermal_printer", lambda: sentinel)
    svc = printer_module.PrinterService()
    assert svc._current_printer() is sentinel
