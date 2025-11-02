import sys
import traceback
sys.path.insert(0, '.')

from beirut_pos.services.printer import printer

print("🧪 Testing printer directly...")
p = printer._current_printer()

if p:
    print(f"✅ Printer found: {p}")
    print(f"   Type: {type(p)}")
    print(f"   Has text method: {hasattr(p, 'text')}")
    print(f"   Has hw method: {hasattr(p, 'hw')}")
    
    try:
        print("1️⃣ Trying hw INIT...")
        p.hw("INIT")
        print("   ✅ INIT successful")
    except Exception as e:
        print(f"   ⚠️ INIT failed: {e}")
        traceback.print_exc()
    
    try:
        print("2️⃣ Trying to send text...")
        p.text("Hello World\n")
        print("   ✅ Text sent")
    except Exception as e:
        print(f"   ❌ Text failed: {e}")
        traceback.print_exc()
    
    try:
        print("3️⃣ Trying newlines...")
        p.text("\n\n\n")
        print("   ✅ Newlines sent")
    except Exception as e:
        print(f"   ❌ Newlines failed: {e}")
    
    try:
        print("4️⃣ Trying cut...")
        p.cut()
        print("   ✅ Cut sent")
    except Exception as e:
        print(f"   ❌ Cut failed: {e}")
        traceback.print_exc()
    
    print("\n✅ All commands executed - check the printer!")
else:
    print("❌ No printer found")
