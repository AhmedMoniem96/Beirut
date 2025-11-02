import usb.core
import usb.util

def print_receipt():
    """Print ASCII only test."""
    try:
        dev = usb.core.find(idVendor=0x0483, idProduct=0x5743)
        dev.set_configuration()
        
        cfg = dev.get_active_configuration()
        intf = cfg[(0,0)]
        ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        
        # ASCII ONLY - no Arabic
        data = b"\x1B\x40"  # Initialize
        data += b"================================\n"
        data += b"       CAFE BEIRUT\n"
        data += b"================================\n"
        data += b"Date: 2025-11-02\n"
        data += b"Table: A1\n"
        data += b"Cashier: Ahmed\n"
        data += b"--------------------------------\n"
        data += b"1. Coffee x2          10.00\n"
        data += b"2. Tea x1              5.00\n"
        data += b"================================\n"
        data += b"Total:                15.00\n"
        data += b"================================\n"
        data += b"Thank you!\n"
        data += b"\n\n\n"
        data += b"\x1D\x56\x00"  # Cut
        
        ep_out.write(data)
        print(f"✅ Sent ASCII receipt")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

print_receipt()
