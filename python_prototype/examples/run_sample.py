"""Run a tiny shrinkage calculation example."""
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
from line_heating.simulation import run_linear_shrinkage_plan, run_structured_plate_solver
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
    material = Material()
    plate = Plate(id="plate1", length=2000.0, width=1000.0, thickness=12.0, material=material)
    target = Target(mode="radius", radius=5000.0)

    line = LineGeometry(
        id="l1",
        name="centerline",
        type="straight",
        points=[(0.0, 500.0), (2000.0, 500.0)],
        nominal_width=18.0,
    )

    process = PassProcess(
        power_W=12_000.0,
        speed_mm_s=15.0,
        footprint_width_mm=18.0,
        repeats=1,
        quench=Quench(mode="water", lag_s=2.0, zones=["Z1"]),
    )

    pass1 = HeatingPass(id="p1", line_id="l1", sequence_index=1, process=process)

    plan = Plan(
        meta_version="0.1.0",
        plate=plate,
        target=target,
        lines=[line],
        passes=[pass1],
        simulation=SimulationSettings(model="mindlin_q4", boundary_condition="clamped"),
    )

    result = run_linear_shrinkage_plan(plan)
    print("Pass results (aggregate):")
    for pr in result["pass_results"]:
        print(f"  {pr['pass_id']}: line_energy={pr['line_energy_J_per_mm']:.3f} J/mm, eps={pr['shrinkage_eps']:.6f}")
    print(f"Total line energy (J): {result['total_line_energy_J']:.3f}")
    print(result["note"])

    grid_result = run_structured_plate_solver(plan)
    print("\nStructured grid shape:", grid_result["grid"]["w"].shape)
    print(grid_result["note"])
    if "stats" in grid_result:
        stats = grid_result["stats"]
        print(f"Deflection stats (mm): w_min={stats['w_min']:.6f}, w_max={stats['w_max']:.6f}, |w|max={stats['w_abs_max']:.6f}")

    # Plotting (fields are zero in placeholder, but this shows the workflow).
    out_dir = os.path.join(os.path.dirname(__file__), "outputs")
    os.makedirs(out_dir, exist_ok=True)

    fig_w, _ = plot_field_heatmap(grid_result["grid"]["x"], grid_result["grid"]["y"], grid_result["grid"]["w"], "Deflection w [mm]")
    fig_w.savefig(os.path.join(out_dir, "deflection.png"), dpi=150)

    fig_ws, _ = plot_field_surface(grid_result["grid"]["x"], grid_result["grid"]["y"], grid_result["grid"]["w"], "Deflection w [mm]")
    fig_ws.savefig(os.path.join(out_dir, "deflection_surface.png"), dpi=150)

    fig_k, _ = plot_curvature_fields(
        grid_result["grid"]["x"],
        grid_result["grid"]["y"],
        grid_result["grid"]["kappa_x"],
        grid_result["grid"]["kappa_y"],
        grid_result["grid"]["kappa_xy"],
    )
    fig_k.savefig(os.path.join(out_dir, "curvature.png"), dpi=150)

    curv_surfaces = plot_curvature_surfaces(
        grid_result["grid"]["x"],
        grid_result["grid"]["y"],
        grid_result["grid"]["kappa_x"],
        grid_result["grid"]["kappa_y"],
        grid_result["grid"]["kappa_xy"],
    )
    for (fig, _), name in zip(curv_surfaces, ["kappa_x", "kappa_y", "kappa_xy"]):
        fig.savefig(os.path.join(out_dir, f"{name}_surface.png"), dpi=150)

    fig_lines, _ = plot_lines_overlay(
        [line.__dict__ for line in plan.lines], plan.plate.length, plan.plate.width
    )
    fig_lines.savefig(os.path.join(out_dir, "heating_lines.png"), dpi=150)

    anim_path = os.path.join(out_dir, "deflection_animation.gif")
    try:
        save_deflection_animation(plan, anim_path)
        print(f"Animation saved to {anim_path}")
    except Exception as exc:
        print(f"Animation failed: {exc}")

    fig_e, _ = plot_pass_energy(result["pass_results"])
    fig_e.savefig(os.path.join(out_dir, "line_energy.png"), dpi=150)

    fig_eps, _ = plot_shrinkage(result["pass_results"])
    fig_eps.savefig(os.path.join(out_dir, "shrinkage.png"), dpi=150)

    print(f"Plots saved to {out_dir}")


if __name__ == "__main__":
    main()
