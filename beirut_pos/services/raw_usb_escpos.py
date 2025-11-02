from __future__ import annotations

import usb.core
import usb.util

from .arabic_codec import sanitize_line, shape_bidi_arabic, encode_for_printer


class RawUsbEscpos:
    """
    Raw ESC/POS adapter using pyusb.
    Ensures Arabic: sets code page, shapes+bidi, CP1256 encoding.
    """

    def __init__(self, vid: int = 0x0483, pid: int = 0x5743, interface: int = 0) -> None:
        self.vid = vid
        self.pid = pid
        self.interface = interface
        self.dev: usb.core.Device | None = None
        self.ep_out: usb.core.Endpoint | None = None
        self.encoding = "cp1256"
        self.name = f"RawUsbEscpos({hex(self.vid)}:{hex(self.pid)})"
        self._connect()

    def _connect(self) -> None:
        dev = usb.core.find(idVendor=self.vid, idProduct=self.pid)
        if dev is None:
            raise RuntimeError(f"USB printer {hex(self.vid)}:{hex(self.pid)} not found")

        try:
            if dev.is_kernel_driver_active(self.interface):
                dev.detach_kernel_driver(self.interface)
        except (NotImplementedError, AttributeError, usb.core.USBError):
            pass

        dev.set_configuration()
        cfg = dev.get_active_configuration()
        intf = cfg[(self.interface, 0)]
        ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
            == usb.util.ENDPOINT_OUT,
        )
        if ep_out is None:
            raise RuntimeError("No BULK OUT endpoint on printer interface")

        self.dev = dev
        self.ep_out = ep_out

        self._raw(b"\x1B@")

        for code, enc in [(0x13, "cp1256"), (0x12, "cp864"), (0x0F, "cp720"), (0x16, "cp862")]:
            try:
                self._raw(b"\x1Bt" + bytes([code]))
                self.encoding = enc
                break
            except Exception:
                continue

        try:
            self._raw(b"\x1B\x61\x00")
        except Exception:
            pass

    def _write(self, data: bytes) -> None:
        if self.ep_out is None:
            raise RuntimeError("Printer not connected (no OUT endpoint)")
        self.ep_out.write(data)

    def _raw(self, data: bytes) -> None:
        self._write(data)

    def text(self, txt: str) -> None:
        sanitized = sanitize_line(txt)
        shaped = shape_bidi_arabic(sanitized)
        payload = encode_for_printer(shaped, self.encoding)
        self._write(payload)

    def set(self, **kwargs) -> None:  # noqa: D401 - compatibility no-op
        return

    def cut(self) -> None:
        self._write(b"\x1D\x56\x00")

    def close(self) -> None:
        try:
            if self.dev is not None:
                usb.util.dispose_resources(self.dev)
        except Exception:
            pass
