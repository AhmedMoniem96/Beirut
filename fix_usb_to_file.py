# Read the printer.py file
with open('beirut_pos/services/printer.py', 'r') as f:
    content = f.read()

# Find the _try_usb_printer call and comment it out
old_init = """    # Always try /dev/usb/lp* first (most reliable for Linux)
    printer = _try_file_printer()
    if printer:
        _log("✅ Printing via /dev backend")
        return printer

    # Fallback to direct USB if /dev doesn't work
    printer = _try_usb_printer()
    if printer:
        return printer"""

new_init = """    # Always use /dev/usb/lp* (USB direct requires root, /dev works for regular users)
    printer = _try_file_printer()
    if printer:
        _log("✅ Printing via /dev backend")
        return printer

    # Skip USB backend (needs root permissions)
    # printer = _try_usb_printer()
    # if printer:
    #     return printer"""

if old_init in content:
    content = content.replace(old_init, new_init)
    with open('beirut_pos/services/printer.py', 'w') as f:
        f.write(content)
    print("✅ Fixed to use File printer only")
else:
    print("⚠️ Could not find the code to fix")
