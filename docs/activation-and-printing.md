# Activation & XP-58 Printing Guide

This document explains how café operators can activate Beirut POS on a new machine and
set up the bundled thermal receipt workflow (including XP-58 drivers) once the
application is deployed.

## Activation workflow

1. Launch Beirut POS. When no valid license is stored, the activation dialog appears
   before the login window. The dialog lists the **device fingerprint**, which is a
   hash of the machine name, operating system, architecture, and primary network
   interface address.
2. Click **Copy fingerprint** (or manually select the text) and send it to the vendor.
3. The vendor issues a signed activation string using the helper exposed in
   `beirut_pos.core.license.issue_license()`. Keys may include an optional expiry.
4. Paste the activation string into the dialog and press **تفعيل**. On success the
   license is stored in both the SQLite database and a cache file under
   `C:\ProgramData\BeirutPOS\license\license.sig.json` so it survives reinstalls.
5. Administrators can revisit the license status from **الإعدادات → عام → إدارة
   الترخيص…**. The dialog allows replacing the key or copying the fingerprint again.

### Issuing vendor keys

```python
from datetime import datetime, timedelta, timezone
from beirut_pos.core.license import issue_license

fingerprint = "<copied from customer>"
expires = datetime.now(timezone.utc) + timedelta(days=365)
key = issue_license("Beirut Coffee Hamra", fingerprint, expires=expires)
print(key)
```

Send the resulting string to the customer. All verification happens locally inside the
POS client, so the secret used to sign keys must remain private to the vendor.

## XP-58 thermal printer setup

1. Install the XP-58 (or compatible 58 mm) Windows driver. The manufacturer provides a
   signed driver on their support site; Windows Update usually picks it up as "XP-58"
   or "XP-58C". Reboot the machine if prompted.
2. Open **Settings → Printers & scanners** and confirm the device appears. Rename the
   printer to something recognisable like `BeirutPOS Bar` or `BeirutPOS Cashier`.
3. Launch Beirut POS and head to **الإعدادات → الطباعة**. Select the printer name for
   each role. Leave the cashier printer blank to use the Windows default.
4. Receipts are rendered as PDFs using an embedded Unicode font so Arabic characters
   print correctly. The app saves the PDF under `receipts/` (ignored by Git) and then
   invokes `os.startfile(path, "print")` on Windows. Ensure the default PDF handler on
   the machine (Microsoft Edge, Adobe Reader, etc.) is allowed to print silently.
5. If print jobs queue but nothing comes out, open the Windows **Devices and Printers**
   panel, right-click the XP-58 device, choose **Printer properties**, and ensure
   "Enable bidirectional support" is unchecked. Some driver builds require this.
6. For darker text, open the printer preferences and raise the density/print darkness.

### Troubleshooting

- **Nothing prints after power failure:** Beirut POS commits the SQLite transaction
  before creating the PDF, so re-open the order and reprint—it will still be available.
- **Printer not listed in the combo boxes:** restart the application so it refreshes the
  installed printer list. Windows adds the device asynchronously after driver install.
- **Garbled Arabic characters:** verify the system’s default PDF viewer is used. Some
  third-party viewers ignore embedded fonts; switch the default handler back to Edge or
  Adobe Reader.

With activation completed and printers configured, daily café operations can resume with
confidence that licensing, receipts, and recovery safeguards are in place.
