# Read the file
with open('beirut_pos/services/printer.py', 'r') as f:
    content = f.read()

# Find and replace the _try_file_printer function
old_code = """        try:
            _log(f"🔍 Trying /dev backend at {device_path}")
            printer = File(device_path)
            printer.open(raise_not_found=False)
            _log(f"✅ /dev backend ready at {device_path}")
            return printer"""

new_code = """        try:
            _log(f"🔍 Trying /dev backend at {device_path}")
            printer = File(device_path)
            try:
                printer.open(raise_not_found=True)  # Actually open the device
                _log(f"✅ /dev backend ready at {device_path}")
                return printer
            except Exception as open_exc:
                _log_printer_error(f"Failed to open {device_path}", open_exc)
                return None"""

if old_code in content:
    content = content.replace(old_code, new_code)
    print("✅ Fixed device_path opening")
else:
    print("⚠️ Could not find device_path code block")

# Also fix the auto-detect loop
old_loop = """        try:
            _log(f"🔍 Trying /dev backend at {path}")
            printer = File(path)
            printer.open(raise_not_found=False)
            _log(f"✅ /dev backend ready at {path}")
            return printer"""

new_loop = """        try:
            _log(f"🔍 Trying /dev backend at {path}")
            printer = File(path)
            try:
                printer.open(raise_not_found=True)  # Actually open the device
                _log(f"✅ /dev backend ready at {path}")
                return printer
            except Exception as open_exc:
                _log_printer_error(f"Failed to open {path}", open_exc)
                continue"""

if old_loop in content:
    content = content.replace(old_loop, new_loop)
    print("✅ Fixed auto-detect loop")
else:
    print("⚠️ Could not find auto-detect loop")

# Write back
with open('beirut_pos/services/printer.py', 'w') as f:
    f.write(content)

print("✅ Printer file updated!")
