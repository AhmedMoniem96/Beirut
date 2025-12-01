from beirut_pos.services import printer as printer_module


def test_usblp_device_paths_sorted(monkeypatch):
    monkeypatch.setattr(printer_module.glob, "glob", lambda pattern: ["/dev/usb/lp1", "/dev/usb/lp0"])
    assert printer_module._usblp_device_paths() == ["/dev/usb/lp0", "/dev/usb/lp1"]
