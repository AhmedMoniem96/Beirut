with open('beirut_pos/services/printer.py', 'r') as f:
    content = f.read()

# Add UsbDirectPrinter class after imports
usb_class = '''
# ---------------- Direct USB Printer ----------------
class UsbDirectPrinter:
    """Direct USB printing using pyusb."""
    def __init__(self, vendor=0x0483, product=0x5743):
        import usb.core
        import usb.util
        self.dev = usb.core.find(idVendor=vendor, idProduct=product)
        if not self.dev:
            raise Exception("Printer not found")
        try:
            self.dev.set_configuration()
        except:
            pass
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0,0)]
        self.ep_out = usb.util.find_descriptor(
            intf,
            custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress) == usb.util.ENDPOINT_OUT
        )
        self.device = self  # For compatibility
        self._buffer = b""
        
    def open(self):
        pass
        
    def close(self):
        pass
        
    def hw(self, cmd):
        if cmd == "INIT":
            self._buffer += b"\\x1B\\x40"
            
    def set(self, **kwargs):
        pass  # Ignore formatting for now
        
    def text(self, txt):
        # ASCII only for now - Arabic needs proper shaping
        try:
            self._buffer += txt.encode('ascii', errors='replace')
        except:
            self._buffer += txt.encode('utf-8', errors='replace')
            
    def cut(self):
        self._buffer += b"\\n\\n\\n"
        self._buffer += b"\\x1D\\x56\\x00"
        self.ep_out.write(self._buffer)
        self._buffer = b""
        
    def _raw(self, data):
        self._buffer += data

'''

insert_point = "from ..core.paths import DATA_DIR"
if "class UsbDirectPrinter" not in content:
    content = content.replace(insert_point, insert_point + "\\n" + usb_class)
    print("✅ Added UsbDirectPrinter")

# Update _find_xp80c_printer
old_find = '''    _log("❌ No printer found")
    return None'''

new_find = '''    # Try direct USB as last resort
    _log("🔧 Trying direct USB...")
    try:
        printer = UsbDirectPrinter(0x0483, 0x5743)
        _log("✅ Using direct USB printer")
        return printer
    except Exception as e:
        _log_printer_error("Direct USB failed", e)
    
    _log("❌ No printer found")
    return None'''

content = content.replace(old_find, new_find)

with open('beirut_pos/services/printer.py', 'w') as f:
    f.write(content)

print("✅ Integrated USB printer!")
print("⚠️ RESTART YOUR APP!")
