"""Animation helpers for visualizing heat sequence and deflection fields."""
from __future__ import annotations

from dataclasses import replace
from typing import Callable, List

import numpy as np

try:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError("matplotlib with animation support is required for animations") from exc

from .models import Plan
from .simulation import run_structured_plate_solver

SolverFn = Callable[[Plan], dict]


def _slice_plan(plan: Plan, n_passes: int) -> Plan:
    return Plan(
        meta_version=plan.meta_version,
        plate=plan.plate,
        target=plan.target,
        lines=plan.lines,
        passes=plan.passes[:n_passes],
        calibration=plan.calibration,
        simulation=plan.simulation,
    )


def save_deflection_animation(
    plan: Plan,
    output_path: str,
    solver: SolverFn | None = None,
    fps: int = 2,
    dpi: int = 120,
) -> None:
    """Animate deflection heatmap as passes accumulate. Saves GIF via pillow writer.

    Args:
        plan: Plan with passes in desired sequence.
        output_path: Path to GIF file.
        solver: function that takes a Plan and returns dict with grid {x,y,w}.
        fps: frames per second for animation.
        dpi: output DPI.
    """
    solve = solver or run_structured_plate_solver
    passes_sorted = sorted(plan.passes, key=lambda p: p.sequence_index)
    if not passes_sorted:
        raise ValueError("Plan has no passes to animate")

    w_frames: List[np.ndarray] = []
    x = y = None
    for i in range(1, len(passes_sorted) + 1):
        sub_plan = _slice_plan(plan, i)
        res = solve(sub_plan)
        grid = res["grid"]
        if x is None:
            x = grid["x"]
            y = grid["y"]
        w_frames.append(grid["w"])

    if x is None or y is None:
        raise RuntimeError("Failed to produce grid for animation")

    fig, ax = plt.subplots(figsize=(6, 4))
    im = ax.imshow(
        w_frames[0],
        origin="lower",
        extent=[x.min(), x.max(), y.min(), y.max()],
        cmap="viridis",
        aspect="auto",
        animated=True,
    )
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Deflection w [mm]")

    def update(frame_idx: int):
        im.set_data(w_frames[frame_idx])
        ax.set_title(f"Deflection after pass {frame_idx + 1}")
        return (im,)

    anim = FuncAnimation(fig, update, frames=len(w_frames), interval=1000 / fps, blit=True, repeat=True)
    anim.save(output_path, writer="pillow", dpi=dpi)
    plt.close(fig)
