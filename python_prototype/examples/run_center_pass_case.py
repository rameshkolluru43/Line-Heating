"""Single-plate, center-pass case for quick deflection estimates."""
from __future__ import annotations

import os

from line_heating.models import (
    LineGeometry,
    Material,
    PassProcess,
    Plate,
    Plan,
    Target,
    HeatingPass,
    Quench,
    SimulationSettings,
)
from line_heating.simulation import run_structured_plate_solver
from line_heating.plotting import (
    plot_field_heatmap,
    plot_field_surface,
    plot_curvature_fields,
    plot_pass_energy,
    plot_shrinkage,
    plot_lines_overlay,
    plot_deflection_profiles_along_lines,
)


def build_plan(repeats: int = 1) -> Plan:
    material = Material()
    plate = Plate(id="plate_center", length=1000.0, width=900.0, thickness=12.0, material=material, mesh_size=5.0)
    target = Target(mode="radius", radius=None)

    line = LineGeometry(
        id="L1",
        name="centerline",
        type="straight",
        points=[(0.0, plate.width / 2.0), (plate.length, plate.width / 2.0)],
        nominal_width=18.0,
    )

    process = PassProcess(
        power_W=12_000.0,
        speed_mm_s=15.0,
        footprint_width_mm=18.0,
        repeats=repeats,
        quench=Quench(mode="water", lag_s=2.0, zones=["Z1"]),
    )

    pass1 = HeatingPass(id="P1", line_id="L1", sequence_index=1, process=process)

    plan = Plan(
        meta_version="0.1.0",
        plate=plate,
        target=target,
        lines=[line],
        passes=[pass1],
        simulation=SimulationSettings(model="mindlin_q4", boundary_condition="simply"),
    )
    return plan


def run_case(repeats: int, label: str) -> None:
    plan = build_plan(repeats=repeats)
    result = run_structured_plate_solver(plan)

    print(f"Case: {label}")
    for pr in result["pass_results"]:
        print(f"  {pr['pass_id']}: line_energy={pr['line_energy_J_per_mm']:.3f} J/mm, eps={pr['shrinkage_eps']:.6f}")
    print(f"Total line energy (J): {result['total_line_energy_J']:.3f}")
    print(result["note"])
    if "stats" in result:
        stats = result["stats"]
        print(f"Deflection stats (mm): w_min={stats['w_min']:.6f}, w_max={stats['w_max']:.6f}, |w|max={stats['w_abs_max']:.6f}")

    out_dir = os.path.join(os.path.dirname(__file__), "outputs_center")
    os.makedirs(out_dir, exist_ok=True)

    grid = result["grid"]
    suffix = label.replace(" ", "_")

    fig_w, _ = plot_field_heatmap(grid["x"], grid["y"], grid["w"], f"Deflection w [mm] ({label})")
    fig_w.savefig(os.path.join(out_dir, f"deflection_{suffix}.png"), dpi=150)

    fig_ws, _ = plot_field_surface(grid["x"], grid["y"], grid["w"], f"Deflection w [mm] ({label})")
    fig_ws.savefig(os.path.join(out_dir, f"deflection_surface_{suffix}.png"), dpi=150)

    fig_k, _ = plot_curvature_fields(grid["x"], grid["y"], grid["kappa_x"], grid["kappa_y"], grid["kappa_xy"])
    fig_k.savefig(os.path.join(out_dir, f"curvature_{suffix}.png"), dpi=150)

    fig_e, _ = plot_pass_energy(result["pass_results"])
    fig_e.savefig(os.path.join(out_dir, f"line_energy_{suffix}.png"), dpi=150)

    fig_eps, _ = plot_shrinkage(result["pass_results"])
    fig_eps.savefig(os.path.join(out_dir, f"shrinkage_{suffix}.png"), dpi=150)

    fig_lines, _ = plot_lines_overlay([line.__dict__ for line in plan.lines], plan.plate.length, plan.plate.width)
    fig_lines.savefig(os.path.join(out_dir, f"heating_lines_{suffix}.png"), dpi=150)

    fig_prof, _ = plot_deflection_profiles_along_lines(grid["x"], grid["y"], grid["w"], [line.__dict__ for line in plan.lines])
    fig_prof.savefig(os.path.join(out_dir, f"deflection_profile_{suffix}.png"), dpi=150)


def main() -> None:
    # Single pass
    run_case(repeats=1, label="single_pass")
    # Multiple passes (e.g., 3 passes on same line)
    run_case(repeats=3, label="triple_pass")


if __name__ == "__main__":
    main()
