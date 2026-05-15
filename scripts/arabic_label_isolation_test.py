#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
import arabic_reshaper
from bidi.algorithm import get_display


RAW_TEXT = "أقراط لؤلؤ"
OUTPUT_DIR = Path("/tmp")
FONT_CANDIDATES = [
    Path("beirut_pos/assets/fonts/NotoNaskhArabic-Regular.ttf"),
    Path("assets/fonts/NotoNaskhArabic-Regular.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]


def _font(size: int = 54) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _save_variant(text: str, out_path: Path) -> None:
    img = Image.new("RGB", (900, 220), "white")
    draw = ImageDraw.Draw(img)
    fnt = _font()
    draw.text((40, 80), text, font=fnt, fill="black")
    img.save(out_path)
    print(f"saved: {out_path} | text={repr(text)} | cps={[f'U+{ord(ch):04X}' for ch in text]}")


def main() -> None:
    reshaped_only = arabic_reshaper.reshape(RAW_TEXT)
    bidi_only = get_display(RAW_TEXT)
    reshaped_bidi = get_display(reshaped_only)

    _save_variant(RAW_TEXT, OUTPUT_DIR / "arabic_label_test_raw.png")
    _save_variant(reshaped_only, OUTPUT_DIR / "arabic_label_test_reshaper_only.png")
    _save_variant(bidi_only, OUTPUT_DIR / "arabic_label_test_bidi_only.png")
    _save_variant(reshaped_bidi, OUTPUT_DIR / "arabic_label_test_reshape_bidi.png")


if __name__ == "__main__":
    main()
