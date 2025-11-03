from __future__ import annotations
import os, glob, platform, re
from typing import Tuple, Sequence
from PIL import Image, ImageDraw, ImageFont

# --------- Arabic detection ----------
_ARABIC_RX = re.compile(r"[\u0600-\u06FF]")
def contains_arabic(s: str) -> bool: return bool(_ARABIC_RX.search(s or ""))

# --------- Font resolve (Arabic + Latin) ----------
_FONT_CACHE: dict[tuple[str | None, int, bool], ImageFont.FreeTypeFont] = {}

SYSTEM_FONT_CANDIDATES_LINUX = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoKufiArabic-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoKufiArabic-Bold.ttf",
]
SYSTEM_FONT_CANDIDATES_WINDOWS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\trado.ttf",
    r"C:\Windows\Fonts\arabtype.ttf",
]
SYSTEM_FONT_CANDIDATES_MAC = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Al Nile.ttc",
]

def _candidate_paths_from_os() -> list[str]:
    sys = platform.system().lower()
    if "linux" in sys:
        extra: list[str] = []
        for pat in (
            "/usr/share/fonts/truetype/*/*.ttf",
            "/usr/share/fonts/truetype/*/*.ttc",
            "/usr/local/share/fonts/**/*.*tf",
            os.path.expanduser("~/.local/share/fonts/**/*.*tf"),
            os.path.expanduser("~/.fonts/**/*.*tf"),
        ):
            extra.extend(glob.glob(pat, recursive=True))
        extra = [p for p in extra if any(k in p.lower() for k in ("dejavu","noto","amiri","kufi","arab","arial"))]
        return SYSTEM_FONT_CANDIDATES_LINUX + sorted(extra)
    if "windows" in sys: return SYSTEM_FONT_CANDIDATES_WINDOWS
    if "darwin" in sys or "mac" in sys: return SYSTEM_FONT_CANDIDATES_MAC
    return []

def resolve_font_path(explicit_path: str | None = None, *, bold: bool = False) -> str | None:
    if explicit_path and os.path.isfile(explicit_path): return explicit_path
    env = os.getenv("BEIRUT_POS_AR_FONT_BOLD" if bold else "BEIRUT_POS_AR_FONT")
    if env and os.path.isfile(env): return env
    for p in _candidate_paths_from_os():
        name = os.path.basename(p).lower()
        if bold and ("bold" not in name and not name.endswith("bd.ttf") and not name.endswith("bd.ttc")):
            continue
        try:
            ImageFont.truetype(p, size=10); return p
        except Exception:
            continue
    return None

