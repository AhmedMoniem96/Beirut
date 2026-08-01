import ast
from pathlib import Path


PRINTER_MODULE = Path("beirut_pos/services/printer.py")


def test_escpos_is_not_imported_at_module_scope():
    """Jewelry startup must not initialize optional python-escpos backends."""
    tree = ast.parse(PRINTER_MODULE.read_text(encoding="utf-8"))
    imports = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

    assert not any(
        (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("escpos"))
        or (
            isinstance(node, ast.Import)
            and any(alias.name.startswith("escpos") for alias in node.names)
        )
        for node in imports
    )


def test_windows_discovery_stops_before_legacy_backends(monkeypatch):
    from beirut_pos.services import printer

    monkeypatch.setattr(printer, "_IS_WINDOWS", True)
    monkeypatch.setattr(
        printer,
        "_try_usb_printer",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("USB probed on Windows")),
    )
    monkeypatch.setattr(
        printer,
        "_try_file_printer",
        lambda: (_ for _ in ()).throw(AssertionError("file backend probed on Windows")),
    )

    assert printer._find_thermal_printer() is None
