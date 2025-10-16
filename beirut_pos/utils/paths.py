from __future__ import annotations
import os, sys
from pathlib import Path

def resource_path(rel: str | os.PathLike) -> str:
    """
    Return an absolute path to `rel` that works both in dev and in a PyInstaller onefile EXE.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return str(Path(base) / rel)
    # dev mode: resolve from the repo root (folder where the main script is)
    return str((Path(sys.argv[0]).resolve().parent / rel).resolve())
