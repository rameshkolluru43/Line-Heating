#!/usr/bin/env python3
"""Build a standalone executable for the line-heating runner.

Notes:
- Build on each target OS for a native executable.
- The executable expects the repository to be present. Run it from the repo root
  or set LINEHEATING_REPO to the repo directory.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str]) -> None:
    subprocess.check_call(cmd, cwd=str(REPO_ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build standalone executable (PyInstaller)")
    parser.add_argument("--name", default="lineheating", help="Executable name")
    parser.add_argument("--onefile", action="store_true", help="Create a single-file executable")
    parser.add_argument("--clean", action="store_true", help="Clean PyInstaller cache")
    args = parser.parse_args()

    entry = REPO_ROOT / "scripts" / "run_anywhere.py"
    if not entry.exists():
        raise SystemExit(f"Missing entrypoint: {entry}")

    py = sys.executable
    cmd = [py, "-m", "PyInstaller", "--noconfirm"]
    if args.clean:
        cmd.append("--clean")
    if args.onefile:
        cmd.append("--onefile")
    cmd += ["--name", args.name, str(entry)]

    print("[build_executable] Running:", " ".join(cmd))
    _run(cmd)

    dist_path = REPO_ROOT / "dist" / args.name
    if os.name == "nt":
        dist_path = dist_path.with_suffix(".exe")

    print(f"[build_executable] Done: {dist_path}")


if __name__ == "__main__":
    main()
