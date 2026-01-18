"""Application launcher for Beirut POS."""

from __future__ import annotations

import os
import sys


def _infer_mode_from_executable() -> str | None:
    executable_name = os.path.basename(sys.argv[0]).lower()
    if "jewelry" in executable_name:
        return "jewelry"
    if "playstation" in executable_name:
        return "playstation"
    return None


def run() -> None:
    raw_mode = os.getenv("APP_MODE")
    if raw_mode is None:
        raw_mode = _infer_mode_from_executable()
    if raw_mode is None:
        raise SystemExit("APP_MODE must be set to 'playstation' or 'jewelry'.")

    mode = raw_mode.strip().lower()
    if mode == "playstation":
        from beirut_pos.apps.playstation.app import run as app_run
    elif mode == "jewelry":
        from beirut_pos.apps.jewelry.app import run as app_run
    else:
        raise SystemExit(f"Unsupported APP_MODE: {mode}")

    app_run()


if __name__ == "__main__":
    run()
