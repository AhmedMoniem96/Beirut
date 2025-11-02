import sys

# Read the current printer.py
with open('beirut_pos/services/printer.py', 'r') as f:
    content = f.read()

# Check if test_print already exists
if 'def test_print(self)' in content:
    print("test_print method already exists!")
    sys.exit(0)

# Find where to insert the test_print method (after __init__)
insert_pos = content.find('    def update_printers(self')

if insert_pos == -1:
    print("Could not find insertion point!")
    sys.exit(1)

test_method = '''    def test_print(self) -> bool:
        """Print a simple test page to verify printer is working."""
        _log("🧪 Starting test print...")
        printer = self._current_printer()
        if not printer:
            _log("❌ No printer available for test")
            return False
        
        try:
            # Initialize printer
            printer.hw("INIT")
            
            # Set codepage for Arabic (if needed)
            try:
                printer.charcode("CP1256")
            except:
                pass
            
            # Simple test using text() method
            printer.text("=" * 32 + "\\n")
            printer.text("  PRINTER TEST\\n")
            printer.text("  اختبار الطابعة\\n")
            printer.text("=" * 32 + "\\n")
            printer.text("ASCII: Hello World 123\\n")
            printer.text("Arabic: مرحبا\\n")
            printer.text("Numbers: 0123456789\\n")
            printer.text("=" * 32 + "\\n")
            printer.text("\\n\\n\\n")
            printer.cut()
            
            _log("✅ Test print completed")
            return True
        except Exception as exc:
            _log_printer_error("Test print failed", exc)
            return False

'''

# Insert the method
new_content = content[:insert_pos] + test_method + '\n' + content[insert_pos:]

# Write back
with open('beirut_pos/services/printer.py', 'w') as f:
    f.write(new_content)

print("✅ test_print method added successfully!")
