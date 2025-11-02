with open('beirut_pos/services/printer.py', 'r') as f:
    content = f.read()

# Add a CUPS printer class right after the imports
cups_class = '''
# ---------------- CUPS Printer Wrapper ----------------
class CupsPrinter:
    """Wrapper to print via CUPS lp command."""
    def __init__(self, printer_name="POS-80"):
        self.printer_name = printer_name
        self.device = self  # Fake device for compatibility
        
    def open(self):
        pass  # CUPS doesn't need opening
        
    def close(self):
        pass
        
    def hw(self, cmd):
        pass  # Ignore hardware commands
        
    def text(self, txt):
        """Buffer text to print."""
        if not hasattr(self, '_buffer'):
            self._buffer = []
        self._buffer.append(txt)
        
    def cut(self):
        """Send buffered content to CUPS."""
        import subprocess, tempfile
        if not hasattr(self, '_buffer'):
            return
            
        content = ''.join(self._buffer)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
            
        try:
            subprocess.run(['lp', '-d', self.printer_name, temp_path], 
                         check=False, capture_output=True, timeout=5)
            _log(f"✅ Sent to CUPS printer {self.printer_name}")
        except Exception as e:
            _log_printer_error("CUPS print failed", e)
        finally:
            import os
            try:
                os.unlink(temp_path)
            except:
                pass
        self._buffer = []

'''

# Insert after the File/Usb imports
insert_point = "from ..core.paths import DATA_DIR"
if insert_point in content and "class CupsPrinter" not in content:
    content = content.replace(insert_point, insert_point + "\n" + cups_class)
    print("✅ Added CupsPrinter class")

# Update _find_xp80c_printer to return CupsPrinter
old_return = '''    _log("❌ No printer found")
    return None'''

new_return = '''    # Last resort: try CUPS
    _log("🔧 Falling back to CUPS backend...")
    try:
        import subprocess
        result = subprocess.run(['lpstat', '-p', 'POS-80'], 
                              capture_output=True, timeout=2)
        if result.returncode == 0:
            _log("✅ Using CUPS printer POS-80")
            return CupsPrinter("POS-80")
    except Exception as e:
        _log_printer_error("CUPS check failed", e)
    
    _log("❌ No printer found")
    return None'''

content = content.replace(old_return, new_return)

with open('beirut_pos/services/printer.py', 'w') as f:
    f.write(content)

print("✅ Added CUPS fallback")
print("⚠️  RESTART YOUR APP NOW!")
