"""Parameter sweep / dataset generator for 3D coupled line-heating runs.

Runs multiple cases by invoking run_coupled_3d.py as a subprocess.
This keeps the dataset logic isolated and avoids tight coupling.

Example:
  python3.11 run_param_sweep_3d.py --out dataset_runs \
    --q0 8 10 12 --velocity 8 10 --h 60 --h-refine 20 --refine-band 40

Outputs:
- Creates one folder per case under --out
- Writes a manifest CSV with parameters and key scalar outputs (min/max T, min/max w)

Note: Use python3.11 in this repo.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from itertools import product
import json
from pathlib import Path
import subprocess
import sys

import numpy as np


@dataclass(frozen=True)
class Case:
    q0: float
    velocity: float


@dataclass(frozen=True)
class CaseResult:
    T_min_final: float
    T_max_final: float
    T_max_global: float
    t_T_max_global: float
    x_source_T_max_global: float
    x_T_max_global: float
    y_T_max_global: float
    z_T_max_global: float
    w_min: float
    w_max: float
    x_w_min: float
    y_w_min: float
    z_w_min: float


def _read_case_result(case_dir: Path) -> CaseResult:
    summary_path = case_dir / "summary.json"
    if summary_path.exists():
        obj = json.loads(summary_path.read_text(encoding="utf-8"))
        th = obj.get("thermal", {})
        me = obj.get("mechanics", {})
        return CaseResult(
            T_min_final=float(th["T_min_final"]),
            T_max_final=float(th["T_max_final"]),
            T_max_global=float(th["T_max_global"]),
            t_T_max_global=float(th["t_at_T_max_global"]),
            x_source_T_max_global=float(th["x_source_at_T_max_global"]),
            x_T_max_global=float(th["x_at_T_max_global"]),
            y_T_max_global=float(th["y_at_T_max_global"]),
            z_T_max_global=float(th["z_at_T_max_global"]),
            w_min=float(me["w_min"]),
            w_max=float(me["w_max"]),
            x_w_min=float(me["x_w_min"]),
            y_w_min=float(me["y_w_min"]),
            z_w_min=float(me["z_w_min"]),
        )

    # Backwards-compatible fallback (older runs without summary.json)
    T = np.load(case_dir / "temperature.npy")
    u = np.load(case_dir / "displacement.npy")
    nodes = np.load(case_dir / "nodes.npy")
    w = -u[:, 2]
    idx_T = int(np.argmax(T))
    idx_w = int(np.argmin(w))
    xyzT = nodes[idx_T]
    xyzw = nodes[idx_w]
    return CaseResult(
        T_min_final=float(T.min()),
        T_max_final=float(T.max()),
        T_max_global=float(T.max()),
        t_T_max_global=float("nan"),
        x_source_T_max_global=float("nan"),
        x_T_max_global=float(xyzT[0]),
        y_T_max_global=float(xyzT[1]),
        z_T_max_global=float(xyzT[2]),
        w_min=float(w.min()),
        w_max=float(w.max()),
        x_w_min=float(xyzw[0]),
        y_w_min=float(xyzw[1]),
        z_w_min=float(xyzw[2]),
    )


def _run_case(script: Path, out_dir: Path, base_args: list[str], case: Case, case_dir_name: str | None = None) -> CaseResult:
    case_dir = out_dir / f"q0_{case.q0:g}_v_{case.velocity:g}"
    if case_dir_name is not None:
        case_dir = out_dir / case_dir_name
    case_dir.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, str(script)] + base_args + [
        "--q0",
        str(case.q0),
        "--velocity",
        str(case.velocity),
        "--out",
        str(case_dir),
    ]

    subprocess.run(cmd, check=True)

    return _read_case_result(case_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sweep q0/velocity and generate dataset")
    parser.add_argument("--out", type=str, default="dataset_runs", help="output root folder")

    # Base geometry/mesh
    parser.add_argument("--Lx", type=float, default=300.0)
    parser.add_argument("--Ly", type=float, default=200.0)
    parser.add_argument("--thickness", type=float, default=12.0)
    parser.add_argument("--h", type=float, default=45.0)
    parser.add_argument("--h-refine", type=float, default=15.0)
    parser.add_argument("--refine-band", type=float, default=35.0)

    # Thermal time controls
    parser.add_argument("--dt", type=float, default=1.0)
    parser.add_argument("--extra-time", type=float, default=10.0)

    # Material/BCs
    parser.add_argument("--k", type=float, default=0.045)
    parser.add_argument("--k-slope", type=float, default=0.0)
    parser.add_argument("--rho", type=float, default=7.85e-6)
    parser.add_argument("--cp", type=float, default=500.0)
    parser.add_argument("--cp-slope", type=float, default=0.0)
    parser.add_argument("--h-conv", type=float, default=5e-5)
    parser.add_argument("--emissivity", type=float, default=0.0)
    parser.add_argument("--picard", type=int, default=1)
    parser.add_argument("--T-inf", type=float, default=293.0)
    parser.add_argument("--T-ref", type=float, default=293.0)

    # Mechanics
    parser.add_argument("--E", type=float, default=210e3)
    parser.add_argument("--nu", type=float, default=0.3)
    parser.add_argument("--alpha", type=float, default=1.2e-5)

    # Optional inherent mode
    parser.add_argument("--use-inherent", action="store_true")
    parser.add_argument("--eps0", type=float, default=0.0)
    parser.add_argument("--inh-sigma", type=float, default=20.0)
    parser.add_argument("--inh-zfrac", type=float, default=0.5)

    # Sweep lists
    parser.add_argument("--q0", type=float, nargs="+", required=True, help="list of q0 values")
    parser.add_argument("--velocity", type=float, nargs="+", required=True, help="list of velocity values")

    # Optional baseline (for delta columns)
    parser.add_argument("--baseline-q0", type=float, default=None, help="optional baseline q0")
    parser.add_argument("--baseline-velocity", type=float, default=None, help="optional baseline velocity")

    args = parser.parse_args()

    out_root = Path(args.out)
    out_root.mkdir(parents=True, exist_ok=True)

    script = Path(__file__).parent / "run_coupled_3d.py"

    base_args = [
        "--Lx",
        str(args.Lx),
        "--Ly",
        str(args.Ly),
        "--thickness",
        str(args.thickness),
        "--h",
        str(args.h),
        "--h-refine",
        str(args.h_refine),
        "--refine-band",
        str(args.refine_band),
        "--dt",
        str(args.dt),
        "--extra-time",
        str(args.extra_time),
        "--k",
        str(args.k),
        "--k-slope",
        str(args.k_slope),
        "--rho",
        str(args.rho),
        "--cp",
        str(args.cp),
        "--cp-slope",
        str(args.cp_slope),
        "--h-conv",
        str(args.h_conv),
        "--emissivity",
        str(args.emissivity),
        "--picard",
        str(args.picard),
        "--T-inf",
        str(args.T_inf),
        "--T-ref",
        str(args.T_ref),
        "--E",
        str(args.E),
        "--nu",
        str(args.nu),
        "--alpha",
        str(args.alpha),
    ]

    if args.use_inherent:
        base_args += [
            "--use-inherent",
            "--eps0",
            str(args.eps0),
            "--inh-sigma",
            str(args.inh_sigma),
            "--inh-zfrac",
            str(args.inh_zfrac),
        ]

    baseline_result: CaseResult | None = None
    if args.baseline_q0 is not None and args.baseline_velocity is not None:
        baseline_case = Case(q0=float(args.baseline_q0), velocity=float(args.baseline_velocity))
        baseline_result = _run_case(
            script,
            out_root,
            base_args,
            baseline_case,
            case_dir_name=f"baseline_q0_{baseline_case.q0:g}_v_{baseline_case.velocity:g}",
        )

    manifest_path = out_root / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        header = [
            "case_dir",
            "q0",
            "velocity",
            "T_min_final",
            "T_max_final",
            "T_max_global",
            "t_T_max_global",
            "x_source_T_max_global",
            "x_T_max_global",
            "y_T_max_global",
            "z_T_max_global",
            "w_min",
            "w_max",
            "x_w_min",
            "y_w_min",
            "z_w_min",
        ]
        if baseline_result is not None:
            header += [
                "dT_max_global",
                "dw_min",
            ]
        writer.writerow(header)

        for q0, v in product(args.q0, args.velocity):
            case = Case(q0=float(q0), velocity=float(v))
            res = _run_case(script, out_root, base_args, case)
            row = [
                f"q0_{case.q0:g}_v_{case.velocity:g}",
                case.q0,
                case.velocity,
                res.T_min_final,
                res.T_max_final,
                res.T_max_global,
                res.t_T_max_global,
                res.x_source_T_max_global,
                res.x_T_max_global,
                res.y_T_max_global,
                res.z_T_max_global,
                res.w_min,
                res.w_max,
                res.x_w_min,
                res.y_w_min,
                res.z_w_min,
            ]
            if baseline_result is not None:
                row += [
                    res.T_max_global - baseline_result.T_max_global,
                    res.w_min - baseline_result.w_min,
                ]
            writer.writerow(row)

    print(f"Wrote manifest: {manifest_path}")


if __name__ == "__main__":
    main()
