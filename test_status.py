from escpos.printer import File
import time

p = File('/dev/usb/lp0')
p.open()

print("Checking printer status...")

# Query printer status
try:
    # DLE EOT n - Transmit printer status
    p._raw(b"\x10\x04\x01")  # Real-time status
    time.sleep(0.1)
    
    # Try to read response (if available)
    print("✅ Status query sent")
except Exception as e:
    print(f"⚠️ Status query failed: {e}")

# Query paper sensor
try:
    p._raw(b"\x10\x04\x04")  # Paper sensor status
    time.sleep(0.1)
    print("✅ Paper sensor query sent")
except Exception as e:
    print(f"⚠️ Paper sensor query failed: {e}")

# Force immediate print (bypasses buffer)
print("\nTrying immediate print commands...")
p._raw(b"\x1B@")  # Reset
p._raw(b"A")      # Single character
p._raw(b"\x0C")   # Form feed (immediate print)
p._raw(b"\n\n\n")

p.close()
print("✅ Commands sent")
