import sys
sys.path.insert(0, '.')

# Test CUPS printing directly
import subprocess
import tempfile

content = """
================================
       CAFE BEIRUT
================================
Date: 2025-11-02
Table: T1
Cashier: Ahmed
--------------------------------
1. قهوة × 2           10.00
2. شاي × 1             5.00
================================
Total:                15.00
================================
شكراً لزيارتكم
Thank you!
"""

print("🧪 Testing CUPS print...")

# Write to temp file
with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
    f.write(content)
    temp_path = f.name

print(f"📄 Temp file: {temp_path}")

# Print via CUPS
result = subprocess.run(['lp', '-d', 'POS-80', temp_path], 
                       capture_output=True, text=True, timeout=5)

print(f"Return code: {result.returncode}")
print(f"STDOUT: {result.stdout}")
print(f"STDERR: {result.stderr}")

import os
os.unlink(temp_path)

print("\n✅ Check your printer!")
