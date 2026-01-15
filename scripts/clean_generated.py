#!/usr/bin/env python3
"""Clean generated artifacts (virtualenvs, simulation outputs, and reports).

Default behavior is a DRY RUN: it prints what it *would* delete.
Pass --apply to actually delete.

This script is intentionally conservative:
- Deletes only known/generated directories and files used by this repo's runners.
- Never deletes source code or user-edited config.

Examples:
  python3 scripts/clean_generated.py
  python3 scripts/clean_generated.py --apply
  python3 scripts/clean_generated.py --apply --include-build --include-caches
"""

from __future__ import annotations

import argparse
import glob
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Candidate:
    path: Path
    kind: str  # 'dir' or 'file'
    reason: str


def _repo_root() -> Path:
    # scripts/clean_generated.py -> repo root
    return Path(__file__).resolve().parents[1]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _expand_glob(root: Path, pattern: str) -> list[Path]:
    # Use glob.glob for ** patterns; return absolute Paths.
    matches = glob.glob(str(root / pattern), recursive=True)
    return [Path(m).resolve() for m in matches]


def _collect_candidates(
    root: Path,
    include_build: bool,
    include_caches: bool,
    include_latex_aux: bool,
) -> list[Candidate]:
    candidates: list[Candidate] = []

    # Virtual environments (created by users or scripts).
    for name in (".venv", ".venv_lineheating", ".venv311"):
        p = (root / name).resolve()
        if p.exists():
            candidates.append(Candidate(p, "dir", "virtualenv"))

    # Any other top-level .venv* folders.
    for p in _expand_glob(root, ".venv*"):
        if p.is_dir() and p.name.startswith(".venv"):
            candidates.append(Candidate(p, "dir", "virtualenv"))

    # Simulation outputs: common patterns used in this repo.
    for pattern, reason in (
        ("results", "simulation results"),
        ("thermo_fem/python/outputs*", "simulation outputs"),
        ("thermo_fem/python/sweep_*", "parameter sweep outputs"),
        ("thermo_fem/outputs", "plots/figures outputs"),
        ("python_prototype/examples/outputs_*", "prototype outputs"),
    ):
        for p in _expand_glob(root, pattern):
            if p.exists() and p.is_dir():
                candidates.append(Candidate(p, "dir", reason))

    # Standalone run artifacts.
    for pattern, reason in (
        ("**/solution_manifest.json", "run manifest"),
    ):
        for p in _expand_glob(root, pattern):
            if p.exists() and p.is_file():
                candidates.append(Candidate(p, "file", reason))

    # Report artifacts outside output directories (prototype example).
    for p in _expand_glob(root, "python_prototype/examples/report.*"):
        if p.exists() and p.is_file():
            candidates.append(Candidate(p, "file", "prototype report artifact"))

    if include_build:
        for pattern, reason in (
            ("thermo_fem/build", "CMake build directory"),
            ("thermo_fem/cpp/build", "CMake build directory"),
        ):
            for p in _expand_glob(root, pattern):
                if p.exists() and p.is_dir():
                    candidates.append(Candidate(p, "dir", reason))

    if include_caches:
        for p in _expand_glob(root, "**/__pycache__"):
            if p.exists() and p.is_dir():
                candidates.append(Candidate(p, "dir", "python bytecode cache"))
        for p in _expand_glob(root, "**/*.pyc"):
            if p.exists() and p.is_file():
                candidates.append(Candidate(p, "file", "python bytecode cache"))

    if include_latex_aux:
        # Keep this narrow: only clean common LaTeX aux files we generate.
        for pattern in (
            "**/report.aux",
            "**/report.fls",
            "**/report.fdb_latexmk",
            "**/report.log",
            "**/report.synctex.gz",
            "inherent_strain_models.aux",
            "inherent_strain_models.log",
        ):
            for p in _expand_glob(root, pattern):
                if p.exists() and p.is_file():
                    candidates.append(Candidate(p, "file", "LaTeX build artifact"))

    # Deduplicate by resolved path.
    dedup: dict[Path, Candidate] = {}
    for c in candidates:
        if not _is_within(c.path, root):
            continue
        dedup[c.path] = c

    # Sort for stable output.
    return sorted(dedup.values(), key=lambda c: str(c.path))


def _delete_candidate(c: Candidate) -> None:
    if c.kind == "dir":
        shutil.rmtree(c.path)
    elif c.kind == "file":
        c.path.unlink(missing_ok=True)
    else:
        raise ValueError(f"Unknown candidate kind: {c.kind}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean generated artifacts.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually delete (default is dry-run).",
    )
    parser.add_argument(
        "--include-build",
        action="store_true",
        help="Also delete CMake build directories.",
    )
    parser.add_argument(
        "--include-caches",
        action="store_true",
        help="Also delete Python __pycache__ and *.pyc.",
    )
    parser.add_argument(
        "--include-latex-aux",
        action="store_true",
        help="Also delete LaTeX aux/log files (keeps PDFs).",
    )

    args = parser.parse_args()

    root = _repo_root()
    candidates = _collect_candidates(
        root=root,
        include_build=args.include_build,
        include_caches=args.include_caches,
        include_latex_aux=args.include_latex_aux,
    )

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"[{mode}] Repo: {root}")

    if not candidates:
        print(f"[{mode}] Nothing to clean.")
        return 0

    total_files = sum(1 for c in candidates if c.kind == "file")
    total_dirs = sum(1 for c in candidates if c.kind == "dir")
    print(f"[{mode}] Candidates: {total_dirs} dirs, {total_files} files")

    for c in candidates:
        rel = c.path.relative_to(root)
        print(f"- {c.kind}: {rel} ({c.reason})")

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to delete.")
        return 0

    # Safety belt: refuse to run if repo root looks wrong.
    if not (root / "thermo_fem").exists():
        print("Refusing to clean: repo root sanity-check failed (missing thermo_fem/).")
        return 2

    # Delete
    deleted = 0
    for c in candidates:
        try:
            _delete_candidate(c)
            deleted += 1
        except Exception as exc:
            rel = c.path.relative_to(root)
            print(f"ERROR deleting {rel}: {exc}")

    print(f"\n[APPLY] Deleted {deleted}/{len(candidates)} items.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
