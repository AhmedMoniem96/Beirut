from escpos.printer import File

p = File('/dev/usb/lp0')
p.open()

# POS-80 specific initialization
p._raw(b"\x1B\x40")  # Initialize
p._raw(b"\x1B\x61\x00")  # Left align
p._raw(b"\x1B\x21\x00")  # Normal font

# IMPORTANT: Use codepage for your language
p._raw(b"\x1Bt\x00")  # CP437 (standard)

# Simple test
p.text("=" * 32 + "\n")
p.text("POS-80 TEST\n")
p.text("=" * 32 + "\n")
p.text("Hello World\n")
p.text("123456789\n")
p.text("\n\n\n")

p.cut()
p.close()

print("✅ Test sent")
