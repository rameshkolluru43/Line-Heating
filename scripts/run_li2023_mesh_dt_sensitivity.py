#!/usr/bin/env python3
"""Run mesh/time-step sensitivity matrix for Li2023 Case 6 (representative).

Outputs:
  results/li2023_case_006_mesh_dt_sensitivity.csv
  results/li2023_case_006_mesh_dt_sensitivity.json
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RUNNER = REPO_ROOT / "scripts" / "run_anywhere.py"
BASELINE_SUMMARY = REPO_ROOT / "results" / "li2023_case_006_v9_table2_extended" / "summary.json"

MATRIX = [
    {
        "setting": "Baseline (paper setting)",
        "slug": "baseline",
        "h": 20.0,
        "h_refine": 5.0,
        "refine_band": 60.0,
        "dt": 2.0,
        "skip_if_exists": True,
        "reuse_dir": "li2023_case_006_v9_table2_extended",
    },
    {
        "setting": "Refined time step",
        "slug": "dt1",
        "h": 20.0,
        "h_refine": 5.0,
        "refine_band": 60.0,
        "dt": 1.0,
    },
    {
        "setting": "Refined mesh (band)",
        "slug": "mesh_refined",
        "h": 20.0,
        "h_refine": 2.5,
        "refine_band": 60.0,
        "dt": 2.0,
    },
    {
        "setting": "Refined mesh + time step",
        "slug": "mesh_refined_dt1",
        "h": 20.0,
        "h_refine": 2.5,
        "refine_band": 60.0,
        "dt": 1.0,
    },
]


def _baseline_sim() -> dict:
    data = json.loads(BASELINE_SUMMARY.read_text(encoding="utf-8"))
    inp = data["inputs"]
    keep = [
        "Lx", "Ly", "thickness", "q0", "r0", "velocity", "heat_mode", "pass_gap",
        "target_Tmax", "k", "k_slope", "rho", "cp", "cp_slope", "h_conv",
        "h_conv_top", "h_conv_bottom", "gaussian_beta", "emissivity", "picard",
        "T_inf", "T_ref", "E_table", "nu_table", "alpha_table", "E", "nu", "alpha",
        "bc", "inh_sigma", "inh_zfrac", "eps0",
    ]
    sim = {k: inp[k] for k in keep if k in inp and inp[k] is not None}
    sim.update({
        "heat_y_list": [150.0],
        "pass_repeats": 2,
        "extra_time": 200.0,
        "target_Tmax_tol": 20.0,
        "target_Tmax_iters": 3,
        "use_inherent": True,
        "use_elastoplastic": False,
        "eps0": float(inp["eps0"]),
        "picard": int(float(inp.get("picard", 1))),
        "vtk_deform_scale": 50,
    })
    return sim


def _metrics_from_summary(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    m = d["mechanics"]
    t = d["thermal"]
    i = d["inputs"]
    w_max = max(abs(float(m["w_min"])), abs(float(m["w_max"])))
    return {
        "dt_s": float(i["dt"]),
        "h_mm": float(i["h"]),
        "h_refine_mm": float(i["h_refine"]),
        "refine_band_mm": float(i["refine_band"]),
        "n_nodes": None,
        "n_tets": None,
        "T_peak_K": float(t["T_max_global"]),
        "w_max_mm": w_max,
        "camber_midspan_mm": float(m.get("camber_midspan_edge_to_edge_mm", 0.0)),
    }


def main() -> None:
    if not BASELINE_SUMMARY.is_file():
        raise SystemExit(f"Missing baseline summary: {BASELINE_SUMMARY}")

    py = REPO_ROOT / ".venv_lineheating" / "bin" / "python"
    if not py.exists():
        py = Path(sys.executable)

    base_sim = _baseline_sim()
    rows: list[dict] = []

    for entry in MATRIX:
        setting = entry["setting"]
        slug = entry["slug"]
        out_name = entry.get("reuse_dir") or f"li2023_case_006_sensitivity_{slug}"
        out_dir = REPO_ROOT / "results" / out_name
        summary_path = out_dir / "summary.json"

        if entry.get("skip_if_exists") and summary_path.is_file():
            print(f"[skip] {setting}: reuse {summary_path}")
        else:
            sim = dict(base_sim)
            sim.update({
                "h": float(entry["h"]),
                "h_refine": float(entry["h_refine"]),
                "refine_band": float(entry["refine_band"]),
                "dt": float(entry["dt"]),
            })
            cfg_path = REPO_ROOT / "results" / f"li2023_case_006_sensitivity_{slug}.json"
            cfg = {
                "out": str(out_dir.relative_to(REPO_ROOT)),
                "runner": {"report_only": False, "no_build": True, "no_report": True},
                "simulation": sim,
            }
            cfg_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
            print(f"[run] {setting} -> {out_dir}")
            subprocess.check_call([str(py), str(RUNNER), "--config", str(cfg_path)], cwd=str(REPO_ROOT))

        met = _metrics_from_summary(summary_path)
        nodes = (out_dir / "nodes.npy")
        if nodes.is_file():
            import numpy as np
            n_nodes = int(np.load(nodes).shape[0])
            n_tets = int(np.load(out_dir / "tet.npy").shape[0])
            met["n_nodes"] = n_nodes
            met["n_tets"] = n_tets

        rows.append({
            "setting": setting,
            "slug": slug,
            "dt_s": met["dt_s"],
            "h_mm": met["h_mm"],
            "h_refine_mm": met["h_refine_mm"],
            "refine_band_mm": met["refine_band_mm"],
            "n_nodes": met.get("n_nodes"),
            "n_tets": met.get("n_tets"),
            "T_peak_K": round(met["T_peak_K"], 3),
            "w_max_mm": round(met["w_max_mm"], 4),
            "camber_midspan_mm": round(met["camber_midspan_mm"], 4),
            "summary": str(summary_path.relative_to(REPO_ROOT)),
        })

    out_csv = REPO_ROOT / "results" / "li2023_case_006_mesh_dt_sensitivity.csv"
    out_json = REPO_ROOT / "results" / "li2023_case_006_mesh_dt_sensitivity.json"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    out_json.write_text(json.dumps({"case_id": 6, "rows": rows}, indent=2), encoding="utf-8")
    print(f"Wrote {out_csv}")
    print(f"Wrote {out_json}")


if __name__ == "__main__":
    main()
