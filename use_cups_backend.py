# Update printer.py to use CUPS backend
with open('beirut_pos/services/printer.py', 'r') as f:
    content = f.read()

# Find the _try_file_printer to add CUPS support
insert_after = "def _try_file_printer(device_path: Optional[str] = None):"

cups_code = '''
def _try_cups_printer(printer_name: str = "POS-80"):
    """Try to use CUPS printer via lp command."""
    import subprocess
    _log(f"🔍 Trying CUPS printer: {printer_name}")
    try:
        # Check if printer exists
        result = subprocess.run(['lpstat', '-p', printer_name], 
                              capture_output=True, text=True, timeout=2)
        if result.returncode == 0:
            _log(f"✅ CUPS printer {printer_name} found")
            # Return a special marker that we'll handle later
            return ("CUPS", printer_name)
        else:
            _log(f"❌ CUPS printer {printer_name} not found")
            return None
    except Exception as e:
        _log_printer_error(f"CUPS check failed", e)
        return None

'''

# Insert before _try_file_printer
if "def _try_cups_printer" not in content:
    content = content.replace(insert_after, cups_code + insert_after)
    print("✅ Added CUPS backend support")

# Update _find_xp80c_printer to try CUPS first
old_find = '''    # ALWAYS use /dev backend (USB direct has endpoint issues)
    _log("🔧 Using File backend only (USB backend disabled)")
    printer = _try_file_printer()
    if printer:
        _log("✅ Printing via /dev backend")
        return printer

    _log("❌ No /dev/usb/lp* printer found")
    return None'''

new_find = '''    # Try CUPS first (most reliable when CUPS manages the printer)
    cups_result = _try_cups_printer("POS-80")
    if cups_result:
        _log("✅ Using CUPS backend")
        return cups_result
    
    # Fallback to /dev backend
    _log("🔧 Trying File backend...")
    printer = _try_file_printer()
    if printer:
        _log("✅ Printing via /dev backend")
        return printer

    _log("❌ No printer found")
    return None'''

content = content.replace(old_find, new_find)

with open('beirut_pos/services/printer.py', 'w') as f:
    f.write(content)

print("✅ Updated to use CUPS backend")
print("⚠️  RESTART YOUR APP!")
