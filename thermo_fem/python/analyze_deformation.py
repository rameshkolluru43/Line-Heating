"""Quick sanity checks for deformation magnitudes.

Usage:
  python3.11 analyze_deformation.py <out_dir> [--vtk-scale 200]

Reads:
  nodes.npy, displacement.npy

Reports:
  - geometry extents inferred from the mesh
  - max displacements (actual, scale=1)
  - simple curvature estimate along x on top surface near each heat line (if present)
  - bounding box of the deformed VTK geometry if a scale is provided
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def _curvature_fit_x(nodes: np.ndarray, w: np.ndarray, y0: float, Ly: float, thickness: float) -> tuple[float, float, float, int]:
    tol_z = max(1e-9, thickness * 1e-3)
    top = nodes[:, 2] > nodes[:, 2].max() - tol_z
    band = max(Ly / 60.0, 15.0)
    m = top & (np.abs(nodes[:, 1] - y0) < band)
    x = nodes[m, 0]
    ww = w[m]
    n = int(x.size)
    if n < 30:
        return float("nan"), float("inf"), float("nan"), n

    x_mean = float(np.mean(x))
    xx = x - x_mean
    A = np.vstack([xx**2, xx, np.ones_like(xx)]).T
    coef, *_ = np.linalg.lstsq(A, ww, rcond=None)
    a = float(coef[0])
    k = 2.0 * a  # 1/mm (for small slopes)
    R = float("inf") if abs(k) < 1e-12 else 1.0 / abs(k)
    w_pred = A @ coef
    rmse = float(np.sqrt(np.mean((ww - w_pred) ** 2)))
    return k, R, rmse, n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=str)
    ap.add_argument("--vtk-scale", type=float, default=200.0, help="Scale used when writing deformed VTK geometry")
    args = ap.parse_args()

    out = Path(args.out_dir)
    nodes = np.load(out / "nodes.npy")
    disp = np.load(out / "displacement.npy")

    Lx = float(nodes[:, 0].max() - nodes[:, 0].min())
    Ly = float(nodes[:, 1].max() - nodes[:, 1].min())
    thickness = float(nodes[:, 2].max() - nodes[:, 2].min())

    ux, uy, uz = disp[:, 0], disp[:, 1], disp[:, 2]
    w = -uz

    print("--- Geometry (from mesh) ---")
    print(f"Lx_mm {Lx:.6g}  Ly_mm {Ly:.6g}  thickness_mm {thickness:.6g}")
    bbmin = nodes.min(axis=0)
    bbmax = nodes.max(axis=0)
    print("bbox_min_xyz", bbmin)
    print("bbox_max_xyz", bbmax)

    print("\n--- Displacements (actual, scale=1) ---")
    print(f"max_abs_ux_mm {float(np.max(np.abs(ux))):.6g}")
    print(f"max_abs_uy_mm {float(np.max(np.abs(uy))):.6g}")
    print(f"max_abs_uz_mm {float(np.max(np.abs(uz))):.6g}")
    print(f"w_min_mm {float(np.min(w)):.6g}  w_max_mm {float(np.max(w)):.6g}")
    print(f"max_abs_u_mm {float(np.max(np.linalg.norm(disp, axis=1))):.6g}")

    print("\n--- Rough curvature along x (top surface) ---")
    # Try to infer heat lines if summary.json exists
    heat_ys = [Ly / 2.0]
    summ = out / "summary.json"
    if summ.exists():
        import json

        d = json.loads(summ.read_text())
        heat_ys = d.get("inputs", {}).get("heat_y_list", heat_ys)

    for y0 in heat_ys:
        k, R, rmse, n = _curvature_fit_x(nodes, w, float(y0), Ly, thickness)
        if n < 30:
            print(f"y={float(y0):.1f} mm: insufficient points (n={n})")
        else:
            print(f"y={float(y0):.1f} mm: k={k:.3e} 1/mm, R~{R:.1f} mm, fit_rmse={rmse:.3f} mm (n={n})")

    print("\n--- Deformed VTK geometry (visualization only) ---")
    scale = float(args.vtk_scale)
    nodes_def = nodes + scale * np.column_stack([ux, uy, -uz])
    bbmin_d = nodes_def.min(axis=0)
    bbmax_d = nodes_def.max(axis=0)
    print(f"vtk_scale {scale:g}")
    print("bbox_min_xyz", bbmin_d)
    print("bbox_max_xyz", bbmax_d)
    print(f"z_range_mm {float(bbmax_d[2]-bbmin_d[2]):.6g}")
    print("NOTE: if this looks huge in ParaView, reduce the scale; the actual w is the unscaled w_min/w_max above.")


if __name__ == "__main__":
    main()
