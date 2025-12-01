from beirut_pos.services import printer as printer_module


def test_ensure_dirs_creates_expected_structure(tmp_path, monkeypatch):
    output_root = tmp_path / "prints"
    receipts = output_root / "receipts"
    bar = output_root / "bar_tickets"
    log_path = output_root / "printer.log"

    monkeypatch.setattr(printer_module, "_OUTPUT_ROOT", output_root)
    monkeypatch.setattr(printer_module, "_RECEIPTS_DIR", receipts)
    monkeypatch.setattr(printer_module, "_BAR_DIR", bar)
    monkeypatch.setattr(printer_module, "_LOG_PATH", log_path)

    printer_module._ensure_dirs()

    assert receipts.exists()
    assert bar.exists()
    assert log_path.exists()
