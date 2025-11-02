import sys
sys.path.insert(0, '.')

from escpos.printer import File

print("🎉 Printing receipt the working way...")

# Open printer directly
p = File('/dev/usb/lp0')
p.open()

print("✅ Printer opened")

# Initialize
p.hw("INIT")

# Print receipt
p.set(align='center', bold=True, double_height=True)
p.text("CAFE BEIRUT\n")
p.text("كافيه بيروت\n")
p.set(align='left', bold=False, double_height=False)

p.text("=" * 32 + "\n")
p.text("Date: 2025-11-02 22:00\n")
p.text("Table: A1\n")
p.text("Cashier: Ahmed\n")
p.text("-" * 32 + "\n")

p.text("1. قهوة x2           10.00\n")
p.text("2. شاي x1             3.00\n")
p.text("   (سكر خفيف)\n")
p.text("3. عصير برتقال x1     8.00\n")
p.text("   (مثلج)\n")

p.text("=" * 32 + "\n")
p.text("Subtotal:            21.00\n")
p.text("Discount:            -1.00\n")
p.text("-" * 32 + "\n")
p.set(bold=True)
p.text("TOTAL:               20.00\n")
p.set(bold=False)
p.text("=" * 32 + "\n")

p.set(align='center')
p.text("\nشكراً لزيارتكم\n")
p.text("Thank you!\n")
p.text("★ ★ ★\n")

p.text("\n\n\n")
p.cut()
p.close()

print("✅ Receipt printed! Check your printer!")
