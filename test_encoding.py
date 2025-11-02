from escpos.printer import File

p = File('/dev/usb/lp0')
p.open()

print("Testing different methods...")

# Test 1: Initialize printer
p._raw(b"\x1B@")  # ESC @ - Initialize
print("✅ Sent initialize command")

# Test 2: Try printer.text() method (handles encoding automatically)
try:
    p.text("=== TEXT METHOD TEST ===\n")
    p.text("Hello World\n")
    p.text("Numbers: 123456789\n")
    p.text("Symbols: !@#$%^&*()\n")
    print("✅ Sent via text() method")
except Exception as e:
    print(f"❌ text() method failed: {e}")

# Test 3: Set character size (makes text visible if too small)
p._raw(b"\x1D\x21\x11")  # Double width and height
p._raw(b"BIG TEXT TEST\n")
p._raw(b"\x1D\x21\x00")  # Normal size
print("✅ Sent size test")

# Test 4: Try different alignments
p._raw(b"\x1B\x61\x01")  # Center
p._raw(b"CENTERED\n")
p._raw(b"\x1B\x61\x00")  # Left
p._raw(b"LEFT ALIGNED\n")
print("✅ Sent alignment test")

# Finish
p._raw(b"\n\n\n\n")
p.cut()
p.close()

print("\n✅ All tests sent to printer!")
print("Check the paper - you should see:")
print("  - 'TEXT METHOD TEST' line")
print("  - 'Hello World'")
print("  - 'BIG TEXT TEST' in large letters")
print("  - 'CENTERED' in center")
print("  - 'LEFT ALIGNED' on left")
