import sys
sys.path.insert(0, '.')

from escpos.printer import File

print("🧪 Testing with manual open...")

# Create printer and EXPLICITLY open it
p = File('/dev/usb/lp0')
print(f"1️⃣ Printer created: {p}")
print(f"   Device before open: {p.device}")

# Open the device
p.open()
print(f"✅ Device opened!")
print(f"   Device after open: {p.device}")

try:
    print("\n2️⃣ Sending text...")
    p.text("================================\n")
    p.text("  HELLO FROM PYTHON!\n")
    p.text("  مرحبا من بايثون\n")
    p.text("  123456789\n")
    p.text("================================\n")
    p.text("\n\n\n")
    print("✅ Text sent!")
    
    print("\n3️⃣ Cutting paper...")
    p.cut()
    print("✅ Cut command sent!")
    
    print("\n4️⃣ Closing printer...")
    p.close()
    print("✅ Printer closed!")
    
    print("\n" + "="*50)
    print("✅ SUCCESS! Check your printer!")
    print("="*50)
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
