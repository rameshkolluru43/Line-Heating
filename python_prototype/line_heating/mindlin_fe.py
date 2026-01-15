"""Mindlin/Reissner Q4 plate solver with reduced shear integration (simplified).

This is a structured-grid implementation with 3 DOF per node (w, theta_x, theta_y).
It applies clamped or simply supported edge constraints and maps shrinkage bands to
an equivalent transverse load field (heuristic). This is a first usable FE step; for
production, add membrane DOFs and refined shear/membrane coupling if needed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence, Tuple

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from .models import LineGeometry, Plan
from .shrinkage import Calibration, PlateContext, compute_shrinkage


@dataclass
class Mesh:
    nodes: np.ndarray  # shape (N, 2)
    elements: np.ndarray  # shape (M, 4) for quad connectivity
    nx: int
    ny: int
    hx: float
    hy: float


@dataclass
class FEResult:
    x: np.ndarray
    y: np.ndarray
    w: np.ndarray  # deflection grid shape (ny, nx)
    theta_x: np.ndarray  # rotations grid
    theta_y: np.ndarray
    kappa_x: np.ndarray
    kappa_y: np.ndarray
    kappa_xy: np.ndarray


def build_structured_mesh(Lx: float, Ly: float, h: float) -> Mesh:
    nx = int(np.ceil(Lx / h)) + 1
    ny = int(np.ceil(Ly / h)) + 1
    xs = np.linspace(0.0, Lx, nx)
    ys = np.linspace(0.0, Ly, ny)
    X, Y = np.meshgrid(xs, ys)
    nodes = np.column_stack([X.ravel(), Y.ravel()])

    elems = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            n0 = j * nx + i
            n1 = n0 + 1
            n2 = n0 + nx + 1
            n3 = n0 + nx
            elems.append([n0, n1, n2, n3])
    elements = np.asarray(elems, dtype=int)
    hx = xs[1] - xs[0] if nx > 1 else Lx
    hy = ys[1] - ys[0] if ny > 1 else Ly
    return Mesh(nodes=nodes, elements=elements, nx=nx, ny=ny, hx=hx, hy=hy)


def _gauss_points():
    gp = 1.0 / np.sqrt(3.0)
    xi = np.array([-gp, gp])
    eta = np.array([-gp, gp])
    w = np.array([1.0, 1.0])
    return xi, eta, w


def _shape_functions(xi: float, eta: float):
    N = 0.25 * np.array([
        (1 - xi) * (1 - eta),
        (1 + xi) * (1 - eta),
        (1 + xi) * (1 + eta),
        (1 - xi) * (1 + eta),
    ])
    dN_dxi = 0.25 * np.array([
        -(1 - eta),
        (1 - eta),
        (1 + eta),
        -(1 + eta),
    ])
    dN_deta = 0.25 * np.array([
        -(1 - xi),
        -(1 + xi),
        (1 + xi),
        (1 - xi),
    ])
    return N, dN_dxi, dN_deta


def _element_stiffness_mindlin(hx: float, hy: float, t: float, E: float, nu: float, kappa_s: float = 5.0 / 6.0):
    xi, eta, w = _gauss_points()
    Db = (E * t**3) / (12 * (1 - nu**2)) * np.array(
        [[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]]
    )
    G = E / (2 * (1 + nu))
    Ds = kappa_s * G * t * np.array([[1, 0], [0, 1]])

    ke = np.zeros((12, 12))  # 4 nodes * 3 dof (w, thx, thy)

    # Bending (2x2 integration)
    for i, xi_g in enumerate(xi):
        for j, eta_g in enumerate(eta):
            N, dN_dxi, dN_deta = _shape_functions(xi_g, eta_g)
            J = np.array([[dN_dxi @ np.array([0, hx, hx, 0]), dN_dxi @ np.array([0, 0, hy, hy])],
                          [dN_deta @ np.array([0, hx, hx, 0]), dN_deta @ np.array([0, 0, hy, hy])]])
            # For structured rect elements, J simplifies:
            detJ = hx * hy / 4.0
            invJ = np.array([[2.0 / hx, 0], [0, 2.0 / hy]])
            dN_dx = invJ[0, 0] * dN_dxi + invJ[0, 1] * dN_deta
            dN_dy = invJ[1, 0] * dN_dxi + invJ[1, 1] * dN_deta

            Bb = np.zeros((3, 12))
            for a in range(4):
                Bb[0, a * 3 + 1] = dN_dx[a]  # dtheta_x/dx
                Bb[1, a * 3 + 2] = dN_dy[a]  # dtheta_y/dy
                Bb[2, a * 3 + 1] = dN_dy[a]  # dtheta_x/dy
                Bb[2, a * 3 + 2] = dN_dx[a]  # dtheta_y/dx

            weight = w[i] * w[j]
            ke += Bb.T @ Db @ Bb * detJ * weight

    # Shear (1x1 reduced integration at center xi=eta=0)
    xi_s = eta_s = 0.0
    N, dN_dxi, dN_deta = _shape_functions(xi_s, eta_s)
    detJ = hx * hy / 4.0
    invJ = np.array([[2.0 / hx, 0], [0, 2.0 / hy]])
    dN_dx = invJ[0, 0] * dN_dxi + invJ[0, 1] * dN_deta
    dN_dy = invJ[1, 0] * dN_dxi + invJ[1, 1] * dN_deta

    Bs = np.zeros((2, 12))
    for a in range(4):
        # gamma_xz = theta_x + dw/dx
        Bs[0, a * 3 + 0] = dN_dx[a]
        Bs[0, a * 3 + 1] = N[a]
        # gamma_yz = theta_y + dw/dy
        Bs[1, a * 3 + 0] = dN_dy[a]
        Bs[1, a * 3 + 2] = N[a]

    ke += Bs.T @ Ds @ Bs * detJ
    return ke


def _shrinkage_from_temperature(T_elem: np.ndarray, cal: Calibration) -> np.ndarray:
    """Map elementwise peak temperature (C) to shrinkage strain with capping."""
    T_cap = cal.thermal_cap_C
    T_ref = cal.thermal_ref_C
    eps_ref = cal.thermal_eps_ref
    exp = cal.thermal_exp
    # Normalize between ref and cap; clamp outside.
    norm = max(T_cap - T_ref, 1e-6)
    x = np.clip((np.minimum(T_elem, T_cap) - T_ref) / norm, 0.0, 1.0)
    return eps_ref * (x ** exp)


def _band_load_field(plan: Plan, mesh: Mesh, cal: Calibration, thermal_elem: np.ndarray | None = None) -> np.ndarray:
    """Compute equivalent transverse load per element center.

    If `thermal_elem` is provided (shape ny-1, nx-1), shrinkage is derived from
    peak temperature using calibration thermal parameters and ignores energy law.
    Otherwise, uses the energy-based shrinkage mapping per pass.
    """
    Xc = (mesh.nodes[mesh.elements, 0].mean(axis=1)).reshape(mesh.ny - 1, mesh.nx - 1)
    Yc = (mesh.nodes[mesh.elements, 1].mean(axis=1)).reshape(mesh.ny - 1, mesh.nx - 1)
    load = np.zeros_like(Xc)
    # Plate bending rigidity D [N*mm], using E in MPa (=N/mm^2) and thickness in mm.
    t = plan.plate.thickness
    E = plan.plate.material.E
    nu = plan.plate.material.nu
    D_plate = (E * t**3) / (12.0 * (1.0 - nu * nu))
    plate_ctx = PlateContext(thickness_mm=plan.plate.thickness, steel_factor=plan.plate.material.steel_factor)

    if thermal_elem is not None:
        if thermal_elem.shape != load.shape:
            raise ValueError(f"thermal_elem shape {thermal_elem.shape} must match (ny-1,nx-1) {load.shape}")
        # Use the first pass footprint as effective width (simplification); if absent, default to mesh size.
        width = plan.passes[0].process.footprint_width_mm if plan.passes else min(mesh.hx, mesh.hy)
        line = plan.lines[0] if plan.lines else LineGeometry(id="L0", name="auto", points=[(0, 0), (plan.plate.length, plan.plate.width / 2)])
        side_sign = -1.0 if line.heated_side == "+z" else 1.0
        eps_elem = _shrinkage_from_temperature(thermal_elem, cal)
        q_equiv = side_sign * D_plate * (eps_elem / max(1e-6, width))
        load += cal.load_scale * q_equiv
        return load

    for p in sorted(plan.passes, key=lambda p: p.sequence_index):
        res = compute_shrinkage(p, plate_ctx, cal)
        p.derived_line_energy_J_mm = res["line_energy_J_per_mm"]
        p.derived_shrinkage_eps = res["shrinkage_eps"]
        p.effective_width_mm = res["effective_width_mm"]
        line = next((ln for ln in plan.lines if ln.id == p.line_id), None)
        if line is None or len(line.points) < 2:
            continue
        width = max(1e-6, res["effective_width_mm"])
        dist = _distance_to_polyline_centers(Xc, Yc, line)
        if plan.simulation.band_profile == "gaussian":
            sigma = plan.simulation.sigma_mm or (0.5 * width)
            weight = np.exp(-0.5 * (dist / sigma) ** 2)
        else:
            weight = (dist <= width * 0.5).astype(float)
        # Sign: heat on +z should bend toward -z; use -1 for +z, +1 for -z.
        side_sign = -1.0 if line.heated_side == "+z" else 1.0
        # Convert imposed shrinkage curvature (~eps/width) to an equivalent transverse load
        # by scaling with plate bending rigidity; load_scale is the only calibration factor.
        q_equiv = side_sign * D_plate * (res["shrinkage_eps"] / width)
        load += cal.load_scale * q_equiv * weight
    return load


def _distance_to_polyline_centers(xc: np.ndarray, yc: np.ndarray, line: LineGeometry) -> np.ndarray:
    dist2 = np.full_like(xc, np.inf, dtype=float)
    for p0, p1 in _pairwise(line.points):
        v = p1 - p0
        seg_len2 = np.dot(v, v)
        if seg_len2 == 0:
            d2 = (xc - p0[0]) ** 2 + (yc - p0[1]) ** 2
            dist2 = np.minimum(dist2, d2)
            continue
        t = ((xc - p0[0]) * v[0] + (yc - p0[1]) * v[1]) / seg_len2
        t = np.clip(t, 0.0, 1.0)
        proj_x = p0[0] + t * v[0]
        proj_y = p0[1] + t * v[1]
        d2 = (xc - proj_x) ** 2 + (yc - proj_y) ** 2
        dist2 = np.minimum(dist2, d2)
    return np.sqrt(dist2)


def _pairwise(points: Sequence[Tuple[float, float]]):
    for a, b in zip(points[:-1], points[1:]):
        yield np.asarray(a, dtype=float), np.asarray(b, dtype=float)


def assemble_global(mesh: Mesh, plan: Plan, cal: Calibration, thermal_elem: np.ndarray | None = None) -> Tuple[sp.csr_matrix, np.ndarray]:
    ke = _element_stiffness_mindlin(mesh.hx, mesh.hy, plan.plate.thickness, plan.plate.material.E, plan.plate.material.nu)
    ndof = mesh.nodes.shape[0] * 3
    K = sp.lil_matrix((ndof, ndof))
    f = np.zeros(ndof)

    # Element load from shrinkage as equivalent uniform transverse load
    q_elem = _band_load_field(plan, mesh, cal, thermal_elem=thermal_elem)  # shape (ny-1, nx-1)

    for e_idx, conn in enumerate(mesh.elements):
        dof_indices = []
        for n in conn:
            base = n * 3
            dof_indices.extend([base, base + 1, base + 2])
        dof_indices = np.array(dof_indices)
        K[np.ix_(dof_indices, dof_indices)] += ke

        # Consistent load: distribute q*A/4 to each node's w DOF
        a_elem = mesh.hx * mesh.hy
        q = q_elem.ravel()[e_idx]
        fe_local = np.zeros(12)
        fe_local[0::3] = q * a_elem / 4.0
        f[dof_indices] += fe_local

    return K.tocsr(), f


def apply_boundary_conditions(K: sp.csr_matrix, f: np.ndarray, mesh: Mesh, bc_type: str) -> Tuple[sp.csr_matrix, np.ndarray]:
    constrained = []
    nx, ny = mesh.nx, mesh.ny
    if bc_type == "free":
        # Free edges still have rigid-body modes; pin one reference node (w, thx, thy)
        ref = 0
        constrained = np.array([ref * 3 + 0, ref * 3 + 1, ref * 3 + 2], dtype=int)
        free = np.setdiff1d(np.arange(K.shape[0]), constrained)
        Kff = K[free][:, free]
        ff = f[free] - K[free][:, constrained] @ np.zeros_like(constrained, dtype=float)
        return Kff, ff, free, constrained

    if bc_type in ("corners_simply", "corners_clamped"):
        corner_nodes = [
            0,  # (0,0)
            nx - 1,  # (Lx,0)
            (ny - 1) * nx,  # (0,Ly)
            (ny - 1) * nx + (nx - 1),  # (Lx,Ly)
        ]
        for n in corner_nodes:
            w_dof = n * 3
            thx_dof = w_dof + 1
            thy_dof = w_dof + 2
            constrained.append(w_dof)
            if bc_type == "corners_clamped":
                constrained.extend([thx_dof, thy_dof])
        if bc_type == "corners_simply":
            # Minimal stabilization to remove rigid rotations: pin one corner's rotations.
            n0 = corner_nodes[0]
            constrained.extend([n0 * 3 + 1, n0 * 3 + 2])
        constrained = np.unique(np.array(constrained, dtype=int))
        free = np.setdiff1d(np.arange(K.shape[0]), constrained)
        Kff = K[free][:, free]
        ff = f[free] - K[free][:, constrained] @ np.zeros_like(constrained, dtype=float)
        return Kff, ff, free, constrained

    for j in range(ny):
        for i in range(nx):
            if j in (0, ny - 1) or i in (0, nx - 1):
                n = j * nx + i
                w_dof = n * 3
                thx_dof = w_dof + 1
                thy_dof = w_dof + 2
                constrained.append(w_dof)
                if bc_type == "clamped":
                    constrained.extend([thx_dof, thy_dof])
                elif bc_type != "simply":
                    raise ValueError(f"Unknown boundary_condition: {bc_type}")
    if not constrained:
        free = np.arange(K.shape[0])
        return K, f, free, np.array([], dtype=int)

    constrained = np.unique(np.array(constrained, dtype=int))
    free = np.setdiff1d(np.arange(K.shape[0]), constrained)

    Kff = K[free][:, free]
    Kfc = K[free][:, constrained]
    ff = f[free] - Kfc @ np.zeros_like(constrained, dtype=float)
    return Kff, ff, free, constrained


def solve_mindlin(plan: Plan, calibration: Calibration | None = None) -> FEResult:
    cal = calibration or Calibration()
    mesh = build_structured_mesh(plan.plate.length, plan.plate.width, plan.plate.mesh_size)

    K, f = assemble_global(mesh, plan, cal)
    bc_type = plan.simulation.boundary_condition
    Kff, ff, free, constrained = apply_boundary_conditions(K, f, mesh, bc_type)

    # Small diagonal regularization to tame near-singular systems (e.g., corner-only supports)
    diag_max = float(np.abs(Kff.diagonal()).max()) if Kff.shape[0] else 0.0
    reg = cal.reg_diag_scale * (diag_max if diag_max > 0 else 1.0)
    if reg > 0:
        Kff = Kff + reg * sp.eye(Kff.shape[0], format="csr")

    wtc = np.zeros(K.shape[0])
    wtc[free] = spla.spsolve(Kff, ff)

    w_grid = wtc[0::3].reshape(mesh.ny, mesh.nx)
    thx_grid = wtc[1::3].reshape(mesh.ny, mesh.nx)
    thy_grid = wtc[2::3].reshape(mesh.ny, mesh.nx)

    hx, hy = mesh.hx, mesh.hy
    kx = np.zeros_like(w_grid)
    ky = np.zeros_like(w_grid)
    kxy = np.zeros_like(w_grid)
    kx[:, 1:-1] = (thx_grid[:, 2:] - thx_grid[:, :-2]) / (2 * hx)
    ky[1:-1, :] = (thy_grid[2:, :] - thy_grid[:-2, :]) / (2 * hy)
    kxy[1:-1, 1:-1] = (
        (thx_grid[2:, 1:-1] - thx_grid[:-2, 1:-1]) / (2 * hy)
        + (thy_grid[1:-1, 2:] - thy_grid[1:-1, :-2]) / (2 * hx)
    )

    xs = mesh.nodes[:, 0].reshape(mesh.ny, mesh.nx)[0, :]
    ys = mesh.nodes[:, 1].reshape(mesh.ny, mesh.nx)[:, 0]

    return FEResult(
        x=xs,
        y=ys,
        w=w_grid,
        theta_x=thx_grid,
        theta_y=thy_grid,
        kappa_x=kx,
        kappa_y=ky,
        kappa_xy=kxy,
    )


def solve_mindlin_with_temperature(plan: Plan, thermal_elem: np.ndarray, calibration: Calibration | None = None) -> FEResult:
    """Solve Mindlin plate using a provided elementwise peak temperature field.

    `thermal_elem` must be shaped (ny-1, nx-1) matching the structured mesh built from
    plate dimensions and mesh_size. Shrinkage is derived from temperature using Calibration
    thermal parameters.
    """
    cal = calibration or Calibration()
    mesh = build_structured_mesh(plan.plate.length, plan.plate.width, plan.plate.mesh_size)

    K, f = assemble_global(mesh, plan, cal, thermal_elem=thermal_elem)
    bc_type = plan.simulation.boundary_condition
    Kff, ff, free, constrained = apply_boundary_conditions(K, f, mesh, bc_type)

    # Small diagonal regularization to tame near-singular systems when thermal loads are applied
    diag_max = float(np.abs(Kff.diagonal()).max()) if Kff.shape[0] else 0.0
    reg = cal.reg_diag_scale * (diag_max if diag_max > 0 else 1.0)
    if reg > 0:
        Kff = Kff + reg * sp.eye(Kff.shape[0], format="csr")

    wtc = np.zeros(K.shape[0])
    wtc[free] = spla.spsolve(Kff, ff)

    w_grid = wtc[0::3].reshape(mesh.ny, mesh.nx)
    thx_grid = wtc[1::3].reshape(mesh.ny, mesh.nx)
    thy_grid = wtc[2::3].reshape(mesh.ny, mesh.nx)

    hx, hy = mesh.hx, mesh.hy
    kx = np.zeros_like(w_grid)
    ky = np.zeros_like(w_grid)
    kxy = np.zeros_like(w_grid)
    kx[:, 1:-1] = (thx_grid[:, 2:] - thx_grid[:, :-2]) / (2 * hx)
    ky[1:-1, :] = (thy_grid[2:, :] - thy_grid[:-2, :]) / (2 * hy)
    kxy[1:-1, 1:-1] = (
        (thx_grid[2:, 1:-1] - thx_grid[:-2, 1:-1]) / (2 * hy)
        + (thy_grid[1:-1, 2:] - thy_grid[1:-1, :-2]) / (2 * hx)
    )

    xs = mesh.nodes[:, 0].reshape(mesh.ny, mesh.nx)[0, :]
    ys = mesh.nodes[:, 1].reshape(mesh.ny, mesh.nx)[:, 0]

    return FEResult(
        x=xs,
        y=ys,
        w=w_grid,
        theta_x=thx_grid,
        theta_y=thy_grid,
        kappa_x=kx,
        kappa_y=ky,
        kappa_xy=kxy,
    )
