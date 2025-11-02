with open('beirut_pos/services/printer.py', 'r') as f:
    content = f.read()

# Find and replace the CupsPrinter class
old_cups = '''class CupsPrinter:
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
        self._buffer = []'''

new_cups = '''class CupsPrinter:
    """Wrapper to use actual File printer via direct device access."""
    def __init__(self, device_path="/dev/usblp0"):
        from escpos.printer import File as EscposFile
        self.device_path = device_path
        self._printer = None
        self._find_device()
        
    def _find_device(self):
        """Find the actual printer device."""
        import glob
        import subprocess
        
        # Try to find via CUPS
        try:
            result = subprocess.run(['lpstat', '-v'], capture_output=True, text=True, timeout=2)
            for line in result.stdout.split('\\n'):
                if 'POS-80' in line and 'usb://' in line:
                    # Extract device - might give us a clue
                    _log(f"CUPS reports: {line}")
        except:
            pass
        
        # Look for usblp devices
        devices = glob.glob('/dev/usblp*')
        if devices:
            self.device_path = devices[0]
            _log(f"Found device: {self.device_path}")
        else:
            _log("⚠️ No /dev/usblp* found, will try /dev/usblp0")
            self.device_path = "/dev/usblp0"
    
    def open(self):
        """Open the actual printer device."""
        from escpos.printer import File as EscposFile
        try:
            self._printer = EscposFile(self.device_path)
            self._printer.open()
            _log(f"✅ Opened {self.device_path}")
        except Exception as e:
            _log_printer_error(f"Failed to open {self.device_path}", e)
            raise
        
    def close(self):
        if self._printer:
            try:
                self._printer.close()
            except:
                pass
        
    def hw(self, cmd):
        if self._printer:
            try:
                self._printer.hw(cmd)
            except:
                pass
        
    def text(self, txt):
        if self._printer:
            self._printer.text(txt)
        
    def cut(self):
        if self._printer:
            self._printer.cut()
    
    def set(self, **kwargs):
        if self._printer:
            try:
                self._printer.set(**kwargs)
            except:
                pass
    
    def _raw(self, data):
        if self._printer:
            self._printer._raw(data)
    
    @property
    def device(self):
        return self._printer.device if self._printer else None'''

if old_cups in content:
    content = content.replace(old_cups, new_cups)
    with open('beirut_pos/services/printer.py', 'w') as f:
        f.write(content)
    print("✅ Fixed CupsPrinter to use actual device")
    print("⚠️ RESTART APP!")
else:
    print("⚠️ Could not find CupsPrinter class to replace")
