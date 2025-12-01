from beirut_pos.services.printer import _format_qty


def test_format_qty_trims_trailing_zero():
    assert _format_qty(3.0) == "3"
    assert _format_qty(1.25) == "1.25"
