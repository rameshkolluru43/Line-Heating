"""Plot PINN deflection results saved by line_heating_pinn.py."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot PINN deflection results")
    parser.add_argument("--input", type=str, required=True, help="Path to .npz results")
    parser.add_argument("--out-dir", type=str, default="results", help="Output directory for plots")
    args = parser.parse_args()

    inp = Path(args.input)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = np.load(inp)
    x = data["x"]
    y = data["y"]
    w = data["w"]

    # 2D heatmap
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(
        w,
        origin="lower",
        extent=[x.min(), x.max(), y.min(), y.max()],
        cmap="coolwarm",
        aspect="equal",
    )
    ax.set_title("PINN Deflection w (mm) at final time")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("w (mm)")
    heatmap_path = out_dir / f"{inp.stem}_deflection.png"
    fig.tight_layout()
    fig.savefig(heatmap_path, dpi=200)
    plt.close(fig)

    # Line plot along midline y
    mid_idx = int(len(y) // 2)
    w_mid = w[mid_idx, :]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(x, w_mid, color="#1f77b4", lw=2)
    ax.axhline(0.0, color="#444", lw=0.8)
    ax.set_title("Deflection along midline (y = Ly/2)")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("w (mm)")
    line_path = out_dir / f"{inp.stem}_deflection_midline.png"
    fig.tight_layout()
    fig.savefig(line_path, dpi=200)
    plt.close(fig)

    print(f"Saved: {heatmap_path}")
    print(f"Saved: {line_path}")


if __name__ == "__main__":
    main()
