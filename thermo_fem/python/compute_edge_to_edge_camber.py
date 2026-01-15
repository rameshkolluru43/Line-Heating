"""Compute edge-to-edge camber (mid-surface) from saved outputs.

This uses the same notion as the driver:
- Pick a strip around midspan x=Lx/2 (±x_band)
- Compute average top and bottom deflection in small y-strips near y=0 and y=Ly
- Mid-surface w := 0.5*(w_top + w_bottom)
- Edge-to-edge camber := w_mid(y=Ly edge) - w_mid(y=0 edge)

Run:
  python3.11 compute_edge_to_edge_camber.py outputs_dir [--Lx 1000 --Ly 1000 --thickness 12]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np


def compute_edge_to_edge_camber_midspan(
    nodes: np.ndarray,
    displacement: np.ndarray,
    Lx: float,
    Ly: float,
    thickness: float,
    x_band: float | None = None,
    y_band: float | None = None,
) -> tuple[float, float, float]:
    tol_z = max(1e-9, float(thickness) * 1e-3)
    top_mask = nodes[:, 2] > float(thickness) - tol_z
    bot_mask = nodes[:, 2] < tol_z

    x0 = 0.5 * float(Lx)
    xb0 = float(x_band) if x_band is not None else max(float(Lx) / 80.0, 25.0)
    yb0 = float(y_band) if y_band is not None else max(float(Ly) / 80.0, 25.0)

    uz = np.asarray(displacement[:, 2], dtype=float)

    def mid_w(mask_y: np.ndarray) -> tuple[float, float, float]:
        # Expand the x-strip until we capture at least a handful of nodes.
        xb = xb0
        for _ in range(8):
            mt = top_mask & mask_y & (np.abs(nodes[:, 0] - x0) < xb)
            mb = bot_mask & mask_y & (np.abs(nodes[:, 0] - x0) < xb)
            if np.count_nonzero(mt) >= 3 and np.count_nonzero(mb) >= 3:
                w_top = -float(np.mean(uz[mt]))
                w_bot = -float(np.mean(uz[mb]))
                return 0.5 * (w_top + w_bot), xb, float(np.count_nonzero(mt) + np.count_nonzero(mb))
            xb *= 1.6
        raise RuntimeError("Not enough top/bottom nodes selected; try increasing --x-band/--y-band")

    # Expand y edge strips if needed.
    yb = yb0
    for _ in range(8):
        try:
            w_mid_y0, xb_used_0, _ = mid_w(nodes[:, 1] < yb)
            w_mid_yLy, xb_used_1, _ = mid_w(nodes[:, 1] > float(Ly) - yb)
            xb_used = max(xb_used_0, xb_used_1)
            yb_used = yb
            break
        except RuntimeError:
            yb *= 1.6
    else:
        raise RuntimeError("Not enough nodes near edges; increase --x-band and/or --y-band")

    camber = w_mid_yLy - w_mid_y0
    return float(camber), float(w_mid_y0), float(w_mid_yLy)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir", type=str, help="outputs directory containing nodes.npy and displacement.npy")
    ap.add_argument("--Lx", type=float, default=1000.0)
    ap.add_argument("--Ly", type=float, default=1000.0)
    ap.add_argument("--thickness", type=float, default=12.0)
    ap.add_argument("--x-band", type=float, default=None)
    ap.add_argument("--y-band", type=float, default=None)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    nodes = np.load(out_dir / "nodes.npy")
    disp = np.load(out_dir / "displacement.npy")

    camber, w0, w1 = compute_edge_to_edge_camber_midspan(
        nodes,
        disp,
        Lx=float(args.Lx),
        Ly=float(args.Ly),
        thickness=float(args.thickness),
        x_band=args.x_band,
        y_band=args.y_band,
    )

    print(f"edge_to_edge_camber_midspan_mm {camber:+.6f}")
    print(f"w_mid_edge_y0_mm             {w0:+.6f}")
    print(f"w_mid_edge_yLy_mm            {w1:+.6f}")


if __name__ == "__main__":
    main()
