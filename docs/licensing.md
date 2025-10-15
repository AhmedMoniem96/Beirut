# Beirut POS Activation Vouchers

Beirut POS now ships with simple voucher-based activation instead of the previous
hardware fingerprint system. A valid voucher must be entered once on each deployment
before the login screen becomes available.

## Operator experience

1. On first launch a dialog prompts for a voucher in the format
   `BEIRUT-XXXX-XXXX-XXXX-X`. The checksum is verified locally; hyphens and case are
   optional.
2. When the voucher is accepted the application stores only a salted hash plus the
   activation timestamp in the SQLite settings table. The raw code is never written to
   disk.
3. Administrators can review the status from **الإعدادات → عام → حالة التفعيل**. The
   same screen offers a **تعطيل** button which clears the stored hash so a different
   voucher can be applied (for example when transferring the license to another site).

## Generating vouchers

Vouchers are random 12-character payloads protected by a Luhn-36 checksum. The helper
script `tools/make_vouchers.py` produces ready-to-print batches:

```bash
python tools/make_vouchers.py 50 --output-dir vouchers
```

The command above writes `vouchers-YYYYMMDD-HHMM.txt` containing 50 unique codes. All
validation is offline: no secrets or network services are required when activating a
deployment.

## Upgrade notes

- Existing installations automatically wipe the old `license_*` settings and cached
  signature file on first run of the new build.
- Because vouchers are not device-bound, reimaging or upgrading the host machine does
  not require a new code unless the administrator explicitly deactivates the current
  voucher.
