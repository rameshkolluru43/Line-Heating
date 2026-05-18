#!/usr/bin/env python3
"""Plot 3D plate surface from a VTK legacy ASCII file."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.tri as mtri


def read_vtk_points(file_path: Path) -> np.ndarray:
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
    ap.add_argument("vtk_file", type=str, help="Path to VTK file")
    ap.add_argument("--out", type=str, default=None, help="Output PNG path")
    args = ap.parse_args()

    vtk_file = Path(args.vtk_file)
    nodes = read_vtk_points(vtk_file)

    z_max = nodes[:, 2].max()
    tol = max(1e-6, (nodes[:, 2].max() - nodes[:, 2].min()) * 0.01)
    top_mask = nodes[:, 2] >= (z_max - tol)

    x = nodes[top_mask, 0]
    y = nodes[top_mask, 1]
    z = nodes[top_mask, 2]

    triang = mtri.Triangulation(x, y)

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")
    ax.plot_trisurf(triang, z, cmap="viridis", linewidth=0.2, alpha=0.95)
    ax.set_title("3D Plate Surface (VTK)")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_zlabel("z (mm)")
    plt.tight_layout()

    if args.out:
        out_path = Path(args.out)
    else:
        out_path = vtk_file.with_suffix("")
        out_path = out_path.parent / "plate_3d_from_vtk.png"

    fig.savefig(out_path, dpi=160)
    plt.close(fig)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()