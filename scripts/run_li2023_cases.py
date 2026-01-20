#!/usr/bin/env python3
"""Run selected Li et al. (2023) cases and compare deflection.

This script uses the existing 3D solver with approximate material modeling:
- Thermal k(T), cp(T) are approximated by a linear slope fit to Table 1.
- Mechanics uses room-temperature E, nu, alpha (temperature dependence not modeled).

Outputs:
- results/li2023_case_<id>/ summary.json for each case
- results/li2023_comparison.csv summary table
"""
from __future__ import annotations

import csv
import json
import math
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_anywhere.py"
RESULTS_ROOT = REPO_ROOT / "results"

# Plate geometry from paper (mm)
Lx = 400.0
Ly = 300.0

# Heat source radius (mm) - initial estimate (tune 6-8 mm)
R0 = 7.0

# Convection + radiation (all surfaces)
H_CONV = 5e-5  # W/mm^2/K (~50 W/m^2/K)
EMISSIVITY = 0.8

# Mesh/time defaults for the small plate
MESH_H = 20.0
MESH_H_REFINE = 5.0
REFINE_BAND = 60.0
DT = 2.0
EXTRA_TIME = 200.0

# Q345 properties (Table 1)
# Convert k from W/mK to W/mmK by /1000
TABLE_T_C = [20, 250, 500, 750, 1000, 1500]
TABLE_K = [50, 47, 40, 27, 30, 45]
TABLE_CP = [460, 480, 530, 675, 670, 660]
TABLE_RHO = [7820, 7700, 7610, 7550, 7490, 7350]
TABLE_NU = [0.28, 0.29, 0.31, 0.35, 0.40, 0.49]
TABLE_ALPHA = [1.1e-5, 1.2e-5, 1.39e-5, 1.48e-5, 1.34e-5, 1.33e-5]
TABLE_E = [2.05e5, 1.87e5, 1.5e5, 0.7e5, 2e3, 1.5e3]

T_REF_C = 20.0
T_REF_K = T_REF_C + 273.15


def _linear_slope_fit(temps_c: list[float], values: list[float], ref_c: float, ref_val: float) -> float:
    """Fit slope s in v(T)=ref_val*(1+s*(T-ref)) via least squares."""
    xs = [(t + 273.15) - (ref_c + 273.15) for t in temps_c]
    ys = [(v / ref_val) - 1.0 for v in values]
    num = sum(x * y for x, y in zip(xs, ys))
    den = sum(x * x for x in xs)
    return 0.0 if den == 0 else num / den


K0 = TABLE_K[0] / 1000.0  # W/mmK
CP0 = TABLE_CP[0]
RHO0 = TABLE_RHO[0] * 1e-9  # kg/mm^3
NU0 = TABLE_NU[0]
ALPHA0 = TABLE_ALPHA[0]
E0 = TABLE_E[0]

K_SLOPE = _linear_slope_fit(TABLE_T_C, [k / 1000.0 for k in TABLE_K], T_REF_C, K0)
CP_SLOPE = _linear_slope_fit(TABLE_T_C, TABLE_CP, T_REF_C, CP0)

# Selected cases from Table 2 (id, v, Ein, h, N_heats, w_exp)
CASES = [
    (1, 6.0, 600.0, 14.0, 1, 5.785),
    (6, 11.0, 600.0, 14.0, 2, 7.712),
    (87, 12.0, 1000.0, 10.0, 2, 13.506),
    (90, 15.0, 1000.0, 10.0, 1, 11.322),
]

# Run other three cases (exclude anchor case 6) for this iteration.
CASE_FILTER = {1, 6, 87, 90}

# Tag to avoid overwriting previous runs.
RUN_TAG = "final_calibrated"

# Inherent strain band settings (mm)
INH_SIGMA = 7.0
INH_ZFRAC = 0.2

# Reference values for inherent-strain scaling law
E_REF = 600.0
V_REF = 6.0
H_REF = 14.0
EPS0_REF = 0.01

