from beirut_pos.services import printer as printer_module


def test_print_bar_ticket_returns_true(monkeypatch):
    mock = printer_module.MockPrinter("bar-test")
    monkeypatch.setattr(printer_module, "_find_thermal_printer", lambda: mock)
    service = printer_module.PrinterService()

    items = [
        {"name": "Espresso", "qty": 1, "total_cents": 700, "unit_price": 700},
        {"name": "Cappuccino", "qty": 2, "total_cents": 1800, "unit_price": 900},
    ]

    assert service.print_bar_ticket("B2", items)
