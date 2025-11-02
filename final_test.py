import sys
sys.path.insert(0, '.')

from beirut_pos.services.printer import printer

print("🎉 Testing actual receipt printing...")

# Create test order
test_items = [
    {"name": "قهوة", "qty": 2, "unit_price": 500, "total_cents": 1000, "note": ""},
    {"name": "شاي", "qty": 1, "unit_price": 300, "total_cents": 300, "note": "سكر خفيف"},
    {"name": "عصير برتقال", "qty": 1, "unit_price": 800, "total_cents": 800, "note": "مثلج"},
]

# Print receipt
success = printer.print_cashier_receipt(
    table_code="A1",
    items=test_items,
    subtotal=2100,
    discount=100,
    total=2000,
    method="نقدي",
    cashier="أحمد"
)

print(f"✅ Receipt printed: {success}")
print("📄 Check your printer!")
