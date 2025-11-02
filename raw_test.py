from escpos.printer import File

p = File('/dev/usb/lp0')
p.open()

print("🧪 Sending raw ESC/POS commands...")

# Method 1: Direct byte writing to device
p.device.write(b"\x1B\x40")  # ESC @ - Initialize
p.device.write(b"DIRECT WRITE TEST\n")
p.device.write(b"Hello World\n")
p.device.write(b"123456789\n")
p.device.write(b"\n\n\n\n")
p.device.write(b"\x1D\x56\x00")  # Cut paper
p.device.flush()

print("✅ Raw commands sent via device.write()")
p.close()
