import sys
sys.path.insert(0, '.')

from beirut_pos.services.printer import printer

print("🔄 Forcing printer reload...")

# Close current printer if any
if hasattr(printer, '_escpos_printer') and printer._escpos_printer:
    try:
        printer._escpos_printer.close()
    except:
        pass

# Force File printer
from escpos.printer import File
new_printer = File('/dev/usb/lp0')
new_printer.open()

printer._escpos_printer = new_printer
print("✅ Printer reloaded with File backend")
print(f"   Type: {type(new_printer)}")
print(f"   Device: {new_printer.device}")

# Test it
print("\n🧪 Testing...")
new_printer.text("Printer reloaded!\n")
new_printer.text("تم إعادة تحميل الطابعة\n")
new_printer.text("\n\n")
new_printer.cut()
print("✅ Test print sent!")
