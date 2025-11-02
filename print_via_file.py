"""Simple working printer that bypasses all the complexity."""
from escpos.printer import File

def print_receipt(lines):
    """Print receipt lines directly."""
    try:
        # Find the device
        import glob
        devices = glob.glob('/dev/usb/lp*')
        if not devices:
            # Stop CUPS temporarily
            import subprocess
            subprocess.run(['sudo', 'systemctl', 'stop', 'cups'], capture_output=True)
            import time
            time.sleep(2)
            devices = glob.glob('/dev/usb/lp*')
        
        if not devices:
            print("❌ No printer device found")
            return False
            
        device_path = devices[0]
        print(f"✅ Using {device_path}")
        
        p = File(device_path)
        p.open()
        p.hw("INIT")
        
        for line in lines:
            p.text(line + "\n")
        
        p.text("\n\n\n")
        p.cut()
        p.close()
        
        print("✅ Printed!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    test_lines = ["TEST PRINT", "Hello World", "مرحبا", "123"]
    print_receipt(test_lines)
