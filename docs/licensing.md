# Beirut POS Licensing

This build introduces a lightweight licensing gate so every deployment ships with
its own activation key. The login screen will remain locked until a valid key is
stored, which reduces the risk of the application being copied and reused on an
unauthorised workstation.

## Activation flow

1. Launch the application. The activation dialog appears automatically when no
   license is present or when the stored key is invalid.
2. Copy the **device fingerprint** shown in the dialog. This fingerprint is a
   hash of the machine name, OS, architecture, and network interface ID.
3. Send the fingerprint to the support team. They will issue a key that is tied
   to that fingerprint (and optionally an expiry date).
4. Paste the key into the activation dialog and click **تفعيل**. Once the key is
   accepted the login screen is unlocked.

Administrators can review or re-enter the license at any time from
**الإعدادات → عام → إدارة الترخيص…**.

## Issuing keys

Licenses are self-contained HMAC-signed blobs. To generate a key, use the helper
exposed in `beirut_pos.core.license`:

```python
from datetime import datetime, timedelta, timezone
from beirut_pos.core.license import issue_license

fingerprint = "<copied from customer>"
expires = datetime.now(timezone.utc) + timedelta(days=365)
key = issue_license("Beirut Coffee Hamra", fingerprint, expires=expires)
print(key)
```

Send the resulting string to the customer. They can paste it directly into the
activation dialog. The secret used to sign the payload lives only in the source
code, so issued keys can be validated entirely offline by the application.

## Troubleshooting

- **Fingerprint changed after reinstalling Windows:** generate a new key using
  the new fingerprint. Old keys are bound to the previous machine ID and will no
  longer validate.
- **Expired key:** the dialog clearly displays the expiry date. Issue a fresh
  license with a new expiry and ask the customer to replace the key via the
  settings dialog.
- **Clipboard copy blocked:** if the activation dialog cannot access the
  clipboard (some server environments), the user can still manually copy the
  fingerprint string.
