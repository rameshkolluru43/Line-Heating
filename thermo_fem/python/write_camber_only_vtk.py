"""Write a camber-only deformed VTK from saved outputs.

Purpose:
- Visualize edge-to-edge camber without thickness distortion.
- Uses a mid-surface width-wise camber field w_mid(y) computed from a midspan x-strip.
- Applies that z-translation to ALL nodes (top and bottom shift together), preserving thickness.

Usage:
  python3.11 write_camber_only_vtk.py <out_dir> [--scale 200]

Writes:
  <out_dir>/results_camber_only_deformed.vtk
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def write_vtk_unstructured_grid(file_path: Path, nodes: np.ndarray, tet: np.ndarray, point_data: dict[str, np.ndarray]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    n_points = int(nodes.shape[0])
    n_cells = int(tet.shape[0])

    with file_path.open("w", encoding="utf-8") as f:
        f.write("# vtk DataFile Version 3.0\n")
        f.write("thermo_fem camber-only results\n")
        f.write("ASCII\n")
        f.write("DATASET UNSTRUCTURED_GRID\n")

        f.write(f"POINTS {n_points} float\n")
        for p in nodes:
            f.write(f"{p[0]:.9g} {p[1]:.9g} {p[2]:.9g}\n")

        f.write(f"CELLS {n_cells} {n_cells * 5}\n")
        for c in tet:
            f.write(f"4 {int(c[0])} {int(c[1])} {int(c[2])} {int(c[3])}\n")

        f.write(f"CELL_TYPES {n_cells}\n")
        for _ in range(n_cells):
            f.write("10\n")

        if not point_data:
            return

        f.write(f"POINT_DATA {n_points}\n")
        for name, arr in point_data.items():
            arr = np.asarray(arr)
            if arr.ndim == 1:
                f.write(f"SCALARS {name} float 1\n")
                f.write("LOOKUP_TABLE default\n")
                for v in arr:
                    f.write(f"{float(v):.9g}\n")
            elif arr.ndim == 2 and arr.shape[1] == 3:
                f.write(f"VECTORS {name} float\n")
                for v in arr:
                    f.write(f"{float(v[0]):.9g} {float(v[1]):.9g} {float(v[2]):.9g}\n")
            else:
                raise ValueError(f"Unsupported VTK point_data shape for {name}: {arr.shape}")


def compute_camber_field_widthwise_midspan(
    nodes: np.ndarray,
    displacement: np.ndarray,
    Lx: float,
    Ly: float,
    thickness: float,
    n_bins: int = 80,
    x_band: float | None = None,
) -> np.ndarray:
    tol_z = max(1e-9, float(thickness) * 1e-3)
    top_mask = nodes[:, 2] > float(thickness) - tol_z
    bot_mask = nodes[:, 2] < tol_z

    x0 = 0.5 * float(Lx)
    xb = float(x_band) if x_band is not None else max(float(Lx) / 80.0, 25.0)
    x_strip_top = top_mask & (np.abs(nodes[:, 0] - x0) < xb)
    x_strip_bot = bot_mask & (np.abs(nodes[:, 0] - x0) < xb)

    edges = np.linspace(0.0, float(Ly), max(2, int(n_bins)) + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])

    uz = np.asarray(displacement[:, 2], dtype=float)
    w_top_mean = np.full(centers.size, np.nan, dtype=float)
    w_bot_mean = np.full(centers.size, np.nan, dtype=float)

    for i in range(centers.size):
        y0, y1 = edges[i], edges[i + 1]
        mtop = x_strip_top & (nodes[:, 1] >= y0) & (nodes[:, 1] < y1)
        mbot = x_strip_bot & (nodes[:, 1] >= y0) & (nodes[:, 1] < y1)
        if np.count_nonzero(mtop) >= 2:
            w_top_mean[i] = -float(np.mean(uz[mtop]))
        if np.count_nonzero(mbot) >= 2:
            w_bot_mean[i] = -float(np.mean(uz[mbot]))

    w_mid = 0.5 * (w_top_mean + w_bot_mean)
    ok = np.isfinite(w_mid)
    if np.count_nonzero(ok) < 2:
        return np.zeros(nodes.shape[0], dtype=float)

    w_mid_filled = w_mid.copy()
    w_mid_filled[~ok] = np.interp(centers[~ok], centers[ok], w_mid[ok])

    y = np.asarray(nodes[:, 1], dtype=float)
    bin_idx = np.clip(np.searchsorted(edges, y, side="right") - 1, 0, centers.size - 1)
    return np.asarray(w_mid_filled[bin_idx], dtype=float)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=str)
    ap.add_argument("--scale", type=float, default=200.0, help="VTK deformation scale")
    ap.add_argument("--Lx", type=float, default=1000.0)
    ap.add_argument("--Ly", type=float, default=1000.0)
    ap.add_argument("--thickness", type=float, default=12.0)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    nodes = np.load(out_dir / "nodes.npy")
    tet = np.load(out_dir / "tet.npy")
    disp = np.load(out_dir / "displacement.npy")

    w_camber = compute_camber_field_widthwise_midspan(
        nodes=nodes,
        displacement=disp,
        Lx=float(args.Lx),
        Ly=float(args.Ly),
        thickness=float(args.thickness),
    )

    point_data: dict[str, np.ndarray] = {
        "Displacement": disp,
        "w": -disp[:, 2],
        "w_camber_midspan": w_camber,
        "DisplacementCamberDown": np.column_stack([np.zeros(nodes.shape[0]), np.zeros(nodes.shape[0]), w_camber]),
    }

    nodes_def = nodes + float(args.scale) * point_data["DisplacementCamberDown"]
    write_vtk_unstructured_grid(out_dir / "results_camber_only_deformed.vtk", nodes_def, tet, point_data)
    print(out_dir / "results_camber_only_deformed.vtk")


if __name__ == "__main__":
    main()
