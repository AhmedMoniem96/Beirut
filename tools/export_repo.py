#!/usr/bin/env python3
"""Utility to export the Beirut POS codebase into a fresh Git repository."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

EXCLUDED_DEFAULT_ITEMS = {
    ".git",
    ".github",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    "venv",
    ".venv",
    "build",
    "dist",
}

ALLOWED_HIDDEN_ITEMS = {".env", ".gitignore"}


def discover_default_items(root: Path) -> list[str]:
    """Return the top-level files/folders that should be exported by default."""

    items: list[str] = []
    for entry in sorted(root.iterdir()):
        name = entry.name
        if name in EXCLUDED_DEFAULT_ITEMS:
            continue
        if name.startswith(".") and name not in ALLOWED_HIDDEN_ITEMS:
            continue
        items.append(name)
    return items


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy the current Beirut POS workspace into a new folder and initialise "
            "a Git repository with an initial commit containing every exported file."
        )
    )
    parser.add_argument(
        "destination",
        help="Directory that will contain the new repository. It will be created if needed.",
    )
    parser.add_argument(
        "--items",
        nargs="*",
        help=(
            "Specific top-level files or folders to copy. By default, everything except"
            " common build and cache directories is exported."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow exporting into a non-empty directory by clearing it first.",
    )
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="Skip initialising a Git repository in the destination.",
    )
    parser.add_argument(
        "--initial-branch",
        default="main",
        help="Name of the initial branch when creating the new Git repository.",
    )
    parser.add_argument(
        "--archive",
        help=(
            "Optional path (without extension) for creating an archive of the exported"
            " files. Use together with --archive-format."
        ),
    )
    parser.add_argument(
        "--archive-format",
        choices=("zip", "gztar", "tar"),
        default="zip",
        help="Archive format to use when --archive is supplied. Default: %(default)s.",
    )
    return parser.parse_args()


def ensure_clean_destination(dest: Path, force: bool) -> None:
    if dest.exists():
        if any(dest.iterdir()):
            if not force:
                raise SystemExit(
                    f"Destination {dest} is not empty. Pass --force to overwrite it."
                )
            for entry in dest.iterdir():
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
    else:
        dest.mkdir(parents=True, exist_ok=True)


def export_items(dest: Path, items: Iterable[str]) -> None:
    root = Path(__file__).resolve().parents[1]
    for item in items:
        source = root / item
        if not source.exists():
            print(f"Skipping missing item: {item}")
            continue
        target = dest / item
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def init_git_repo(dest: Path, branch_name: str) -> None:
    subprocess.run(["git", "init", "-b", branch_name], cwd=dest, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True)
    subprocess.run(
        [
            "git",
            "commit",
            "-m",
            "Initial import of Beirut POS features",
        ],
        cwd=dest,
        check=True,
    )


def create_archive(dest: Path, archive_base: Path, archive_format: str) -> Path:
    archive_base.parent.mkdir(parents=True, exist_ok=True)
    archive_file = shutil.make_archive(
        base_name=str(archive_base),
        format=archive_format,
        root_dir=dest,
    )
    return Path(archive_file)


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    items = args.items if args.items else discover_default_items(root)
    destination = Path(os.path.expanduser(args.destination)).resolve()
    ensure_clean_destination(destination, args.force)
    export_items(destination, items)
    if not args.no_git:
        init_git_repo(destination, args.initial_branch)
    archive_message = ""
    if args.archive:
        archive_base = Path(os.path.expanduser(args.archive)).resolve()
        archive_file = create_archive(destination, archive_base, args.archive_format)
        archive_message = f" Archive created at: {archive_file}."
    print(
        "Export complete. New repository is located at:"
        f" {destination}.{archive_message}"
    )


if __name__ == "__main__":
    main()
