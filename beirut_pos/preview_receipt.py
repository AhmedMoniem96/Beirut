from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import textwrap
import arabic_reshaper
from bidi.algorithm import get_display

# Path to the last generated receipt
txt_path = Path.home() / ".beirut_pos/data/prints/receipts"
txt_files = sorted(txt_path.glob("*.txt"), reverse=True)
if not txt_files:
    print("No receipts found!")
    exit(1)

receipt_path = txt_files[0]
text = receipt_path.read_text(encoding="utf-8")

# Optional: reshape Arabic so it's visually correct
reshaped = arabic_reshaper.reshape(text)
bidi_text = get_display(reshaped)

# Set up the image canvas (width ~80mm, height auto)
width = 580
lines = bidi_text.splitlines()
font = ImageFont.load_default()

# Estimate height based on text lines
line_height = 22
height = line_height * (len(lines) + 2)

img = Image.new("RGB", (width, height), color="white")
draw = ImageDraw.Draw(img)

y = 10
for line in lines:
    draw.text((10, y), line, font=font, fill="black", align="right")
    y += line_height

# Save the preview
out_path = receipt_path.with_suffix(".jpg")
img.save(out_path)
print(f"✅ Preview saved as: {out_path}")
