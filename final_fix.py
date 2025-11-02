import re

with open('beirut_pos/services/printer.py', 'r') as f:
    content = f.read()

# 1. Disable USB backend completely
content = re.sub(
    r'def _try_usb_printer\([^)]*\):',
    'def _try_usb_printer(*, allow_when_blocked: bool = False):\n    """USB backend disabled - use File backend instead."""\n    return None\n\ndef _try_usb_printer_DISABLED(*, allow_when_blocked: bool = False):',
    content
)

# 2. Make sure File backend always works
old_find = '''def _find_xp80c_printer():
    _log("🖨️  Searching for thermal printer...")

    if not _ESCPOS_OK or Usb is None:
        _log("❌ ESC/POS library not available")
        return None

    if _DISABLE_ESCPOS:
        _log("ℹ️  ESC/POS disabled by environment variable")
        return None

    # Always try /dev/usb/lp* first (most reliable for Linux)
    printer = _try_file_printer()
    if printer:
        _log("✅ Printing via /dev backend")
        return printer

    # Fallback to direct USB if /dev doesn't work
    printer = _try_usb_printer()
    if printer:
        return printer

    _log("❌ No compatible thermal printers found")
    return None'''

new_find = '''def _find_xp80c_printer():
    _log("🖨️  Searching for thermal printer...")

    if not _ESCPOS_OK:
        _log("❌ ESC/POS library not available")
        return None

    if _DISABLE_ESCPOS:
        _log("ℹ️  ESC/POS disabled by environment variable")
        return None

    # ALWAYS use /dev backend (USB direct has endpoint issues)
    _log("🔧 Using File backend only (USB backend disabled)")
    printer = _try_file_printer()
    if printer:
        _log("✅ Printing via /dev backend")
        return printer

    _log("❌ No /dev/usb/lp* printer found")
    return None'''

content = content.replace(old_find, new_find)

with open('beirut_pos/services/printer.py', 'w') as f:
    f.write(content)

print("✅ Printer fixed - USB backend completely disabled")
print("✅ Will only use File backend (/dev/usb/lp0)")
print("\n⚠️  NOW RESTART YOUR APPLICATION!")
