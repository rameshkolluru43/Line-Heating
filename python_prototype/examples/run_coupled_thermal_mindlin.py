"""Coupled thermal->Mindlin deflection demo for the centerline pass.

Workflow:
- Solve 2D heat on the plate using thermo_fem bindings with a line source tuned to ~923 K peak.
- Interpolate nodal temperatures to element-center values on the Mindlin grid.
- Map temperature (C) to shrinkage, solve Mindlin Q4 plate, and plot deflection/curvature.

This script also prints thermal/structural mesh counts, deflection stats, and a simple
left-right symmetry metric along the centerline to help sanity-check results.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter

# Local paths
ROOT = Path(__file__).resolve().parents[1]
THERMO_PY = ROOT.parent / "thermo_fem" / "python"
THERMO_CPP = ROOT.parent / "thermo_fem" / "build" / "cpp"
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))
if str(THERMO_PY) not in sys.path:
    sys.path.append(str(THERMO_PY))
if str(THERMO_CPP) not in sys.path:
    sys.path.append(str(THERMO_CPP))

import run_plate_heat as heat  # type: ignore
from line_heating.mindlin_fe import solve_mindlin_with_temperature
from line_heating.plotting import (
    plot_curvature_fields,
    plot_curvature_surfaces,
    plot_deflection_profiles_along_lines,
    plot_field_heatmap,
    plot_field_surface,
)
from line_heating.shrinkage import Calibration
from run_center_pass_case import build_plan


def solve_thermal(plan, line_q_w_per_mm: float, line_width_mm: float, gaussian: bool = False, plot: bool = False, out_dir: Path | None = None):
    nodes, tri, edges = heat.build_plate_mesh(plan.plate.length, plan.plate.width, plan.plate.mesh_size)
    K, M = heat.assemble_sparse(nodes, tri, plan.plate.material.k if hasattr(plan.plate.material, "k") else 0.045, plan.plate.material.rho if hasattr(plan.plate.material, "rho") else 7.85e-6, 500.0)
    Kb, rhs_b = heat.boundary_matrices(nodes, edges, h_conv=5e-5, T_inf=293.0)
    bc_nodes = heat.boundary_nodes_rect(nodes, plan.plate.length, plan.plate.width, tol=1e-6)
    q_vec = heat.line_source_field(nodes, plan.plate.length, plan.plate.width, line_q_w_per_mm, line_width_mm, gaussian=gaussian)
    T0 = np.zeros(nodes.shape[0])
    T_final = heat.implicit_heat(
        K,
        M,
        T0,
        dt=5e-4,
        steps=500,
        q_vol=q_vec,
        dirichlet_nodes=bc_nodes,
        dirichlet_value=293.0,
        Kb=Kb,
        rhs_b=rhs_b,
    )
    if plot and out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        heat.plot_solution(nodes, tri, T_final, out_dir)
    return nodes, tri, T_final


def interpolate_to_mindlin_grid(plan, nodes: np.ndarray, T_nodes: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    nx = int(np.ceil(plan.plate.length / plan.plate.mesh_size)) + 1
    ny = int(np.ceil(plan.plate.width / plan.plate.mesh_size)) + 1
    xs = np.linspace(0.0, plan.plate.length, nx)
    ys = np.linspace(0.0, plan.plate.width, ny)
    xc = 0.5 * (xs[:-1] + xs[1:])
    yc = 0.5 * (ys[:-1] + ys[1:])
    Xc, Yc = np.meshgrid(xc, yc)
    pts = nodes[:, :2]
    targets = np.column_stack([Xc.ravel(), Yc.ravel()])
    T_centers = griddata(pts, T_nodes, targets, method="linear", fill_value=0.0)
    T_elem = T_centers.reshape((ny - 1, nx - 1))
    T_elem_C = np.clip(T_elem - 273.15, 0.0, None)
    # Smooth to reduce checkerboard loading in Mindlin mapping
    T_elem_C = gaussian_filter(T_elem_C, sigma=0.5, mode="nearest")
    return T_elem_C, xc, yc


def plot_results(out_dir: Path, plan, fe_res):
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_w, _ = plot_field_heatmap(fe_res.x, fe_res.y, fe_res.w, "Deflection w [mm]")
    fig_w.savefig(out_dir / "deflection_heatmap.png", dpi=150)

    fig_ws, _ = plot_field_surface(fe_res.x, fe_res.y, fe_res.w, "Deflection w [mm]")
    fig_ws.savefig(out_dir / "deflection_surface.png", dpi=150)

    fig_k, _ = plot_curvature_fields(fe_res.x, fe_res.y, fe_res.kappa_x, fe_res.kappa_y, fe_res.kappa_xy)
    fig_k.savefig(out_dir / "curvature_fields.png", dpi=150)

    for (fig, _), name in zip(
        plot_curvature_surfaces(fe_res.x, fe_res.y, fe_res.kappa_x, fe_res.kappa_y, fe_res.kappa_xy),
        ("kappa_x", "kappa_y", "kappa_xy"),
    ):
        fig.savefig(out_dir / f"{name}_surface.png", dpi=150)

    fig_line, ax_line = plot_deflection_profiles_along_lines(fe_res.x, fe_res.y, fe_res.w, [ln.__dict__ for ln in plan.lines])
    ax_line.set_title("Deflection along line")
    fig_line.savefig(out_dir / "deflection_profile.png", dpi=150)

    # Curvature along centerline (kappa_x)
    j_mid = int(np.abs(fe_res.y - plan.plate.width / 2.0).argmin())
    fig_kline, ax_kline = plt.subplots(figsize=(6, 4))
    ax_kline.plot(fe_res.x, fe_res.kappa_x[j_mid, :], label="kappa_x midline")
    ax_kline.set_xlabel("x [mm]")
    ax_kline.set_ylabel("kappa_x [1/mm]")
    ax_kline.set_title("Curvature kappa_x along centerline")
    ax_kline.grid(True, alpha=0.3)
    ax_kline.legend()
    fig_kline.savefig(out_dir / "kappa_x_centerline.png", dpi=150)


def centerline_symmetry(w: np.ndarray, x: np.ndarray) -> float:
    """Return max relative asymmetry about the plate mid-span for the mid-y row.

    For a symmetric load and boundary, the centerline deflection should be symmetric in x.
    Metric: max(|w(x)-w(L-x)|)/max(|w|). Returns 0 if |w| is zero.
    """
    if w.size == 0 or x.size < 2:
        return 0.0
    j = w.shape[0] // 2
    row = w[j, :]
    w_abs_max = float(np.abs(row).max())
    if w_abs_max == 0:
        return 0.0
    flipped = row[::-1]
    n = min(row.size, flipped.size)
    asym = np.max(np.abs(row[:n] - flipped[:n])) / w_abs_max
    return float(asym)


def main():
    parser = argparse.ArgumentParser(description="Coupled thermal->Mindlin deflection demo")
    parser.add_argument("--load-scale", type=float, default=5e-7, help="Calibration load_scale for shrinkage->load mapping")
    parser.add_argument("--mesh-size", type=float, default=None, help="Override plate mesh_size (mm) for both thermal and Mindlin grids")
    parser.add_argument("--boundary", type=str, default="simply", choices=["simply", "clamped", "corners_simply", "corners_clamped", "free"], help="Mindlin boundary condition")
    parser.add_argument("--line-q", type=float, default=340.0, help="Line heat W/mm for thermal solve")
    parser.add_argument("--gaussian", action="store_true", help="Use gaussian line source (default)")
    parser.add_argument("--top-hat", dest="gaussian", action="store_false", help="Use top-hat line source")
    args = parser.parse_args()

    plan = build_plan(repeats=1)
    plan.simulation.boundary_condition = args.boundary
    if args.mesh_size is not None:
        plan.plate.mesh_size = args.mesh_size
    line = plan.lines[0]
    line_q = args.line_q
    line_width = line.nominal_width

    out_dir = Path(__file__).with_name("outputs_coupled")
    nodes, tri, T_nodes = solve_thermal(plan, line_q, line_width, gaussian=args.gaussian, plot=True, out_dir=out_dir / "thermal")
    T_elem_C, xc, yc = interpolate_to_mindlin_grid(plan, nodes, T_nodes)

    cal = Calibration(load_scale=args.load_scale)
    fe_res = solve_mindlin_with_temperature(plan, T_elem_C, cal)

    plot_results(out_dir, plan, fe_res)

    # Diagnostics
    print(f"Thermal mesh: nodes={nodes.shape[0]}, tris={tri.shape[0]}")
    print(f"Mindlin grid: nx={fe_res.w.shape[1]}, ny={fe_res.w.shape[0]}")
    print(f"Thermal field: T_min={T_nodes.min():.3f}, T_max={T_nodes.max():.3f} (K, nodal)")
    print(f"Element-center temperature (C) min={T_elem_C.min():.3f}, max={T_elem_C.max():.3f}")
    w_abs_max = float(np.abs(fe_res.w).max())
    print(f"Deflection stats (mm): w_min={fe_res.w.min():.6f}, w_max={fe_res.w.max():.6f}, |w|max={w_abs_max:.6f}")
    print(f"Curvature stats (1/mm): kx_min={fe_res.kappa_x.min():.6e}, kx_max={fe_res.kappa_x.max():.6e}")
    asym = centerline_symmetry(fe_res.w, fe_res.x)
    print(f"Centerline symmetry: max(|w(x)-w(L-x)|)/|w|max = {asym:.3e}")


if __name__ == "__main__":
    main()
