# Production Readiness & Windows Packaging

This guide summarizes where the Beirut POS stands today, what still needs attention before calling it "production ready," and how to turn the project into a distributable Windows 10 executable.

## Production readiness checklist

| Area | Current status | Notes |
| --- | --- | --- |
| Application entry point | ✅ `beirut_pos.__main__` bootstraps the Qt app and applies the configured branding icon. | `python -m beirut_pos` runs the `main()` function defined in `beirut_pos/app.py`, so tools like PyInstaller can point at the module directly.【F:beirut_pos/__main__.py†L1-L5】【F:beirut_pos/app.py†L1-L32】 |
| Database | ⚠️ SQLite lives under `%ProgramData%\\BeirutPOS\\data` with WAL/full sync, but passwords remain plaintext. | The engine applies durability PRAGMAs, snapshots PlayStation sessions, and mirrors backups under `%ProgramData%\\BeirutPOS\\backup`. Harden auth before shipping builds.【F:beirut_pos/core/db.py†L1-L214】【F:beirut_pos/services/backup.py†L1-L120】 |
| Authentication | ⚠️ Duplicate usernames are prevented, but credentials are validated against plaintext rows. | Consider adding password hashing plus audit logging for login attempts before going live.【F:beirut_pos/core/auth.py†L1-L76】 |
| Branding assets | ✅ Logo/background paths and palette values are cached and sanitized, so the UI handles missing files gracefully. | The branding helper validates colors and only loads existing images, which helps avoid crashes during theming updates.【F:beirut_pos/ui/common/branding.py†L1-L132】 |
| Error handling | ⚠️ Top-level exceptions show a dialog but allow the process to continue. | For production you may want centralized logging/telemetry alongside the GUI message box shown by `_qt_excepthook()`.【F:beirut_pos/app.py†L1-L31】 |
| Testing & CI | ❌ Manual `compileall` check only. | Add automated unit/UI tests and run them in CI to catch regressions before shipping builds. |

### Recommended next steps before production

1. **Secure credentials** – Hash passwords (e.g., `bcrypt`) and add password reset auditing so leaked databases do not expose logins.【F:beirut_pos/core/db.py†L188-L217】【F:beirut_pos/core/auth.py†L1-L76】
2. **Automate backups** – Mirror `%ProgramData%\\BeirutPOS\\data` and the dated folders in `%ProgramData%\\BeirutPOS\\backup` so you always have 14 days of restore points.【F:beirut_pos/services/backup.py†L1-L120】
3. **Expand testing** – Introduce end-to-end printer tests and UI smoke tests to ensure the bar/cashier workflows keep working after updates.
4. **Centralize logging** – Persist unexpected exceptions raised in the Qt layer and emit audit entries for user-management operations.【F:beirut_pos/app.py†L1-L31】
5. **Harden updates** – Ship migrations for schema changes with versioning so cafés upgrading from older builds keep their historical data intact.【F:beirut_pos/core/db.py†L57-L118】

## Building a Windows 10 executable with PyInstaller

1. **Install tooling inside a Windows Python 3.12 environment**
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\activate
   pip install --upgrade pip
   pip install PyInstaller PyQt6
   ```
2. **Run PyInstaller against the module entry point**
   ```powershell
   pyinstaller -F -w -n BeirutPOS beirut_pos\__main__.py
   ```
   * `-F -w` creates a single-windowed executable.
   * The `--add-data` switches bundle the default database and ticket templates that the printers read.
3. **Ship user-configurable assets alongside the EXE**
   * Place your café logo/background in the same directory as the executable or embed them via additional `--add-data` paths so the branding helper can load them at runtime.【F:beirut_pos/ui/common/branding.py†L19-L75】
4. **First-run initialization**
   * Launching the generated `BeirutPOS.exe` creates `%ProgramData%\\BeirutPOS` on Windows (or `~/.beirut_pos` when developing on Linux) with seeded data, config, backup, and license folders.【F:beirut_pos/core/paths.py†L1-L44】【F:beirut_pos/core/db.py†L160-L214】
5. **Optional: create an installer**
   * Wrap the executable with tools like Inno Setup or MSIX if you need desktop shortcuts, auto-start entries, or automatic updates.

### Troubleshooting tips

* If the build fails to locate Qt plugins, add `--collect-all PyQt6` to the PyInstaller command.
* When printers do not appear, confirm their names are configured under **Settings → Printers** after the first launch and that the Windows account running the app has permission to print.
* Use `pyinstaller --noconfirm --clean ...` during repeat builds to avoid reusing stale caches.

With these steps, you can evaluate the remaining production gaps and deliver a Windows-friendly executable without modifying the core application code.

## Creating a clean repository build

When you want to hand off the latest feature set without this original Git history, run the
export helper from the project root:

```bash
python tools/export_repo.py C:\\path\\to\\BeirutPOS-Pro
```

The script copies the application sources and documentation (everything under the project
root except build artefacts such as virtual environments and caches) into the specified
directory and creates a fresh Git repository with an initial commit.  Use `--no-git` if you
only want the files, `--items` to limit which top-level folders are exported, or `--archive`
to generate a ZIP/TAR archive alongside the exported folder.