# Fixed eps0 law parameters for this iteration
EPS0_A = 0.35
EPS0_B = 0.0
EPS0_P = 0.325
EPS0_DELTA = 0.02
EPS0_PASS_ENERGY_K = 0.43
EPS0_PASS_ENERGY_LOW_K = 0.88
EPS0_PASS_E_REF = 800.0
EPS0_SINGLE_PASS_K = 0.33
EPS0_LOW_SINGLE_ETA = 0.2
EPS0_LOW_SINGLE_E0 = 600.0
EPS0_LOW_SINGLE_DE = 180.0
EPS0_C = 0.060
USE_FIXED_ONLY = True


def energy_to_q0(E_in: float, v: float, r0: float) -> float:
    """Convert energy per unit length to peak flux for this solver's Gaussian model.

    Our Gaussian: q(r) = q0 * exp(-2 r^2 / r0^2)
    Total power = q0 * pi * r0^2 / 2
    Power = E_in * v
    => q0 = 2 * E_in * v / (pi * r0^2)
    """
    return 2.0 * float(E_in) * float(v) / (math.pi * float(r0) ** 2)


def target_peak_k_from_energy(E_in: float) -> float:
    """Map energy input to a target peak temperature in K (900–1100 C range)."""
    e_clamped = max(600.0, min(1000.0, float(E_in)))
    t_c = 900.0 + (e_clamped - 600.0) * (200.0 / 400.0)
    return t_c + 273.15


def run_case(case_id: int, v: float, e_in: float, h: float, n_heats: int, eps0: float | None) -> Path:
    suffix = f"_{RUN_TAG}" if RUN_TAG else ""
    out_dir = RESULTS_ROOT / f"li2023_case_{case_id:03d}{suffix}"
    q0 = energy_to_q0(e_in, v, R0)

    target_peak_k = target_peak_k_from_energy(e_in)

    sim_cfg = {
        "Lx": Lx,
        "Ly": Ly,
        "thickness": h,
        "h": MESH_H,
        "h_refine": MESH_H_REFINE,
        "refine_band": REFINE_BAND,
        "heat_y_list": [Ly / 2.0],
        "heat_mode": "sequential",
        "pass_gap": 0,
        "pass_repeats": n_heats,
        "dt": DT,
        "extra_time": EXTRA_TIME,
        "q0": q0,
        "target_Tmax": target_peak_k,
        "target_Tmax_tol": 20.0,
        "target_Tmax_iters": 3,
        "r0": R0,
        "gaussian_beta": 3.0,
        "velocity": v,
        "k": K0,
        "k_slope": K_SLOPE,
        "rho": RHO0,
        "cp": CP0,
        "cp_slope": CP_SLOPE,
        "h_conv": H_CONV,
        "h_conv_top": H_CONV,
        "h_conv_bottom": H_CONV,
        "emissivity": EMISSIVITY,
        "T_inf": T_REF_K,
        "T_ref": T_REF_K,
        "E": E0,
        "nu": NU0,
        "alpha": ALPHA0,
        "E_table": "20:205000,250:187000,500:150000,750:70000,1000:2000,1500:1500",
        "nu_table": "20:0.28,250:0.29,500:0.31,750:0.35,1000:0.40,1500:0.49",
        "alpha_table": "20:1.1e-5,250:1.2e-5,500:1.39e-5,750:1.48e-5,1000:1.34e-5,1500:1.33e-5",
        "bc": "centerline_fixed",
        "use_inherent": bool(eps0 is not None and eps0 > 0.0),
        "eps0": 0.0 if eps0 is None else float(eps0),
        "inh_sigma": float(INH_SIGMA),
        "inh_zfrac": float(INH_ZFRAC),
        "vtk_deform_scale": 50,
    }

    config = {
        "out": str(out_dir),
        "runner": {"report_only": False, "no_build": False, "no_report": False},
        "simulation": sim_cfg,
    }

    cfg_path = RESULTS_ROOT / f"li2023_case_{case_id:03d}{suffix}.json"
    cfg_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    subprocess.check_call([str(Path.cwd() / ".venv_lineheating" / "bin" / "python"), str(RUNNER), "--config", str(cfg_path)])
    return out_dir


