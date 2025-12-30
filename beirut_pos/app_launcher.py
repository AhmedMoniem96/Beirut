"""Application launcher for Beirut POS."""

from __future__ import annotations

import os
import sys


def run() -> None:
    mode = os.getenv("APP_MODE", "playstation").strip().lower()
    if mode == "playstation":
        from beirut_pos.apps.playstation.app import run as app_run
    elif mode == "jewelry":
        from beirut_pos.apps.jewelry.app import run as app_run
    else:
        raise SystemExit(f"Unsupported APP_MODE: {mode}")

    app_run()


if __name__ == "__main__":
    run()
