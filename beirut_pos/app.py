"""Backward-compatible application entrypoint.

Historically deployment tooling imported ``beirut_pos.app``.
The runtime launcher now lives in :mod:`beirut_pos.app_launcher`,
so this module keeps the old import path working.
"""

from __future__ import annotations

from beirut_pos.app_launcher import run


def main() -> None:
    """Run the configured Beirut POS application."""
    run()


if __name__ == "__main__":
    main()
