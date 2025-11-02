import usb.core
import usb.util

dev = usb.core.find(idVendor=0x0483, idProduct=0x5743)
dev.set_configuration()
cfg = dev.get_active_configuration()
intf = cfg[(0,0)]
ep_out = usb.util.find_descriptor(intf, custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT)

# Set codepage for Arabic
data = b"\x1B\x40"           # Initialize
data += b"\x1Bt\x13"         # Select CP1256 (Arabic Windows)
data += b"ASCII: Hello\n"
data += "Arabic: مرحبا\n".encode('cp1256')
data += b"\n\n\n"
data += b"\x1D\x56\x00"

ep_out.write(data)
print("✅ Sent with CP1256 encoding")
