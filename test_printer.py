import sys
sys.path.insert(0, '.')

from beirut_pos.services.printer import printer

print("🧪 Running test print...")
result = printer.test_print()
print(f"✅ Test completed: {result}")
