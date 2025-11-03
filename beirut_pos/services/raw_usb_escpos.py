from __future__ import annotations
import os, time
import usb.core, usb.util
from .arabic_codec import sanitize_line, shape_bidi_arabic, encode_for_printer

try:
    from .arabic_bitmap import (
        render_line_bitmap,
        render_table_bitmap,
        pil_image_to_escpos_raster,
        load_font,
    )
    _BITMAP_OK = True
except Exception:
    _BITMAP_OK = False


class RawUsbEscpos:
    """pyusb ESC/POS with bitmap rendering, alignment tags, and full-width tables."""
    def __init__(self, vid: int = 0x0483, pid: int = 0x5743, interface: int = 0) -> None:
        self.vid, self.pid, self.interface = vid, pid, interface
        self.dev: usb.core.Device | None = None
        self.ep_out: usb.core.Endpoint | None = None
        self.encoding = "cp1256"
        self.name = f"RawUsbEscpos({hex(self.vid)}:{hex(self.pid)})"
        self._delay_s = max(0.0, float(os.getenv("BEIRUT_POS_WRITE_DELAY_MS", "0")) / 1000.0)
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
        self.dev, self.ep_out = dev, ep_out

        self._raw(b"\x1B@")        # reset
        self._raw(b"\x1B\x61\x00") # left align device

        for code, enc in [(0x13, "cp1256"), (0x12, "cp864"), (0x0F, "cp720"), (0x16, "cp862")]:
            try:
                self._raw(b"\x1Bt" + bytes([code]))
                self.encoding = enc
                break
            except Exception:
                continue

    def _write(self, data: bytes) -> None:
        if self.ep_out is None:
            raise RuntimeError("Printer not connected (no OUT endpoint)")
        self.ep_out.write(data)
        if self._delay_s:
            time.sleep(self._delay_s)

    def _raw(self, data: bytes) -> None:
        self._write(data)

    def text(self, txt: str) -> None:
        sanitized = sanitize_line(txt)
        shaped = shape_bidi_arabic(sanitized)
        self._write(encode_for_printer(shaped, self.encoding))

    def set(self, **kwargs) -> None:
        return

    def cut(self) -> None:
        try:
            self._raw(b"\n")
            self._raw(b"\x1B\x64\x02")  # feed 2 lines
            self._raw(b"\x1B\x4A\x30")  # feed 48 dots (~6mm)
            time.sleep(0.15)
        except Exception:
            pass
        self._write(b"\x1D\x56\x00")

    def close(self) -> None:
        try:
            if self.dev is not None:
                usb.util.dispose_resources(self.dev)
        except Exception:
            pass

    # --- main renderer, now with font_size override ---
    def text_or_bitmap(
        self,
        line: str,
        *,
        font_path: str | None = None,
        align: str = "left",
        font_size: int = 28,
    ):
        s = sanitize_line(line or "")
        force_bitmap = (os.getenv("BEIRUT_POS_AR_FORCE_BITMAP", "1") != "0")
        use_shaper   = (os.getenv("BEIRUT_POS_AR_SHAPER", "1") != "0")
        custom_font  = os.getenv("BEIRUT_POS_AR_FONT_PATH", None)

        if force_bitmap and _BITMAP_OK:
            shaped = shape_bidi_arabic(s) if use_shaper else s
            font = load_font(custom_font or font_path, size=font_size)
            img = render_line_bitmap(shaped, paper_px=576, font=font, align=align)
            self._raw(pil_image_to_escpos_raster(img))
        else:
            shaped = shape_bidi_arabic(s) if use_shaper else s
            self._raw(encode_for_printer(shaped, self.encoding) + b"\n")

    def print_lines(self, lines, *, font_path: str | None = None) -> None:
        """
        Tags:
          >>C  center   >>R  right   >>L  left
          >>S  small font (labels/meta)
        """
        self._raw(b"\x1B@")
        self._raw(b"\x1B\x61\x00")

        for raw in lines:
            line = raw or ""
            align = "left"
            fsize = 28

            # small-font tag
            if line.startswith(">>S "):
                fsize = 22
                line = line[4:].lstrip()

            # alignment tag (after removing >>S if present)
            if line.startswith(">>C "):
                align, line = "center", line[4:]
            elif line.startswith(">>R "):
                align, line = "right",  line[4:]
            elif line.startswith(">>L "):
                align, line = "left",   line[4:]

            self.text_or_bitmap(line, font_path=font_path, align=align, font_size=fsize)

    # full-width table passthrough
    # ... inside class RawUsbEscpos ...

    def print_table(
            self,
            headers,
            rows,
            *,
            footer_rows=None,
            font_size: int = 30,
            col_widths_px=None,
            col_align=("left", "center", "right", "right"),
            cell_pad=(8, 4),
            draw_borders=True,
    ):
        if not _BITMAP_OK:
            self.print_lines([" | ".join(headers)] + [" | ".join(map(str, r)) for r in rows])
            if footer_rows:
                self.print_lines([" | ".join(map(str, r)) for r in footer_rows])
            return

        font_body = load_font(size=font_size)
        # 👇 make headers clearly smaller than body
        font_header = load_font(size=max(14, font_size - 8), bold=True)
        font_footer = load_font(size=font_size, bold=True)

        img = render_table_bitmap(
            headers, rows,
            footer_rows=footer_rows,
            paper_px=576,
            col_widths_px=col_widths_px,
            font_body=font_body, font_header=font_header, font_footer=font_footer,
            cell_pad=cell_pad, draw_borders=draw_borders,
            col_align=col_align,
        )
        self._raw(pil_image_to_escpos_raster(img))