def load_font(font_path: str | None = None, *, size: int = 30, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = (font_path, size, bold)
    if key in _FONT_CACHE: return _FONT_CACHE[key]
    path = resolve_font_path(font_path, bold=bold)
    try: font = ImageFont.truetype(path, size=size) if path else ImageFont.load_default()
    except Exception: font = ImageFont.load_default()
    _FONT_CACHE[key] = font
    return font

# --------- Line raster (slightly more padding so text isn't glued to border) ----------
def render_line_bitmap(
    text: str,
    paper_px: int = 576,
    font: ImageFont.FreeTypeFont | None = None,
    padding: Tuple[int, int, int, int] = (2, 1, 2, 1),  # L,T,R,B — tiny vertical pad
    align: str = "left",
) -> Image.Image:
    if font is None: font = load_font(size=28)
    tmp = Image.new("L", (1, 1), 255); dr = ImageDraw.Draw(tmp)
    x0, y0, x1, y1 = dr.textbbox((0, 0), text, font=font)
    text_w, text_h = (x1 - x0), (y1 - y0)

    W = paper_px
    H = max(text_h + padding[1] + padding[3], text_h + 2)
    img = Image.new("L", (W, H), 255); dr = ImageDraw.Draw(img)

    if align == "center": x = max((W - text_w) // 2, 0)
    elif align == "right": x = max(W - text_w - padding[2], 0)
    else: x = padding[0]

    y = padding[1]
    dr.text((x, y), text, fill=0, font=font)
    return img.convert("1")

# --------- Helpers ----------
def _measure(text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    tmp = Image.new("L", (1, 1), 255); dr = ImageDraw.Draw(tmp)
    x0, y0, x1, y1 = dr.textbbox((0, 0), text, font=font)
    return (x1 - x0), (y1 - y0)

# --------- FULL-WIDTH table raster (compact but readable) ----------
def render_table_bitmap(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    footer_rows: Sequence[Sequence[str]] | None = None,
    paper_px: int = 576,
    col_widths_px: Sequence[int] | None = None,
    font_body: ImageFont.FreeTypeFont | None = None,
    font_header: ImageFont.FreeTypeFont | None = None,
    font_footer: ImageFont.FreeTypeFont | None = None,
    cell_pad: tuple[int, int] = (8, 4),  # a bit higher per your request
    draw_borders: bool = True,
    col_align: Sequence[str] = ("left", "center", "right", "right"),
) -> Image.Image:
    """
    Full-width table with boxed cells and centered headers.
    footer_rows are drawn in bold at the bottom (e.g., Subtotal/Discount/Total).
    """
    size_env = int(os.getenv("BEIRUT_POS_TABLE_FONT", "30"))
    if font_body is None:   font_body   = load_font(size=size_env)
    if font_header is None: font_header = load_font(size=size_env, bold=True)
    if font_footer is None: font_footer = load_font(size=size_env, bold=True)

    if col_widths_px is None:
        # Item 58%, Qty 11%, Price 15.5%, Total 15.5% => sum 576
        col_widths_px = [332, 64, 90, 90]

    def row_h(cells: Sequence[str], f: ImageFont.ImageFont) -> int:
        h = 0
        for c in cells:
            _, ch = _measure(str(c), f)
            h = max(h, ch + cell_pad[1] * 2)
        return max(h, 30)

    header_h = row_h(headers, font_header)
    body_h   = sum(row_h(r, font_body) for r in rows)
    footer_h = sum(row_h(r, font_footer) for r in (footer_rows or []))
    total_h  = header_h + body_h + footer_h + (2 if draw_borders else 0)

    img = Image.new("L", (paper_px, total_h), 255)
    dr  = ImageDraw.Draw(img)

    def draw_row(y: int, cells: Sequence[str], f: ImageFont.ImageFont, *, header=False, footer=False) -> int:
        x = 0; max_h = row_h(cells, f)
        for i, t in enumerate(cells):
            txt = str(t); cw = col_widths_px[i]
            tw, th = _measure(txt, f)
            align = ("center" if header else col_align[i])
            if align == "right":     tx = x + cw - tw - cell_pad[0]
            elif align == "center":  tx = x + max((cw - tw) // 2, 0)
            else:                    tx = x + cell_pad[0]
            ty = y + max((max_h - th) // 2, 0)
            dr.text((tx, ty), txt, 0, font=f)
            if draw_borders:
                dr.rectangle([x, y, x + cw - 1, y + max_h - 1], outline=0)
            x += cw
        return y + max_h

    y = 0
    y = draw_row(y, headers, font_header, header=True)
    for r in rows:
        y = draw_row(y, r, font_body)
    for r in (footer_rows or []):
        y = draw_row(y, r, font_footer, footer=True)

    return img.convert("1")

# --------- ESC/POS raster ----------
def pil_image_to_escpos_raster(img: Image.Image) -> bytes:
    if img.mode != "1": img = img.convert("1")
    width, height = img.size; row_bytes = (width + 7) // 8
    data = bytearray(b"\x1D\x76\x30" + bytes([0, row_bytes & 0xFF, (row_bytes >> 8) & 0xFF, height & 0xFF, (height >> 8) & 0xFF]))
    px = img.load()
    for y in range(height):
        byte = 0; bit = 7
        for x in range(width):
            if px[x, y] == 0: byte |= (1 << bit)
            bit -= 1
            if bit < 0: data.append(byte); byte = 0; bit = 7
        if bit != 7: data.append(byte)
    return bytes(data)
