#!/usr/bin/env python3
"""Forward + inverse tools for line-heating plans.

This script wraps the existing solver by generating a config for run_coupled_3d.py via run_anywhere.py.

Modes:
- Forward: plan -> curvature (uses `plan.lines` in the config).
- Inverse: target curvature -> plan (uses `planner` in the config).

Limitations (current solver interface):
- Uses global energy/speed and pass count shared by all lines.
- Per-line parameters can be added once the solver supports them.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from scipy.optimize import minimize

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_anywhere.py"
RESULTS_ROOT = REPO_ROOT / "results"

DEFAULT_EPS0_MODEL = {
    "C": 0.06,
    "a": 0.35,
    "b": 0.0,
    "p": 0.325,
    "delta": 0.02,
    "E_ref": 600.0,
    "V_ref": 6.0,
    "H_ref": 14.0,
    "k_energy": 0.43,
    "k_low": 0.88,
    "e_ref_pass": 800.0,
    "k_single": 0.33,
    "eta_low_single": 0.2,
    "e0_low_single": 600.0,
    "de_low_single": 180.0,
}

DEFAULT_TMAX_MAP = {
    "E_min": 600.0,
    "E_max": 1000.0,
    "T_min_C": 900.0,
    "T_max_C": 1100.0,
}


def energy_to_q0(E_in: float, v: float, r0: float) -> float:
    """Convert energy per unit length to peak Gaussian flux for the solver."""
    return 2.0 * float(E_in) * float(v) / (math.pi * float(r0) ** 2)


def _pass_factor(
    n_passes: float,
    delta: float,
    e_in: float,
    e_ref: float,
    k_energy: float,
    k_low: float,
    e_ref_pass: float,
) -> float:
    if float(n_passes) <= 1.0:
        return 1.0
    base = 1.0 + (float(n_passes) - 1.0) * float(delta)
    energy_ratio = max(0.0, float(e_in) / float(e_ref))
    energy_scale = 1.0 - float(k_energy) * max(0.0, energy_ratio - 1.0)
    low_ratio = max(0.0, float(e_in) / float(e_ref_pass))
    low_scale = 1.0 - float(k_low) * max(0.0, 1.0 - low_ratio)
    return base * max(0.0, energy_scale) * max(0.0, low_scale)


def _single_pass_energy_boost(n_passes: float, e_in: float, e_ref: float, k_single: float) -> float:
    if float(n_passes) > 1.0:
        return 1.0
    energy_ratio = max(0.0, float(e_in) / float(e_ref))
    return 1.0 + float(k_single) * max(0.0, energy_ratio - 1.0)


def _low_energy_single_pass_boost(
    n_passes: float,
    e_in: float,
    e0: float,
    delta_e: float,
    eta: float,
) -> float:
    if float(n_passes) > 1.0:
        return 1.0
    if float(delta_e) <= 0.0:
        return 1.0
    x = (float(e_in) - float(e0)) / float(delta_e)
    return 1.0 + float(eta) * math.exp(-(x * x))


def eps0_from_model(energy: float, velocity: float, thickness: float, passes: int, model: dict) -> float:
    cfg = {**DEFAULT_EPS0_MODEL, **(model or {})}
    base = (float(energy) / float(cfg["E_ref"])) ** float(cfg["a"])
    base *= (float(cfg["V_ref"]) / float(velocity)) ** float(cfg["b"])
    base *= (float(cfg["H_ref"]) / float(thickness)) ** float(cfg["p"])
    base *= _pass_factor(
        passes,
        cfg["delta"],
        energy,
        cfg["E_ref"],
        cfg["k_energy"],
        cfg["k_low"],
        cfg["e_ref_pass"],
    )
    base *= _single_pass_energy_boost(passes, energy, cfg["E_ref"], cfg["k_single"])
    base *= _low_energy_single_pass_boost(
        passes,
        energy,
        cfg["e0_low_single"],
        cfg["de_low_single"],
        cfg["eta_low_single"],
    )
    return float(cfg["C"]) * float(base)


def target_tmax_from_energy(energy: float, model: dict | None = None) -> float:
    cfg = {**DEFAULT_TMAX_MAP, **(model or {})}
    e_min = float(cfg["E_min"])
    e_max = float(cfg["E_max"])
    t_min = float(cfg["T_min_C"])
    t_max = float(cfg["T_max_C"])
    if e_max <= e_min:
        raise ValueError("Invalid target_Tmax_model: E_max must be greater than E_min")
    e_clamped = max(e_min, min(e_max, float(energy)))
    t_c = t_min + (e_clamped - e_min) * (t_max - t_min) / (e_max - e_min)
    return t_c + 273.15


@dataclass
class TargetProfile:
    y: np.ndarray
    w: np.ndarray


def load_target_profile(cfg: dict) -> TargetProfile:
    target = cfg["target"]
    ttype = target.get("type", "profile")
    if ttype == "profile":
        if "file" in target:
            data = np.loadtxt(target["file"], delimiter=",", skiprows=1)
            return TargetProfile(y=data[:, 0], w=data[:, 1])
        return TargetProfile(y=np.array(target["y_mm"], dtype=float), w=np.array(target["w_mm"], dtype=float))
    if ttype == "radius":
        Ly = float(cfg["plate"]["Ly"])
        R = float(target["radius_mm"])
        y = np.linspace(0.0, Ly, 81)
        y0 = Ly / 2.0
        w = (y - y0) ** 2 / (2.0 * R)
        w -= w.min()
        return TargetProfile(y=y, w=w)
    raise ValueError(f"Unsupported target type: {ttype}")


def read_output_profile(out_dir: Path) -> TargetProfile | None:
    candidates = list(out_dir.glob("*camber_width_profile*.csv"))
    if not candidates:
        return None
    data = np.loadtxt(candidates[0], delimiter=",", skiprows=1)
    return TargetProfile(y=data[:, 0], w=data[:, 1])


def read_summary_deflection(out_dir: Path, Ly: float) -> TargetProfile:
    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    w_min = float(summary["mechanics"]["w_min"])
    w_max = float(summary["mechanics"]["w_max"])
    w_amp = max(abs(w_min), abs(w_max))
    y = np.linspace(0.0, Ly, 81)
    w = w_amp * 4.0 * (y / Ly) * (1.0 - y / Ly)
    return TargetProfile(y=y, w=w)


def _resolve_output_root(cfg: dict) -> Path:
    out_root = Path(cfg["output"]["root"])
    if not out_root.is_absolute():
        out_root = REPO_ROOT / out_root
    return out_root


def build_solver_config(
    cfg: dict,
    y_lines: Iterable[float],
    energy: float,
    velocity: float,
    passes: int,
    *,
    report: bool,
    heat_lines: list[dict[str, float]] | None = None,
) -> dict:
    plate = cfg["plate"]
    solver = cfg["solver"]
    Ly = float(plate["Ly"])
    heat_y_list = [float(y) for y in y_lines]
    heat_y_list = [min(max(0.0, y), Ly) for y in heat_y_list]

    eps0_model = solver.get("eps0_model") or solver.get("eps0_model_params")
    eps0_value = solver.get("eps0")
    if eps0_model is not None:
        eps0_value = eps0_from_model(energy, velocity, float(plate["thickness"]), int(passes), eps0_model)

    target_tmax = solver.get("target_Tmax")
    if target_tmax in (None, "mapped", "auto") and bool(solver.get("target_Tmax_from_energy", False)):
        target_tmax = target_tmax_from_energy(energy, solver.get("target_Tmax_model"))

    sim_cfg = {
        "Lx": float(plate["Lx"]),
        "Ly": float(plate["Ly"]),
        "thickness": float(plate["thickness"]),
        "h": float(solver.get("h", 20.0)),
        "h_refine": float(solver.get("h_refine", 5.0)),
        "refine_band": float(solver.get("refine_band", 60.0)),
        "heat_y_list": heat_y_list,
        "heat_mode": str(solver.get("heat_mode", "sequential")),
        "pass_gap": float(solver.get("pass_gap", 0.0)),
        "pass_repeats": int(passes),
        "dt": float(solver.get("dt", 2.0)),
        "extra_time": float(solver.get("extra_time", 200.0)),
        "q0": energy_to_q0(energy, velocity, float(solver.get("r0", 7.0))),
        "target_Tmax": None if target_tmax is None else float(target_tmax),
        "target_Tmax_tol": float(solver.get("target_Tmax_tol", 20.0)) if target_tmax is not None else None,
        "target_Tmax_iters": int(solver.get("target_Tmax_iters", 3)) if target_tmax is not None else None,
        "r0": float(solver.get("r0", 7.0)),
        "gaussian_beta": float(solver.get("gaussian_beta", 3.0)),
        "velocity": float(velocity),
        "k": float(solver.get("k", 0.05)),
        "k_slope": float(solver.get("k_slope", 0.0)),
        "rho": float(solver.get("rho", 7.82e-6)),
        "cp": float(solver.get("cp", 460.0)),
        "cp_slope": float(solver.get("cp_slope", 0.0)),
        "h_conv": float(solver.get("h_conv", 5e-5)),
        "h_conv_top": float(solver.get("h_conv_top", solver.get("h_conv", 5e-5))),
        "h_conv_bottom": float(solver.get("h_conv_bottom", solver.get("h_conv", 5e-5))),
        "emissivity": float(solver.get("emissivity", 0.8)),
        "T_inf": float(solver.get("T_inf", 293.15)),
        "T_ref": float(solver.get("T_ref", 293.15)),
        "E": float(solver.get("E", 2.05e5)),
        "nu": float(solver.get("nu", 0.28)),
        "alpha": float(solver.get("alpha", 1.1e-5)),
        "bc": str(solver.get("bc", "centerline_fixed")),
        "use_inherent": bool(solver.get("use_inherent", True)),
        "eps0": 0.0 if eps0_value is None else float(eps0_value),
        "inh_sigma": float(solver.get("inh_sigma", 7.0)),
        "inh_zfrac": float(solver.get("inh_zfrac", 0.2)),
        "vtk_deform_scale": float(solver.get("vtk_deform_scale", 50.0)),
    }

    if heat_lines is not None:
        sim_cfg["heat_lines"] = heat_lines

    if target_tmax is None:
        sim_cfg.pop("target_Tmax", None)
        sim_cfg.pop("target_Tmax_tol", None)
        sim_cfg.pop("target_Tmax_iters", None)

    out_root = _resolve_output_root(cfg)
    runner_no_build = bool(cfg["output"].get("no_build", True))
    return {
        "out": str(out_root / cfg["output"]["run_tag"]),
        "runner": {
            "report_only": False,
            "no_build": runner_no_build,
            "no_report": not bool(report),
        },
        "simulation": sim_cfg,
    }


def simulate(
    cfg: dict,
    y_lines: Iterable[float],
    energy: float,
    velocity: float,
    passes: int,
    *,
    report: bool,
    heat_lines: list[dict[str, float]] | None = None,
) -> tuple[TargetProfile, Path]:
    out_root = _resolve_output_root(cfg).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    sim_cfg = build_solver_config(cfg, y_lines, energy, velocity, passes, report=report, heat_lines=heat_lines)
    run_tag = cfg["output"]["run_tag"]
    cfg_path = out_root / f"plan_{run_tag}.json"
    cfg_path.write_text(json.dumps(sim_cfg, indent=2), encoding="utf-8")

    if cfg["solver"].get("use_solver", True):
        venv_python = REPO_ROOT / ".venv_lineheating" / "bin" / "python"
        python_exec = venv_python if venv_python.exists() else Path(sys.executable)
        subprocess.check_call([
            str(python_exec),
            str(RUNNER),
            "--config",
            str(cfg_path),
        ])

    out_dir = Path(sim_cfg["out"]).resolve()
    profile = read_output_profile(out_dir)
    if profile is None:
        profile = read_summary_deflection(out_dir, float(cfg["plate"]["Ly"]))
    return profile, out_dir


def _append_log(cfg: dict, row: dict) -> None:
    log_path = cfg["output"].get("log_csv")
    if not log_path:
        return
    log_path = Path(log_path)
    if not log_path.is_absolute():
        log_path = REPO_ROOT / log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)
    header = not log_path.exists()
    with log_path.open("a", encoding="utf-8") as f:
        if header:
            f.write(",".join(row.keys()) + "\n")
        f.write(",".join(str(v) for v in row.values()) + "\n")


def misfit(sim: TargetProfile, target: TargetProfile) -> float:
    w_sim = np.interp(target.y, sim.y, sim.w)
    return float(np.mean((w_sim - target.w) ** 2))


def objective(x: np.ndarray, cfg: dict, target: TargetProfile) -> float:
    n_lines = int(cfg["planner"]["n_lines"])
    y_lines = x[:n_lines]
    energy = x[n_lines]
    velocity = x[n_lines + 1]
    passes = int(round(x[n_lines + 2]))

    sim, _ = simulate(cfg, y_lines, energy, velocity, passes, report=False)
    base = misfit(sim, target)

    penalty = 0.0
    passes = max(1, passes)
    penalty += 1e-3 * (passes - 1) ** 2
    penalty += 1e-6 * max(0.0, energy - 1100.0) ** 2
    total = base + penalty
    _append_log(
        cfg,
        {
            "y_lines": ";".join(f"{y:.3f}" for y in y_lines),
            "energy": float(energy),
            "velocity": float(velocity),
            "passes": int(max(1, passes)),
            "loss": float(total),
        },
    )
    return total


def plan(cfg: dict) -> dict:
    target = load_target_profile(cfg)
    planner = cfg["planner"]
    n_lines = int(planner["n_lines"])

    init = planner["initial"]
    x0 = list(init["y"]) + [init["E"], init["v"], init["passes"]]

    bounds_cfg = planner["bounds"]
    bounds = bounds_cfg["y"] + [bounds_cfg["E"], bounds_cfg["v"], bounds_cfg["passes"]]

    result = minimize(
        objective,
        np.array(x0, dtype=float),
        args=(cfg, target),
        bounds=bounds,
        method="Nelder-Mead",
        options={"maxiter": int(planner.get("maxiter", 30))},
    )

    x = result.x
    y_lines = x[:n_lines]
    energy = float(x[n_lines])
    velocity = float(x[n_lines + 1])
    passes = int(round(x[n_lines + 2]))

    if bool(cfg["output"].get("final_report", True)):
        simulate(cfg, y_lines, energy, velocity, passes, report=True)

    plan_data = {
        "plate": cfg["plate"],
        "lines": [
            {
                "y_mm": float(y),
                "x_start_mm": float(cfg["planner"].get("x_start_mm", 0.0)),
                "x_end_mm": float(cfg["planner"].get("x_end_mm", cfg["plate"]["Lx"])),
                "energy_J_mm": energy,
                "velocity_mm_s": velocity,
                "passes": max(1, passes),
                "sequence": str(cfg["planner"].get("sequence", "sequential")),
            }
            for y in y_lines
        ],
        "objective": float(result.fun),
        "success": bool(result.success),
        "message": result.message,
    }
    return plan_data


def _load_lines_from_plan(cfg: dict) -> list[dict]:
    if "plan" in cfg and isinstance(cfg["plan"], dict):
        return list(cfg["plan"].get("lines", []))
    if "lines" in cfg:
        return list(cfg["lines"])
    raise SystemExit("Forward mode requires a 'plan.lines' array in the config.")


def _extract_uniform_params(lines: list[dict]) -> tuple[float, float, int]:
    if not lines:
        raise SystemExit("Plan has no lines.")
    energy_vals = [float(ln.get("energy_J_mm", ln.get("E", 0.0))) for ln in lines]
    velocity_vals = [float(ln.get("velocity_mm_s", ln.get("v", 0.0))) for ln in lines]
    passes_vals = [int(round(float(ln.get("passes", ln.get("N", 1))))) for ln in lines]

    e0 = energy_vals[0]
    v0 = velocity_vals[0]
    n0 = passes_vals[0]
    if not all(math.isclose(e, e0, rel_tol=1e-6, abs_tol=1e-6) for e in energy_vals):
        raise SystemExit("Solver only supports a single energy value across lines (per-line energy not yet supported).")
    if not all(math.isclose(v, v0, rel_tol=1e-6, abs_tol=1e-6) for v in velocity_vals):
        raise SystemExit("Solver only supports a single velocity value across lines (per-line velocity not yet supported).")
    if not all(n == n0 for n in passes_vals):
        raise SystemExit("Solver only supports a single pass count across lines (per-line passes not yet supported).")
    if e0 <= 0.0:
        raise SystemExit("Line energy must be positive (energy_J_mm).")
    if v0 <= 0.0:
        raise SystemExit("Line velocity must be positive (velocity_mm_s).")
    if n0 < 1:
        raise SystemExit("Pass count must be >= 1.")
    return e0, v0, n0


def _plan_lines_to_heat_lines(lines: list[dict]) -> list[dict[str, float]]:
    heat_lines: list[dict[str, float]] = []
    for ln in lines:
        if all(k in ln for k in ("x0", "y0", "x1", "y1")):
            heat_lines.append({
                "x0": float(ln["x0"]),
                "y0": float(ln["y0"]),
                "x1": float(ln["x1"]),
                "y1": float(ln["y1"]),
            })
        elif all(k in ln for k in ("x_start_mm", "x_end_mm", "y_mm")):
            y = float(ln["y_mm"])
            heat_lines.append({
                "x0": float(ln["x_start_mm"]),
                "y0": y,
                "x1": float(ln["x_end_mm"]),
                "y1": y,
            })
        else:
            raise SystemExit("Plan line must include x0/y0/x1/y1 or x_start_mm/x_end_mm/y_mm")
    return heat_lines


def run_forward(cfg: dict) -> dict:
    plate = cfg["plate"]
    lines = _load_lines_from_plan(cfg)
    energy, velocity, passes = _extract_uniform_params(lines)
    heat_lines = _plan_lines_to_heat_lines(lines)
    y_lines = [float(ln["y0"]) for ln in heat_lines if abs(float(ln["y0"]) - float(ln["y1"])) < 1e-9]

    profile, out_dir = simulate(
        cfg,
        y_lines,
        energy,
        velocity,
        passes,
        report=bool(cfg["output"].get("final_report", True)),
        heat_lines=heat_lines,
    )

    summary_path = out_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}

    return {
        "plate": plate,
        "lines": lines,
        "out_dir": str(out_dir),
        "summary": summary,
        "camber_profile": {
            "y_mm": profile.y.tolist(),
            "w_mm": profile.w.tolist(),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to planning config JSON.")
    parser.add_argument("--output", help="Override output plan JSON path.")
    args = parser.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out_root = _resolve_output_root(cfg)
    out_path = Path(args.output) if args.output else out_root / "plan.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if "planner" in cfg:
        plan_data = plan(cfg)
        out_path.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")
        return

    if "plan" in cfg or "lines" in cfg:
        forward_data = run_forward(cfg)
        out_path.write_text(json.dumps(forward_data, indent=2), encoding="utf-8")
        return

    raise SystemExit("Config must contain either 'planner' (inverse) or 'plan' (forward).")


if __name__ == "__main__":
    main()
