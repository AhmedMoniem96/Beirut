from escpos.printer import File

p = File('/dev/usb/lp0')
p.open()

print("🧪 Testing line feed (like the feed button)...")

# Just send line feeds
for i in range(10):
    p.device.write(b"\n")
    
p.device.flush()
p.close()

print("✅ Sent 10 line feeds - did paper move?")
