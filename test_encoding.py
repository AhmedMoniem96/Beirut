from beirut_pos.services.printer import _format_currency_simple


def test_format_currency_simple_handles_strings():
    assert _format_currency_simple("12.500") == "12.5"
    assert _format_currency_simple("7") == "7"
