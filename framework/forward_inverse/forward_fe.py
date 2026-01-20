"""Forward problem: run FE given heat inputs and read deflection summary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_TOPS = {"thermo_fem", "python_prototype", "scripts", "docs", "LiteratureDocs"}


def _normalize_out_dir(out_dir: Path) -> Path:
    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve()
    try:
        rel = out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except Exception:
        return out_dir
    if len(rel.parts) == 0:
        return out_dir
    top = rel.parts[0]
    if top in CODE_TOPS:
        return (REPO_ROOT / "results" / out_dir.name).resolve()
    return out_dir


def _default_out_from_config(config_path: Path) -> Path:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if isinstance(cfg, dict):
        out = cfg.get("out")
        if out:
            return _normalize_out_dir(Path(out))
    return _normalize_out_dir(REPO_ROOT / "results" / config_path.stem)


def _run_anywhere(config_path: Path, out_dir: Path, no_report: bool, no_build: bool) -> None:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_anywhere.py"),
        "--config",
        str(config_path),
        "--out",
        str(out_dir),
    ]
    if no_report:
        cmd.append("--no-report")
    if no_build:
        cmd.append("--no-build")
    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))


def _load_summary(out_dir: Path) -> dict:
    summary = out_dir / "summary.json"
    if not summary.exists():
        raise SystemExit(f"summary.json not found: {summary}")
    return json.loads(summary.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward FE run for line heating")
    parser.add_argument("--config", required=True, type=str, help="Path to JSON config")
    parser.add_argument("--out", type=str, default=None, help="Override output directory")
    parser.add_argument("--no-report", action="store_true", help="Skip LaTeX report")
    parser.add_argument("--no-build", action="store_true", help="Skip C++ extension rebuild")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        raise SystemExit(f"Config not found: {config_path}")

    out_dir = _normalize_out_dir(Path(args.out)) if args.out else _default_out_from_config(config_path)

    _run_anywhere(config_path, out_dir, args.no_report, args.no_build)

    summary = _load_summary(out_dir)
    mech = summary.get("mechanics", {})
    w_min = float(mech.get("w_min", 0.0))
    w_max = float(mech.get("w_max", 0.0))
    out = {
        "out_dir": str(out_dir),
        "w_min_mm": w_min,
        "w_max_mm": w_max,
        "w_max_abs_mm": max(abs(w_min), abs(w_max)),
        "camber_midspan_edge_to_edge_mm": float(mech.get("camber_midspan_edge_to_edge_mm", 0.0)),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
