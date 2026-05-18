#!/usr/bin/env python3
"""
Plot unscaled deformation using VTK files (undeformed + deformed raw).

Reads:
  results_undeformed.vtk
  results_deformed_raw.vtk

Outputs:
  deflection_3d_unscaled_vtk.png
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as mtri


def read_vtk_points(file_path: Path) -> np.ndarray:
    """Read point coordinates from a VTK legacy ASCII file."""
    with file_path.open("r") as f:
        lines = f.readlines()

    points_line_idx = None
    n_points = None
    for i, line in enumerate(lines):
        if line.startswith("POINTS "):
            parts = line.strip().split()
            n_points = int(parts[1])
            points_line_idx = i + 1
            break

    if points_line_idx is None or n_points is None:
        raise ValueError(f"POINTS section not found in {file_path}")

    coords = []
    for line in lines[points_line_idx:]:
        if line.startswith("CELLS "):
            break
        coords.extend(line.strip().split())

    coords = np.array(coords, dtype=float)
    if coords.size < n_points * 3:
        raise ValueError("Not enough point data in VTK file")

    return coords[: n_points * 3].reshape((n_points, 3))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=str, help="Results directory containing VTK files")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    undeformed_vtk = out_dir / "results_undeformed.vtk"
    deformed_vtk = out_dir / "results_deformed_raw.vtk"

    if not undeformed_vtk.exists() or not deformed_vtk.exists():
        raise FileNotFoundError("Missing VTK files in output directory")

    nodes_undef = read_vtk_points(undeformed_vtk)
    nodes_def = read_vtk_points(deformed_vtk)

    z_max = nodes_undef[:, 2].max()
    tol = max(1e-6, (nodes_undef[:, 2].max() - nodes_undef[:, 2].min()) * 0.01)
    top_mask = nodes_undef[:, 2] >= (z_max - tol)

    x = nodes_undef[top_mask, 0]
    y = nodes_undef[top_mask, 1]
    w = nodes_def[top_mask, 2] - nodes_undef[top_mask, 2]

    triang = mtri.Triangulation(x, y)

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_trisurf(
        triang,
        w,
        cmap="RdBu_r",
        linewidth=0.2,
        antialiased=True,
        alpha=0.95,
    )
    fig.colorbar(surf, ax=ax, shrink=0.6, label="Deflection (mm)")
    ax.set_title("Unscaled Deformation (from VTK)")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_zlabel("w (mm)")
    plt.tight_layout()

    out_file = out_dir / "deflection_3d_unscaled_vtk.png"
    fig.savefig(out_file, dpi=160)
    plt.close(fig)

    print(f"Saved: {out_file}")


if __name__ == "__main__":
    main()