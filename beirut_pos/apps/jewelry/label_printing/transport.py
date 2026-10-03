import sys
from dataclasses import dataclass


class LabelTransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class Submission:
    submitted: bool
    printer_name: str
    copies: int
    physical_print_confirmed: bool = False


def _validate(image, printer_name, copies):
    if not isinstance(printer_name, str) or not printer_name:
        raise LabelTransportError(
            "printer_name must be a non-empty exact queue name"
        )

    if isinstance(copies, bool) or not isinstance(copies, int) or copies < 1:
        raise LabelTransportError(
            "copies must be an integer >= 1"
        )

    if getattr(image, "size", None) != (304, 200):
        raise LabelTransportError(
            "label image must be exactly 304 x 200 pixels"
        )

    if getattr(image, "mode", None) != "1":
        raise LabelTransportError(
            "label image must use Pillow mode '1'"
        )


def print_image(image, printer_name, copies=1):
    _validate(image, printer_name, copies)

    if sys.platform != "win32":
        raise LabelTransportError(
            "Windows GDI transport is only available on Windows"
        )

    try:
        import win32con
        import win32ui
        from PIL import ImageWin
    except ImportError as e:
        raise LabelTransportError(
            "pywin32 and Pillow Windows support are required"
        ) from e

    dc = None

    try:
        dc = win32ui.CreateDC()

        try:
            dc.CreatePrinterDC(printer_name)
        except Exception as e:
            raise LabelTransportError(
                f"Unable to use printer queue {printer_name!r}"
            ) from e

        # The rendered label is fixed at 304x200 pixels.
        # At 203 DPI this corresponds to approximately 38x25 mm.
        printable_width = dc.GetDeviceCaps(win32con.HORZRES)
        printable_height = dc.GetDeviceCaps(win32con.VERTRES)

        if 304 > printable_width or 200 > printable_height:
            raise LabelTransportError(
                "label exceeds printable area "
                f"(required=304x200, "
                f"printable={printable_width}x{printable_height})"
            )

        # CreatePrinterDC already uses the printable-area origin.
        # Do not manually apply PHYSICALOFFSETX/Y.
        dc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
        dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)

        # Keep the renderer output strictly 1-bit, but convert only the
        # Windows GDI copy to RGB. Some thermal-printer Windows drivers
        # interpret 1-bit DIB palette polarity incorrectly and produce
        # a solid black label.
        gdi_image = image.convert("RGB")
        dib = ImageWin.Dib(gdi_image)

        for _ in range(copies):
            dc.StartDoc("BeirutPOS Jewelry Label")

            try:
                dc.StartPage()

                dib.draw(
                    dc.GetHandleOutput(),
                    (0, 0, 304, 200),
                )

                dc.EndPage()
                dc.EndDoc()

            except Exception as e:
                try:
                    dc.AbortDoc()
                except Exception:
                    pass

                if isinstance(e, LabelTransportError):
                    raise

                raise LabelTransportError(
                    "Windows GDI label submission failed"
                ) from e

        return Submission(
            submitted=True,
            printer_name=printer_name,
            copies=copies,
        )

    finally:
        if dc is not None:
            try:
                dc.DeleteDC()
            except Exception:
                pass