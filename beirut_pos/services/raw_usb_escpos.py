from __future__ import annotations

import usb.core
import usb.util


class RawUsbEscpos:
    """Minimal ESC/POS adapter using pyusb for STMicroelectronics USB printers."""

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
        except (NotImplementedError, AttributeError):
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

    def _write(self, data: bytes) -> None:
        if self.ep_out is None:
            raise RuntimeError("Printer not connected (no OUT endpoint)")
        self.ep_out.write(data)

    def _raw(self, data: bytes) -> None:
        self._write(data)

    def text(self, txt: str) -> None:
        payload = txt.encode(self.encoding, errors="replace")
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
