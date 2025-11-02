from escpos.printer import File
import time

p = File('/dev/usb/lp0')
p.open()

print("Testing different initialization sequences...")

# Test 1: Multiple resets
print("1️⃣ Trying hard reset...")
p._raw(b"\x1B@")  # ESC @
time.sleep(0.2)
p._raw(b"\x1B@")  # Double reset
time.sleep(0.2)

# Test 2: Wake up printer (some printers are in sleep mode)
print("2️⃣ Waking up printer...")
p._raw(b"\x1B\x3D\x01")  # ESC = 1 (Select printer)
time.sleep(0.1)

# Test 3: Set to standard mode
print("3️⃣ Setting standard mode...")
p._raw(b"\x1B\x21\x00")  # ESC ! 0 (Cancel emphasized/double-strike/etc)

# Test 4: Enable printing
print("4️⃣ Enabling print mode...")
p._raw(b"\x1B\x38")  # ESC 8 (Cancel paper-out disable)

# Test 5: Set line spacing
print("5️⃣ Setting line spacing...")
p._raw(b"\x1B\x33\x20")  # ESC 3 n (Set line spacing to 32/180")

# Test 6: Simple ASCII only (no special chars)
print("6️⃣ Sending simple ASCII...")
p._raw(b"TEST\n")
p._raw(b"1234\n")
p._raw(b"ABCD\n")

# Test 7: Try bitmap mode (some printers need this)
print("7️⃣ Trying graphics mode...")
p._raw(b"\x1D\x76\x30\x00")  # Start raster bitmap
# Send 1 line of black pixels (8 dots)
p._raw(b"\x01\x00\x08\x00")  # Width: 1, Height: 8
p._raw(b"\xFF")  # 8 black dots

# Test 8: Bold text (sometimes more visible)
print("8️⃣ Trying bold...")
p._raw(b"\x1B\x45\x01")  # ESC E 1 (Bold ON)
p._raw(b"BOLD TEST\n")
p._raw(b"\x1B\x45\x00")  # ESC E 0 (Bold OFF)

# Test 9: Underline (visual test)
print("9️⃣ Trying underline...")
p._raw(b"\x1B\x2D\x02")  # ESC - 2 (Thick underline)
p._raw(b"UNDERLINE\n")
p._raw(b"\x1B\x2D\x00")  # ESC - 0 (Underline OFF)

# Finish
p._raw(b"\n\n\n\n\n")
p.cut()
p.close()

print("\n" + "="*50)
print("✅ All commands sent!")
print("="*50)
print("\nCheck the paper. You should see:")
print("  - 'TEST' / '1234' / 'ABCD'")
print("  - A small black line (bitmap test)")
print("  - 'BOLD TEST'")
print("  - 'UNDERLINE' with underline")
print("\nIf STILL blank:")
print("  → Printer may be in a special mode")
print("  → Try turning printer OFF and ON")
print("  → Check if printer has a 'feed' button - press it")
