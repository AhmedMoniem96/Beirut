from beirut_pos.services.printer import MockPrinter, _emit_lines_to_printer


def test_emit_lines_to_printer_appends_newlines():
    printer = MockPrinter("raw-test")
    _emit_lines_to_printer(printer, ["foo", "bar"])
    assert "foo\n" in printer.buffer
    assert "bar\n" in printer.buffer