def read_predicted_deflection(out_dir: Path) -> float:
    summary_path = out_dir / "summary.json"
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    w_min = float(data["mechanics"]["w_min"])
    w_max = float(data["mechanics"]["w_max"])
    return max(abs(w_min), abs(w_max))


def read_peak_temperature(out_dir: Path) -> float:
    data = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    return float(data["thermal"]["T_max_global"])


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


def fit_eps0_law(_: list[dict]) -> dict:
    """Use fixed eps0 parameters for this iteration."""
    return {
        "a": EPS0_A,
        "b": EPS0_B,
        "p": EPS0_P,
        "delta": EPS0_DELTA,
        "k_energy": EPS0_PASS_ENERGY_K,
        "k_low": EPS0_PASS_ENERGY_LOW_K,
        "e_ref_pass": EPS0_PASS_E_REF,
        "k_single": EPS0_SINGLE_PASS_K,
        "eta_low_single": EPS0_LOW_SINGLE_ETA,
        "e0_low_single": EPS0_LOW_SINGLE_E0,
        "de_low_single": EPS0_LOW_SINGLE_DE,
        "C": EPS0_C,
        "max_abs_pct": float("nan"),
        "rmse": float("nan"),
    }


def main() -> None:
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)

    if USE_FIXED_ONLY:
        fit = fit_eps0_law([])
        print(
            "[eps0-fixed]"
            f" C={fit['C']:.5f}, a={fit['a']}, b={fit['b']}, p={fit['p']}, delta={fit['delta']},"
            f" k_energy={fit['k_energy']}, k_low={fit['k_low']}, e_ref_pass={fit['e_ref_pass']},"
            f" k_single={fit['k_single']}, eta_low_single={fit['eta_low_single']},"
            f" e0_low_single={fit['e0_low_single']}, de_low_single={fit['de_low_single']}"
        )
        rows = []
        for case_id, v, e_in, h, n_heats, w_exp in CASES:
            if CASE_FILTER and case_id not in CASE_FILTER:
                continue
            base = (e_in / E_REF) ** fit["a"]
            base *= (V_REF / v) ** fit["b"]
            base *= (H_REF / h) ** fit["p"]
            base *= _pass_factor(
                n_heats,
                fit["delta"],
                e_in,
                E_REF,
                fit["k_energy"],
                fit["k_low"],
                fit["e_ref_pass"],
            )
            base *= _single_pass_energy_boost(n_heats, e_in, E_REF, fit["k_single"])
            base *= _low_energy_single_pass_boost(
                n_heats,
                e_in,
                fit["e0_low_single"],
                fit["de_low_single"],
                fit["eta_low_single"],
            )
            eps0_total = fit["C"] * base

            out_dir = run_case(case_id, v, e_in, h, n_heats, eps0_total)
            w_pred = read_predicted_deflection(out_dir)
            T_peak = read_peak_temperature(out_dir)
            rows.append({
                "case_id": case_id,
                "velocity_mm_s": v,
                "energy_J_mm": e_in,
                "thickness_mm": h,
                "passes": n_heats,
                "w_exp_mm": w_exp,
                "w_pred_mm": w_pred,
                "error_mm": w_pred - w_exp,
                "eps0": eps0_total,
                "T_peak_K": T_peak,
                "eps0_model": (
                    f"C={fit['C']:.4g},a={fit['a']},b={fit['b']},p={fit['p']},"
                    f"delta={fit['delta']},k_energy={fit['k_energy']},k_low={fit['k_low']},"
                    f"e_ref_pass={fit['e_ref_pass']},k_single={fit['k_single']},"
                    f"eta_low_single={fit['eta_low_single']},e0_low_single={fit['e0_low_single']},"
                    f"de_low_single={fit['de_low_single']}"
                ),
            })
    else:
        # Baseline runs with EPS0_REF to estimate linear scaling.
        baseline_rows = []
        for case_id, v, e_in, h, n_heats, w_exp in CASES:
            if CASE_FILTER and case_id not in CASE_FILTER:
                continue
            out_dir = run_case(case_id, v, e_in, h, n_heats, EPS0_REF)
            w_pred_ref = read_predicted_deflection(out_dir)
            T_peak = read_peak_temperature(out_dir)
            baseline_rows.append({
                "case_id": case_id,
                "velocity_mm_s": v,
                "energy_J_mm": e_in,
                "thickness_mm": h,
                "passes": n_heats,
                "w_exp_mm": w_exp,
                "w_pred_ref": w_pred_ref,
                "T_peak_K": T_peak,
            })

        fit = fit_eps0_law(baseline_rows)
        print(
            "[eps0-fit]"
            f" C={fit['C']:.5f}, a={fit['a']}, b={fit['b']}, p={fit['p']}, delta={fit['delta']},"
            f" k_energy={fit['k_energy']}, k_low={fit['k_low']}, e_ref_pass={fit['e_ref_pass']},"
            f" k_single={fit['k_single']}, eta_low_single={fit['eta_low_single']},"
            f" e0_low_single={fit['e0_low_single']}, de_low_single={fit['de_low_single']}"
        )

        rows = []
        for row in baseline_rows:
            base = (row["energy_J_mm"] / E_REF) ** fit["a"]
            base *= (V_REF / row["velocity_mm_s"]) ** fit["b"]
            base *= (H_REF / row["thickness_mm"]) ** fit["p"]
            base *= _pass_factor(
                row["passes"],
                fit["delta"],
                row["energy_J_mm"],
                E_REF,
                fit["k_energy"],
                fit["k_low"],
                fit["e_ref_pass"],
            )
            base *= _single_pass_energy_boost(row["passes"], row["energy_J_mm"], E_REF, fit["k_single"])
            base *= _low_energy_single_pass_boost(
                row["passes"],
                row["energy_J_mm"],
                fit["e0_low_single"],
                fit["de_low_single"],
                fit["eta_low_single"],
            )
            eps0_total = fit["C"] * base

            out_dir = run_case(
                row["case_id"],
                row["velocity_mm_s"],
                row["energy_J_mm"],
                row["thickness_mm"],
                row["passes"],
                eps0_total,
            )
            w_pred = read_predicted_deflection(out_dir)
            T_peak = read_peak_temperature(out_dir)
            rows.append({
                "case_id": row["case_id"],
                "velocity_mm_s": row["velocity_mm_s"],
                "energy_J_mm": row["energy_J_mm"],
                "thickness_mm": row["thickness_mm"],
                "passes": row["passes"],
                "w_exp_mm": row["w_exp_mm"],
                "w_pred_mm": w_pred,
                "error_mm": w_pred - row["w_exp_mm"],
                "eps0": eps0_total,
                "T_peak_K": T_peak,
                "eps0_model": (
                    f"C={fit['C']:.4g},a={fit['a']},b={fit['b']},p={fit['p']},"
                    f"delta={fit['delta']},k_energy={fit['k_energy']},k_low={fit['k_low']},"
                    f"e_ref_pass={fit['e_ref_pass']},k_single={fit['k_single']},"
                    f"eta_low_single={fit['eta_low_single']},e0_low_single={fit['e0_low_single']},"
                    f"de_low_single={fit['de_low_single']}"
                ),
            })

    suffix = f"_{RUN_TAG}" if RUN_TAG else ""
    out_csv = RESULTS_ROOT / f"li2023_comparison{suffix}.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "velocity_mm_s",
                "energy_J_mm",
                "thickness_mm",
                "passes",
                "w_exp_mm",
                "w_pred_mm",
                "error_mm",
                "eps0",
                "T_peak_K",
                "eps0_model",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
