from beirut_pos.services import printer as printer_module


def test_print_cashier_receipt_works_without_physical_printer(monkeypatch):
    mock = printer_module.MockPrinter("unit-test")
    monkeypatch.setattr(printer_module, "_find_thermal_printer", lambda: mock)
    service = printer_module.PrinterService()

    items = [
        {"name": "Latte", "qty": 2, "total_cents": 2000, "unit_price": 1000, "note": ""},
        {"name": "Tea", "qty": 1, "total_cents": 500, "unit_price": 500, "note": "سكر خفيف"},
    ]

    assert service.print_cashier_receipt(
        table_code="A1",
        items=items,
        subtotal=2500,
        discount=0,
        total=2500,
        method="نقدي",
        cashier="أحمد",
    )
