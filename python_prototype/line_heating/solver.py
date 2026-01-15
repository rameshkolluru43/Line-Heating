"""Structured thin-plate solver (simplified finite-difference FE).

Notes
- Uses a Kirchhoff-Love plate bending model discretized on a structured grid
    via a biharmonic (Δ² w) operator with Dirichlet boundary (w=0) for now.
- Shrinkage bands are converted to an equivalent curvature forcing field.
- This is intentionally lightweight and meant to be replaced by a higher-fidelity
    Mindlin/Reissner FE later, but provides non-zero fields for iteration/plots.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .models import LineGeometry, Plan
from .shrinkage import Calibration, PlateContext, compute_shrinkage
from .mindlin_fe import solve_mindlin


@dataclass
class FieldResult:
    x: np.ndarray  # shape (nx,)
    y: np.ndarray  # shape (ny,)
    w: np.ndarray  # deflection field shape (ny, nx)
    kappa_x: np.ndarray  # curvature fields (placeholders)
    kappa_y: np.ndarray
    kappa_xy: np.ndarray


@dataclass
class SolveResult:
    field: FieldResult
    pass_results: List[Dict[str, float]]
    total_line_energy_J: float
    note: str


def _structured_grid(Lx: float, Ly: float, h: float) -> Tuple[np.ndarray, np.ndarray]:
    nx = max(2, int(np.ceil(Lx / h)) + 1)
    ny = max(2, int(np.ceil(Ly / h)) + 1)
    x = np.linspace(0.0, Lx, nx)
    y = np.linspace(0.0, Ly, ny)
    return x, y


def _pairwise(points: Sequence[Tuple[float, float]]):
    for a, b in zip(points[:-1], points[1:]):
        yield np.asarray(a, dtype=float), np.asarray(b, dtype=float)


def _distance_and_t_to_polyline(xg: np.ndarray, yg: np.ndarray, line: LineGeometry) -> Tuple[np.ndarray, np.ndarray, float]:
    """Compute distance and normalized arc-length coordinate to closest point on polyline.

    Returns
    -------
    dist : ndarray
        Minimum distance from each grid point to the polyline.
    t_norm : ndarray
        Normalized curvilinear coordinate (0 at start, 1 at end) of the closest point.
    total_len : float
        Total polyline length (mm); 0 if degenerate.
    """
    dist2 = np.full_like(xg, np.inf, dtype=float)
    t_norm = np.zeros_like(xg, dtype=float)

    # total length for normalization
    seg_lengths = []
    for p0, p1 in _pairwise(line.points):
        seg_lengths.append(np.linalg.norm(p1 - p0))
    total_len = float(np.sum(seg_lengths))
    if total_len <= 0:
        return np.full_like(xg, np.inf, dtype=float), t_norm, total_len

    seg_start = 0.0
    for (p0, p1), seg_len in zip(_pairwise(line.points), seg_lengths):
        if seg_len == 0:
            d2 = (xg - p0[0]) ** 2 + (yg - p0[1]) ** 2
            mask = d2 < dist2
            dist2[mask] = d2[mask]
            t_norm[mask] = seg_start / total_len
            seg_start += seg_len
            continue

        v = p1 - p0
        seg_len2 = seg_len * seg_len
        t = ((xg - p0[0]) * v[0] + (yg - p0[1]) * v[1]) / seg_len2
        t = np.clip(t, 0.0, 1.0)
        proj_x = p0[0] + t * v[0]
        proj_y = p0[1] + t * v[1]
        d2 = (xg - proj_x) ** 2 + (yg - proj_y) ** 2
        mask = d2 < dist2
        dist2[mask] = d2[mask]
        # Broadcast-safe update using where to avoid shape mismatch
        t_norm = np.where(mask, (seg_start + t * seg_len) / total_len, t_norm)
        seg_start += seg_len

    return np.sqrt(dist2), t_norm, total_len


def _band_load(x: np.ndarray, y: np.ndarray, lines: List[LineGeometry], plan: Plan, cal: Calibration) -> np.ndarray:
    """Create a load field from shrinkage bands (approximate curvature forcing)."""
    X, Y = np.meshgrid(x, y)
    load = np.zeros_like(X)
    # Plate bending rigidity D [N*mm], with E in MPa (=N/mm^2) and thickness in mm.
    t = plan.plate.thickness
    E = plan.plate.material.E
    nu = plan.plate.material.nu
    D_plate = (E * t**3) / (12.0 * (1.0 - nu * nu))
    plate_ctx = PlateContext(thickness_mm=plan.plate.thickness, steel_factor=plan.plate.material.steel_factor)

    for p in sorted(plan.passes, key=lambda p: p.sequence_index):
        res = compute_shrinkage(p, plate_ctx, cal)
        p.derived_line_energy_J_mm = res["line_energy_J_per_mm"]
        p.derived_shrinkage_eps = res["shrinkage_eps"]
        p.effective_width_mm = res["effective_width_mm"]

        line = next((ln for ln in plan.lines if ln.id == p.line_id), None)
        if line is None or len(line.points) < 2:
            continue
        dist, t_norm, total_len = _distance_and_t_to_polyline(X, Y, line)
        width = max(1e-6, res["effective_width_mm"])
        if plan.simulation.band_profile == "gaussian":
            sigma = plan.simulation.sigma_mm or (0.5 * width)
            weight = np.exp(-0.5 * (dist / sigma) ** 2)
        else:
            weight = (dist <= width * 0.5).astype(float)
        # Exponential cooling/decay along the travel direction (0 disables).
        if plan.simulation.cooling_decay_per_mm > 0.0:
            cooling = np.exp(-plan.simulation.cooling_decay_per_mm * t_norm * total_len)
        else:
            cooling = 1.0
        # Sign: heat on +z should bend toward -z; use -1 for +z, +1 for -z.
        side_sign = -1.0 if line.heated_side == "+z" else 1.0
        # Convert shrinkage curvature (~eps/width) to an equivalent transverse load; shrinkage already reflects heat input.
        q_equiv = side_sign * D_plate * (res["shrinkage_eps"] / width) * cooling
        load += q_equiv * weight
    return load


def _build_biharmonic_matrix(nx: int, ny: int, hx: float, hy: float) -> sp.csr_matrix:
    """Build sparse biharmonic operator with Dirichlet boundaries on structured grid."""
    # Interior node counts
    nx_i = nx - 2
    ny_i = ny - 2
    if nx_i < 1 or ny_i < 1:
        raise ValueError("Grid too small for biharmonic solve")

    # 1D second-derivative with Dirichlet boundaries: tridiagonal
    diag_x = np.full(nx_i, -2.0 / (hx * hx))
    off_x = np.full(nx_i - 1, 1.0 / (hx * hx))
    Dxx = sp.diags([off_x, diag_x, off_x], [-1, 0, 1], format="csr")

    diag_y = np.full(ny_i, -2.0 / (hy * hy))
    off_y = np.full(ny_i - 1, 1.0 / (hy * hy))
    Dyy = sp.diags([off_y, diag_y, off_y], [-1, 0, 1], format="csr")

    Ix = sp.eye(nx_i, format="csr")
    Iy = sp.eye(ny_i, format="csr")

    Lap = sp.kron(Iy, Dxx) + sp.kron(Dyy, Ix)
    A = Lap @ Lap  # biharmonic operator
    return A.tocsr()


def solve_plan_structured(plan: Plan, calibration: Calibration | None = None) -> SolveResult:
    """Run either simplified biharmonic or Mindlin FE depending on model flag."""
    cal = calibration or Calibration()

    x, y = _structured_grid(plan.plate.length, plan.plate.width, plan.plate.mesh_size)
    hx = float(x[1] - x[0]) if x.size > 1 else 1.0
    hy = float(y[1] - y[0]) if y.size > 1 else 1.0

    load = _band_load(x, y, plan.lines, plan, cal)

    nx, ny = x.size, y.size
    A = _build_biharmonic_matrix(nx, ny, hx, hy)

    rhs = load[1:-1, 1:-1].ravel()
    w_int = spla.spsolve(A, rhs)
    w = np.zeros((ny, nx))
    w[1:-1, 1:-1] = w_int.reshape((ny - 2, nx - 2))

    # If boundary_condition is "simply", we still enforce w=0 at boundary in this simplified model.
    # A future Mindlin FE should distinguish slope constraints.

    # Curvatures via second derivatives (central differences); zero at boundary
    kx = np.zeros_like(w)
    ky = np.zeros_like(w)
    kxy = np.zeros_like(w)
    kx[1:-1, 1:-1] = (w[1:-1, 2:] - 2 * w[1:-1, 1:-1] + w[1:-1, :-2]) / (hx * hx)
    ky[1:-1, 1:-1] = (w[2:, 1:-1] - 2 * w[1:-1, 1:-1] + w[:-2, 1:-1]) / (hy * hy)
    kxy[1:-1, 1:-1] = (
        w[2:, 2:] - w[2:, :-2] - w[:-2, 2:] + w[:-2, :-2]
    ) / (4 * hx * hy)

    if plan.simulation.model == "mindlin_q4":
        fe_res = solve_mindlin(plan, cal)
        pass_results: List[Dict[str, float]] = []
        total_energy = 0.0
        plate_ctx = PlateContext(thickness_mm=plan.plate.thickness, steel_factor=plan.plate.material.steel_factor)
        for p in sorted(plan.passes, key=lambda p: p.sequence_index):
            res = compute_shrinkage(p, plate_ctx, cal)
            p.derived_line_energy_J_mm = res["line_energy_J_per_mm"]
            p.derived_shrinkage_eps = res["shrinkage_eps"]
            p.effective_width_mm = res["effective_width_mm"]
            total_energy += res["line_energy_J_per_mm"] * p.process.footprint_width_mm
            pass_results.append({"pass_id": p.id, **res})

        note = "Mindlin Q4 solve with reduced shear; boundary per simulation setting."
        field = FieldResult(
            x=fe_res.x,
            y=fe_res.y,
            w=fe_res.w,
            kappa_x=fe_res.kappa_x,
            kappa_y=fe_res.kappa_y,
            kappa_xy=fe_res.kappa_xy,
        )
        return SolveResult(field=field, pass_results=pass_results, total_line_energy_J=total_energy, note=note)

    # Fallback: biharmonic simplified
    x, y = _structured_grid(plan.plate.length, plan.plate.width, plan.plate.mesh_size)
    hx = float(x[1] - x[0]) if x.size > 1 else 1.0
    hy = float(y[1] - y[0]) if y.size > 1 else 1.0

    load = _band_load(x, y, plan.lines, plan, cal)

    nx, ny = x.size, y.size
    A = _build_biharmonic_matrix(nx, ny, hx, hy)

    rhs = load[1:-1, 1:-1].ravel()
    w_int = spla.spsolve(A, rhs)
    w = np.zeros((ny, nx))
    w[1:-1, 1:-1] = w_int.reshape((ny - 2, nx - 2))

    # Curvatures via second derivatives (central differences); zero at boundary
    kx = np.zeros_like(w)
    ky = np.zeros_like(w)
    kxy = np.zeros_like(w)
    kx[1:-1, 1:-1] = (w[1:-1, 2:] - 2 * w[1:-1, 1:-1] + w[1:-1, :-2]) / (hx * hx)
    ky[1:-1, 1:-1] = (w[2:, 1:-1] - 2 * w[1:-1, 1:-1] + w[:-2, 1:-1]) / (hy * hy)
    kxy[1:-1, 1:-1] = (
        w[2:, 2:] - w[2:, :-2] - w[:-2, 2:] + w[:-2, :-2]
    ) / (4 * hx * hy)

    pass_results: List[Dict[str, float]] = []
    total_energy = 0.0
    plate_ctx = PlateContext(thickness_mm=plan.plate.thickness, steel_factor=plan.plate.material.steel_factor)
    for p in sorted(plan.passes, key=lambda p: p.sequence_index):
        res = compute_shrinkage(p, plate_ctx, cal)
        p.derived_line_energy_J_mm = res["line_energy_J_per_mm"]
        p.derived_shrinkage_eps = res["shrinkage_eps"]
        p.effective_width_mm = res["effective_width_mm"]
        total_energy += res["line_energy_J_per_mm"] * p.process.footprint_width_mm
        pass_results.append({"pass_id": p.id, **res})

    note = (
        "Solved biharmonic plate with shrinkage-band forcing (simplified). "
        "Model uses w=0 Dirichlet edges; upgrade to full FE for accuracy."
    )
    field = FieldResult(x=x, y=y, w=w, kappa_x=kx, kappa_y=ky, kappa_xy=kxy)
    return SolveResult(field=field, pass_results=pass_results, total_line_energy_J=total_energy, note=note)

    note = (
        "Solved biharmonic plate with shrinkage-band forcing (simplified). "
        "Model uses w=0 Dirichlet edges; upgrade to full FE for accuracy."
    )
    field = FieldResult(x=x, y=y, w=w, kappa_x=kx, kappa_y=ky, kappa_xy=kxy)
    return SolveResult(field=field, pass_results=pass_results, total_line_energy_J=total_energy, note=note)
