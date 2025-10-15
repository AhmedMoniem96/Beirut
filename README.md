# Beirut POS (Café Edition)

This repository hosts a PyQt-based point-of-sale experience tailored for cafés and lounges.  
It combines the custom coffee workflow, dual-printer receipts, configurable branding, table
management, licensing, and hardened persistence that we iterated on across prior tasks.

## Highlights
- **Optimised core** – memory-thrifty models, a weak-reference event bus, cached branding assets,
  transactional order flow, and SQLite tuned for WAL/full sync to survive power failures.
- **Café-focused UX** – dynamic logo/background/theme controls, a redesigned login dashboard,
  inline toast notifications, barista tips, coffee customiser, duplicate-line folding in receipts,
  session timers, and keyboard shortcuts for the busiest screens.
- **Operations tooling** – table admin with drag-and-drop ordering, user creation with admin
  verification, voucher activation guard rails, rich multi-tab reports (cashier, product movers,
  low-stock alerts, price history), and ProgramData-friendly backups with restore helpers.

## Storage layout
- **Windows deployments** persist everything under `%ProgramData%\BeirutPOS`:
  - `data\beirut_pos.db` → live SQLite database.
  - `config\settings.json` → JSON config/PRAGMA overrides.
  - `backup\YYYY-MM-DD\beirut_pos.db` → rolling 14-day backups.
  - Voucher activations are stored as hashed entries inside the SQLite `settings` table.
- **Linux/macOS development** can override the root with `BEIRUTPOS_DATA_DIR`; otherwise files live under `~/.beirut_pos`.

## Exporting into a fresh repository
Need a clean repo that only contains the final feature set?  Run the helper script:

```bash
python tools/export_repo.py ../BeirutPOS-Pro
```

By default this copies every top-level file and folder except build artefacts (for example
`venv/` or cache directories) into the requested folder and initialises a new Git repository
on the `main` branch.  Use `--force` to export into a non-empty directory (the contents will
be replaced), customise the exported items via `--items`, or pass `--no-git` when you only
need the files without a new repo.  Add `--archive ../BeirutPOS-Pro-archive` to produce a
ZIP (or `--archive-format gztar` for a `.tar.gz`) alongside the exported folder.

## Documentation & packaging
- [Activation & XP-58 printing guide](docs/activation-and-printing.md)
- [Simple voucher activation](docs/activation-simple-vouchers.md)
- [Catalog & order screen updates](docs/catalog-and-order-screen.md)
- [Production hardening & Windows executable notes](docs/production_and_windows.md)

Refer to those documents for deployment, licensing, printing, and packaging guidance.
