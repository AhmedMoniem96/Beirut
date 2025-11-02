import usb.core
import usb.util

def print_receipt(lines):
    """Print directly via USB device."""
    try:
        # Find the printer
        dev = usb.core.find(idVendor=0x0483, idProduct=0x5743)
        if not dev:
            print("❌ Printer not found")
            return False
        
        print(f"✅ Found printer: {dev}")
        
        # Set configuration
        try:
            dev.set_configuration()
        except:
            pass  # May already be configured
        
        # Get endpoint
        cfg = dev.get_active_configuration()
        intf = cfg[(0,0)]
        
        ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        
        if not ep_out:
            print("❌ Could not find OUT endpoint")
            return False
        
        print(f"✅ OUT endpoint: 0x{ep_out.bEndpointAddress:02x}")
        
        # Send data
        data = b"\x1B\x40"  # Initialize
        for line in lines:
            data += line.encode('cp1256', errors='replace') + b"\n"
        data += b"\n\n\n"
        data += b"\x1D\x56\x00"  # Cut
        
        ep_out.write(data)
        print(f"✅ Sent {len(data)} bytes")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_lines = [
        "================================",
        "  CAFE BEIRUT",
        "  كافيه بيروت",
        "================================",
        "Date: 2025-11-02",
        "Table: A1",
        "--------------------------------",
        "1. قهوة × 2           10.00",
        "2. شاي × 1             5.00",
        "================================",
        "Total:                15.00",
        "================================",
        "شكراً لزيارتكم",
        "Thank you!",
    ]
    print_receipt(test_lines)
