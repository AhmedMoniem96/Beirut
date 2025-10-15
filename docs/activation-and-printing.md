# Activation & XP-58 Printing Guide

This document explains how café operators can activate Beirut POS on a new machine and
set up the bundled thermal receipt workflow (including XP-58 drivers) once the
application is deployed.

## Activation workflow

1. Launch Beirut POS. On first run, a voucher dialog appears before the login window.
   Enter the code supplied by the vendor in the format `BEIRUT-XXXX-XXXX-XXXX-X`.
2. Vouchers are case-insensitive and accept optional hyphens. The dialog validates the
   checksum locally and shows a confirmation message on success.
3. Once activated, the status is persisted in the SQLite database (only a hash of the
   voucher is stored). Administrators can revisit the status from **الإعدادات → عام →
   حالة التفعيل** and deactivate the current voucher if the license needs to move to
   a different site.

### Issuing vendor vouchers

Use the helper script `python tools/make_vouchers.py 50` to generate printable codes
for customers. The script writes `vouchers-YYYYMMDD-HHMM.txt` to the chosen output
folder. Each line already includes the checksum and formatting required by the dialog.
For more details see [activation-simple-vouchers](activation-simple-vouchers.md).

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
