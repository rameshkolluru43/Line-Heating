#!/usr/bin/env python3
"""
Iterative optimization loop to match IGES target curvature.

Adjusts inherent strain (eps0) and heat input (q0) using a bounded
proportional update until transverse curvature matches target.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def run_simulation(result_dir: Path, params: dict) -> None:
    result_dir.mkdir(parents=True, exist_ok=True)
    log_file = result_dir / "run.log"
    pid_file = result_dir / "simulation.pid"

    cmd = [
        sys.executable,
        str(REPO_ROOT / "thermo_fem" / "python" / "run_coupled_3d.py"),
        "--Lx", str(params["Lx"]),
        "--Ly", str(params["Ly"]),
        "--thickness", str(params["thickness"]),
        "--h", str(params["h"]),
        "--h-refine", str(params["h_refine"]),
        "--refine-band", str(params["refine_band"]),
        "--q0", str(params["q0"]),
        "--r0", str(params["r0"]),
        "--velocity", str(params["velocity"]),
        "--T-inf", str(params["T_inf"]),
        "--h-conv", str(params["h_conv"]),
        "--dt", str(params["dt"]),
        "--extra-time", str(params["extra_time"]),
        "--heat-mode", "simultaneous",
        "--pass-repeats", str(params["pass_repeats"]),
        "--pass-gap", str(params["pass_gap"]),
        "--heat-y-list", params["heat_y_list"],
        "--bc", "centerline_fixed",
        "--use-inherent",
        "--eps0", str(params["eps0"]),
        "--inh-sigma", str(params["inh_sigma"]),
        "--out", str(result_dir)
    ]

    with open(log_file, "w") as log:
        proc = subprocess.Popen(
            cmd,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )

    pid_file.write_text(str(proc.pid))
    proc.wait()


def compare_curvature(result_dir: Path) -> dict:
    compare_script = Path(__file__).parent / "compare_curvature.py"
    subprocess.run(
        [sys.executable, str(compare_script), "--results-dir", str(result_dir)],
        check=True
    )
    comparison_file = result_dir / "curvature_comparison.json"
    return json.loads(comparison_file.read_text())


def main() -> None:
    base_result_dir = REPO_ROOT / "results" / "keel_plate_opt_loop"
    base_result_dir.mkdir(parents=True, exist_ok=True)

    # Base parameters (single pass, coarse mesh)
    Lx, Ly, thickness = 3000.0, 1000.0, 49.0
    num_lines = 5
    spacing = Ly / (num_lines + 1)
    heat_y_list = ",".join([f"{spacing * (i + 1):.2f}" for i in range(num_lines)])

    params = {
        "Lx": Lx,
        "Ly": Ly,
        "thickness": thickness,
        "h": 60.0,
        "h_refine": 30.0,
        "refine_band": 120.0,
        "q0": 12000.0,   # 1200 J/mm @ 10 mm/s
        "r0": 9.0,
        "velocity": 10.0,
        "T_inf": 20.0,
        "h_conv": 25.0,
        "dt": 3.0,
        "extra_time": 300.0,
        "pass_repeats": 1,
        "pass_gap": 0.0,
        "heat_y_list": heat_y_list,
        "eps0": 0.023,
        "inh_sigma": 40.0
    }

    target_tol = 0.05  # 5% curvature tolerance
    max_iters = 6

    history = []

    for i in range(1, max_iters + 1):
        result_dir = base_result_dir / f"iter_{i:02d}"
        print(f"\n=== Iteration {i} ===")
        print(f"q0={params['q0']:.2f}, eps0={params['eps0']:.5f}")

        run_simulation(result_dir, params)
        results = compare_curvature(result_dir)

        target_kappa = abs(results["iges_analysis"]["curvature_per_mm"])
        achieved_kappa = abs(results["simulation_results"]["kappa_transverse_per_mm"])
        if achieved_kappa == 0:
            raise RuntimeError("Achieved curvature is zero; check simulation outputs.")

        ratio = target_kappa / achieved_kappa
        history.append({
            "iteration": i,
            "q0": params["q0"],
            "eps0": params["eps0"],
            "target_kappa": target_kappa,
            "achieved_kappa": achieved_kappa,
            "ratio": ratio
        })

        print(f"Target kappa:   {target_kappa:.6e} 1/mm")
        print(f"Achieved kappa: {achieved_kappa:.6e} 1/mm")
        print(f"Ratio:          {ratio:.3f}")

        if abs(1.0 - ratio) <= target_tol:
            print("\nOK: Target curvature achieved within tolerance.")
            break

        # Bounded proportional update to stabilize convergence
        update = max(0.6, min(1.4, ratio))
        params["q0"] *= update
        params["eps0"] *= update

    # Save summary
    summary_file = base_result_dir / "optimization_history.json"
    summary_file.write_text(json.dumps(history, indent=2))
    print(f"\nSaved optimization history: {summary_file}")


if __name__ == "__main__":
    main()