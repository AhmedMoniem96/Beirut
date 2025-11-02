from escpos.printer import File

p = File('/dev/usb/lp0')
p.open()

print("🧪 Testing if printer responds to ANY command...")

# Test 1: Just newlines (this should feed paper)
p.device.write(b"\n" * 20)
p.device.flush()

print("✅ Test 1: Sent 20 newlines - did paper feed?")
input("Press Enter after checking if paper moved...")

# Test 2: Try paper cut command
p.device.write(b"\x1D\x56\x00")  # Full cut
p.device.flush()

print("✅ Test 2: Sent cut command - did paper cut?")
input("Press Enter after checking...")

# Test 3: Try partial cut
p.device.write(b"\x1D\x56\x01")  # Partial cut
p.device.flush()

print("✅ Test 3: Sent partial cut")

p.close()
