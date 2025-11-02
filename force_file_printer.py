# Read the printer.py file
with open('beirut_pos/services/printer.py', 'r') as f:
    content = f.read()

# Find the USB_PRINTER_IDS list and comment out the STMicroelectronics entry
old_ids = """USB_PRINTER_IDS = [
    (0x0483, 0x5743),  # STMicroelectronics USB Printer Port
    (XP80C_VENDOR_ID, XP80C_PRODUCT_ID),
    (0x04B8, 0x0202),  # Epson TM-T88IV
    (0x04B8, 0x0E15),  # Epson TM-T88V
    (0x067B, 0x2305),  # Prolific PL2305 bridge
]"""

new_ids = """USB_PRINTER_IDS = [
    # (0x0483, 0x5743),  # STMicroelectronics - DISABLED (use File backend instead)
    (XP80C_VENDOR_ID, XP80C_PRODUCT_ID),
    (0x04B8, 0x0202),  # Epson TM-T88IV
    (0x04B8, 0x0E15),  # Epson TM-T88V
    (0x067B, 0x2305),  # Prolific PL2305 bridge
]"""

if old_ids in content:
    content = content.replace(old_ids, new_ids)
    with open('beirut_pos/services/printer.py', 'w') as f:
        f.write(content)
    print("✅ Disabled USB backend for your printer")
    print("✅ It will now use File backend (/dev/usb/lp0)")
else:
    print("⚠️ Could not find USB_PRINTER_IDS")
