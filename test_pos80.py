from beirut_pos.services import printer as printer_module


def test_build_items_table_calculates_totals():
    headers, rows, subtotal, qty = printer_module._build_items_table(
        [
            {"name": "Coffee", "qty": 2, "total_cents": 1000, "unit_price": 500},
            {"name": "Tea", "qty": 1, "total_cents": 500, "unit_price": 500},
        ]
    )
    assert headers[0] == "الصنف"
    assert rows[0][1] == "2"
    assert subtotal == 1500
    assert qty == 3
