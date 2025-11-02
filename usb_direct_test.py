import usb.core
import usb.util

# Find the printer
dev = usb.core.find(idVendor=0x0483, idProduct=0x5743)

if dev is None:
    print("❌ Printer not found")
    exit(1)

print(f"✅ Found printer: {dev}")

# Detach kernel driver if active
if dev.is_kernel_driver_active(0):
    print("📌 Detaching kernel driver...")
    dev.detach_kernel_driver(0)

# Set configuration
dev.set_configuration()
print("✅ Configuration set")

# Get endpoint
cfg = dev.get_active_configuration()
intf = cfg[(0,0)]

ep_out = usb.util.find_descriptor(
    intf,
    custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
)

ep_in = usb.util.find_descriptor(
    intf,
    custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_IN
)

print(f"📤 OUT endpoint: {ep_out.bEndpointAddress}")
print(f"📥 IN endpoint: {ep_in.bEndpointAddress}")

# Send data
print("📤 Sending test data...")
test_data = b"\x1B\x40"  # Initialize
test_data += b"USB DIRECT TEST\n"
test_data += b"Hello World\n"
test_data += b"123456789\n"
test_data += b"\n\n\n\n"

ep_out.write(test_data)
print("✅ Data sent!")

# Try to read response
try:
    print("📥 Reading response...")
    response = ep_in.read(64, timeout=1000)
    print(f"📥 Response: {response}")
except Exception as e:
    print(f"⚠️ No response: {e}")

print("\n✅ Test complete - check printer!")
