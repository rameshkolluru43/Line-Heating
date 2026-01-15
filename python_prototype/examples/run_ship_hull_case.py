"""Ship-hull-like case with multiple heating lines to induce curvature."""
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
    plot_pass_energy,
    plot_shrinkage,
    plot_lines_overlay,
    plot_deflection_profiles_along_lines,
    plot_deflection_profiles_comparison,
)
from line_heating.animation import save_deflection_animation


def build_plan(quench_mode: str = "water") -> Plan:
    material = Material()
    # Plate approximating a hull panel
    # Ship panel: 1 m x 0.9 m x 12 mm; lines limited to 100 mm length
    plate = Plate(id="hull_panel", length=1000.0, width=900.0, thickness=12.0, material=material, mesh_size=40.0)
    # No prescribed target curvature; let the simulation report what curvature results.
    target = Target(mode="radius", radius=None)

    # Five longitudinal heating lines, offset in y
    y_offsets = [100.0, 200.0, 300.0, 400.0, 500.0,600.0,700.0,800.0]
    lines = []
    passes = []
    for idx, y in enumerate(y_offsets, start=1):
        line_id = f"L{idx}"
        line = LineGeometry(
            id=line_id,
            name=f"longitudinal_{idx}",
            type="straight",
            points=[(0.0, y), (100.0, y)],
            nominal_width=18.0,
        )
        lines.append(line)
        power = 11_000.0 + 500.0 * idx  # vary power slightly
        # Slow travel to reflect hotter passes (approximate; thermal field not solved here)
        speed = max(1.0, 5.0 - 0.5 * idx)  # 5 mm/s down toward ~1 mm/s
        process = PassProcess(
            power_W=power,
            speed_mm_s=speed,
            footprint_width_mm=18.0,
            repeats=1,
            quench=Quench(mode=quench_mode, lag_s=2.0, zones=["Z1"]),
        )
        passes.append(HeatingPass(id=f"P{idx}", line_id=line_id, sequence_index=idx, process=process))

    plan = Plan(
        meta_version="0.1.0",
        plate=plate,
        target=target,
        lines=lines,
        passes=passes,
        simulation=SimulationSettings(
            model="mindlin_q4",
            boundary_condition="simply",
            cooling_decay_per_mm=0.01,  # exponential decay of forcing along line (torch cools as it moves)
        ),
    )
    return plan


def main() -> None:
    scenarios = [
        {"name": "water", "quench_mode": "water", "suffix": "water"},
        {"name": "no_quench", "quench_mode": "air", "suffix": "air"},
    ]

    results = []
    for sc in scenarios:
        plan = build_plan(quench_mode=sc["quench_mode"])
        result = run_structured_plate_solver(plan)
        results.append((sc, plan, result))

    out_dir = os.path.join(os.path.dirname(__file__), "outputs_ship")
    os.makedirs(out_dir, exist_ok=True)

    for sc, plan, result in results:
        print(f"Scenario: {sc['name']}")
        for pr in result["pass_results"]:
            print(f"  {pr['pass_id']}: line_energy={pr['line_energy_J_per_mm']:.3f} J/mm, eps={pr['shrinkage_eps']:.6f}")
        print(f"Total line energy (J): {result['total_line_energy_J']:.3f}")
        print(result["note"])
        if "stats" in result:
            stats = result["stats"]
            print(f"Deflection stats (mm): w_min={stats['w_min']:.6f}, w_max={stats['w_max']:.6f}, |w|max={stats['w_abs_max']:.6f}")

        grid = result["grid"]
        suffix = sc["suffix"]

        fig_w, _ = plot_field_heatmap(grid["x"], grid["y"], grid["w"], f"Deflection w [mm] ({sc['name']})")
        fig_w.savefig(os.path.join(out_dir, f"deflection_{suffix}.png"), dpi=150)

        fig_ws, _ = plot_field_surface(grid["x"], grid["y"], grid["w"], f"Deflection w [mm] ({sc['name']})")
        fig_ws.savefig(os.path.join(out_dir, f"deflection_surface_{suffix}.png"), dpi=150)

        fig_defl_profiles, _ = plot_deflection_profiles_along_lines(grid["x"], grid["y"], grid["w"], [line.__dict__ for line in plan.lines])
        fig_defl_profiles.savefig(os.path.join(out_dir, f"deflection_profiles_{suffix}.png"), dpi=150)

        fig_lines, _ = plot_lines_overlay([line.__dict__ for line in plan.lines], plan.plate.length, plan.plate.width)
        fig_lines.savefig(os.path.join(out_dir, f"heating_lines_{suffix}.png"), dpi=150)

        fig_e, _ = plot_pass_energy(result["pass_results"])
        fig_e.savefig(os.path.join(out_dir, f"line_energy_{suffix}.png"), dpi=150)

        fig_eps, _ = plot_shrinkage(result["pass_results"])
        fig_eps.savefig(os.path.join(out_dir, f"shrinkage_{suffix}.png"), dpi=150)

    # comparison plot for deflection profiles
    (sc_a, plan_a, res_a), (sc_b, plan_b, res_b) = results
    fig_cmp, _ = plot_deflection_profiles_comparison(
        res_a["grid"]["x"],
        res_a["grid"]["y"],
        res_a["grid"]["w"],
        res_b["grid"]["w"],
        [line.__dict__ for line in plan_a.lines],
        label_a=sc_a["name"],
        label_b=sc_b["name"],
    )
    fig_cmp.savefig(os.path.join(out_dir, "deflection_profiles_compare.png"), dpi=150)

    anim_path = os.path.join(out_dir, "deflection_animation_water.gif")
    try:
        save_deflection_animation(plan_a, anim_path)
        print(f"Animation saved to {anim_path}")
    except Exception as exc:
        print(f"Animation failed: {exc}")


if __name__ == "__main__":
    main()
