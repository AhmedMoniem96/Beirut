import json

import pytest

from beirut_pos.apps.jewelry.services import barcode_printer


class BackendFailure(RuntimeError):
    code = "spooler_offline"
    stage = "StartDocPrinter"


def test_diagnostic_wrapper_preserves_structured_backend_failure(monkeypatch):
    captured = {}

    def fake_log(context, exc, *, tb=None, extra=None):
        captured.update(context=context, exc=exc, tb=tb, extra=extra)

    monkeypatch.setattr(barcode_printer.error_handling, "log_exception", fake_log)
    original = BackendFailure("The configured spooler is offline")
    try:
        raise original
    except BackendFailure as caught:
        diagnostic = barcode_printer._diagnostic_error(
            caught,
            context=barcode_printer.BarcodePrintContext("RP310", 2, 38.0, 25.0),
            backend="windows-raw",
            stage="RAW dispatch",
        )

    assert diagnostic.original_exception is original
    assert diagnostic.original_type is BackendFailure
    assert diagnostic.original_type_name == "BackendFailure"
    assert diagnostic.code == "spooler_offline"
    assert diagnostic.original_message == "The configured spooler is offline"
    assert diagnostic.stage == "StartDocPrinter"
    assert str(diagnostic) == diagnostic.original_message
    assert captured["exc"] is original
    assert captured["tb"] is original.__traceback__
    assert json.loads(captured["extra"]) == {
        "backend": "windows-raw",
        "copies": 2,
        "height_mm": 25.0,
        "printer_name": "RP310",
        "stage": "StartDocPrinter",
        "width_mm": 38.0,
    }


def test_try_print_surfaces_original_actionable_message(monkeypatch):
    def fail(*args, **kwargs):
        raise BackendFailure("Access denied by the Windows spooler")

    monkeypatch.setattr(barcode_printer, "print_barcode_label_image", fail)
    monkeypatch.setattr(barcode_printer.error_handling, "log_exception", lambda *args, **kwargs: None)

    with pytest.raises(barcode_printer.BarcodePrintDiagnosticError) as raised:
        barcode_printer.try_print_barcode_label_image(
            object(), printer_name="RP310", copies=1, retries=0
        )

    assert str(raised.value) == "Access denied by the Windows spooler"
    assert raised.value.code == "spooler_offline"
