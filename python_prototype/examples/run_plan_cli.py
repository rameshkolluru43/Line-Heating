"""CLI to run a plan JSON, compute shrinkage, and generate plots (placeholder fields)."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from line_heating.io import load_plan_json
from line_heating.simulation import run_structured_plate_solver
from line_heating.plotting import (
    plot_field_heatmap,
    plot_curvature_fields,
    plot_field_surface,
    plot_pass_energy,
    plot_shrinkage,
    plot_lines_overlay,
    plot_curvature_surfaces,
)
from line_heating.animation import save_deflection_animation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run line heating plan and plot results (placeholder solver).")
    parser.add_argument("plan", type=Path, help="Path to plan JSON")
    parser.add_argument("--plots-dir", type=Path, default=Path("plots"), help="Directory to save plots")
    args = parser.parse_args()

    plan = load_plan_json(str(args.plan))
    result = run_structured_plate_solver(plan)

    print("Pass results:")
    for pr in result["pass_results"]:
        print(pr)
    print("Total line energy (J):", result["total_line_energy_J"])
    print(result["note"])

    args.plots_dir.mkdir(parents=True, exist_ok=True)
    grid = result["grid"]

    fig_w, _ = plot_field_heatmap(grid["x"], grid["y"], grid["w"], "Deflection w [mm]")
    fig_w.savefig(args.plots_dir / "deflection.png", dpi=150)

    fig_ws, _ = plot_field_surface(grid["x"], grid["y"], grid["w"], "Deflection w [mm]")
    fig_ws.savefig(args.plots_dir / "deflection_surface.png", dpi=150)

    fig_k, _ = plot_curvature_fields(grid["x"], grid["y"], grid["kappa_x"], grid["kappa_y"], grid["kappa_xy"])
    fig_k.savefig(args.plots_dir / "curvature.png", dpi=150)

    curv_surfaces = plot_curvature_surfaces(grid["x"], grid["y"], grid["kappa_x"], grid["kappa_y"], grid["kappa_xy"])
    for (fig, _), name in zip(curv_surfaces, ["kappa_x", "kappa_y", "kappa_xy"]):
        fig.savefig(args.plots_dir / f"{name}_surface.png", dpi=150)

    fig_e, _ = plot_pass_energy(result["pass_results"])
    fig_e.savefig(args.plots_dir / "line_energy.png", dpi=150)

    fig_eps, _ = plot_shrinkage(result["pass_results"])
    fig_eps.savefig(args.plots_dir / "shrinkage.png", dpi=150)

    fig_lines, _ = plot_lines_overlay([
        {"id": ln.id, "name": ln.name, "points": ln.points} for ln in plan.lines
    ], plan.plate.length, plan.plate.width)
    fig_lines.savefig(args.plots_dir / "heating_lines.png", dpi=150)

    anim_path = args.plots_dir / "deflection_animation.gif"
    try:
        save_deflection_animation(plan, str(anim_path))
        print(f"Animation saved to {anim_path}")
    except Exception as exc:
        print(f"Animation failed: {exc}")

    print(f"Plots saved to {args.plots_dir}")


if __name__ == "__main__":
    main()
