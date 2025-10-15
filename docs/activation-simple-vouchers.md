# Simple Voucher Activation

Beirut POS now activates with single-use vouchers instead of hardware fingerprints.
Each voucher follows the format `BEIRUT-XXXX-XXXX-XXXX-X` where the last character is a
Luhn-36 checksum.

## How to activate

1. Launch Beirut POS. The voucher dialog appears before login if the system is not
   activated.
2. Enter the voucher code (hyphens and case are optional) and click **تفعيل**.
3. On success the dialog closes and the status is persisted. Only the first 16
   characters of a salted SHA-256 hash are stored alongside the activation timestamp
   and the final four characters of the voucher. The raw code is never written to disk.
4. Administrators can view the status (including the masked suffix and activation time)
   or deactivate the current voucher from **الإعدادات → عام → حالة التفعيل**.

## Generating vouchers

Run `python tools/make_vouchers.py 20` to generate 20 unique vouchers. The script writes
`vouchers-YYYYMMDD-HHMM.txt` containing ready-to-print codes.

## Deactivation

Press **تعطيل** in the settings dialog to clear the stored voucher. The app will prompt
for a new voucher on the next launch.

The settings window and voucher dialog both refresh automatically after activation or
deactivation so operators can immediately confirm the current status.
