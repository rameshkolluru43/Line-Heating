    """Inherent-strain (eigenstrain) helpers for fast plate bending demos.

This module provides a minimal mapping from line-level inherent deformation
parameters (Tx, Ty, Bx, By, width) into an equivalent transverse load field
for a plate bending solve. It is a reduced-order approximation: we turn the
imposed curvature/shrinkage into an effective transverse load using the plate
bending rigidity. This keeps units consistent with the existing biharmonic
prototype without implementing a full membrane + bending eigenstrain solver.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Sequence, Tuple

import numpy as np

from .mindlin_fe import (
    FEResult,
    _element_stiffness_mindlin,
    _gauss_points,
    _shape_functions,
    apply_boundary_conditions,
    build_structured_mesh,
    _distance_to_polyline_centers,
)
from .models import LineGeometry, Plate


def _pairwise(points: Sequence[Tuple[float, float]]):
    for a, b in zip(points[:-1], points[1:]):
        yield np.asarray(a, dtype=float), np.asarray(b, dtype=float)


def _distance_to_polyline(X: np.ndarray, Y: np.ndarray, line: LineGeometry) -> np.ndarray:
    """Minimum distance from each (X,Y) point to the polyline defined by line.points."""
    dist2 = np.full_like(X, np.inf, dtype=float)
    for p0, p1 in _pairwise(line.points):
        v = p1 - p0
        seg_len2 = float(np.dot(v, v))
        if seg_len2 == 0.0:
            d2 = (X - p0[0]) ** 2 + (Y - p0[1]) ** 2
            dist2 = np.minimum(dist2, d2)
            continue
        t = ((X - p0[0]) * v[0] + (Y - p0[1]) * v[1]) / seg_len2
        t = np.clip(t, 0.0, 1.0)
        proj_x = p0[0] + t * v[0]
        proj_y = p0[1] + t * v[1]
        d2 = (X - proj_x) ** 2 + (Y - proj_y) ** 2
        dist2 = np.minimum(dist2, d2)
    return np.sqrt(dist2)


def _line_orientation(line: LineGeometry) -> float:
    """Orientation angle (radians) from first to last point; fallback 0 if degenerate."""
    if len(line.points) < 2:
        return 0.0
    p0 = np.asarray(line.points[0], dtype=float)
    p1 = np.asarray(line.points[-1], dtype=float)
    vec = p1 - p0
    if np.allclose(vec, 0.0):
        return 0.0
    return float(np.arctan2(vec[1], vec[0]))


def _rotate_curvatures(kx: float, ky: float, theta: float) -> Tuple[float, float, float]:
    """Rotate principal curvatures (kx, ky) by theta to global (kx, ky, kxy)."""
    c = np.cos(theta)
    s = np.sin(theta)
    kx_g = kx * c * c + ky * s * s
    ky_g = kx * s * s + ky * c * c
    kxy_g = 2.0 * (ky - kx) * s * c
    return kx_g, ky_g, kxy_g


@dataclass
class InherentStrainParams:
    """Per-line inherent deformation parameters (simplified).

    Tx, Ty: in-plane shrinkage components (dimensionless strain).
    Bx, By: bending components (radians of angular change over the band thickness scale).
    width_mm: width of the band where the eigenstrain is imposed.
    theta_rad: orientation of the line relative to global x (for future rotation; not used here).
    """

    Tx: float
    Ty: float
    Bx: float
    By: float
    width_mm: float
    theta_rad: Optional[float] = None


def band_load_from_inherent(
    x: np.ndarray,
    y: np.ndarray,
    plate: Plate,
    line: LineGeometry,
    params: InherentStrainParams,
) -> np.ndarray:
    """Create an equivalent transverse load field from inherent strains for one line.

    This reduced model collapses the bending components (Bx, By) into an
    effective curvature k_eff ~ (Bx + By) / width and scales by plate bending
    rigidity D. Shrinkage (Tx, Ty) is folded in as a membrane-like curvature
    surrogate to keep a simple scalar loading. The sign follows heated_side:
    +z heating bends toward -z.
    """

    X, Y = np.meshgrid(x, y)
    dist = _distance_to_polyline(X, Y, line)
    weight = (dist <= params.width_mm * 0.5).astype(float)

    t = plate.thickness
    E = plate.material.E
    nu = plate.material.nu
    D_plate = (E * t ** 3) / (12.0 * (1.0 - nu * nu))

    # Effective curvature surrogate (very reduced-order)
    k_eff = (params.Bx + params.By) / max(1e-6, params.width_mm)
    # Fold shrinkage into the same surrogate to show effect in w (approximate)
    k_eff += 0.5 * (params.Tx + params.Ty) / max(1e-6, params.width_mm)

    side_sign = -1.0 if line.heated_side == "+z" else 1.0
    q_equiv = side_sign * D_plate * k_eff * weight
    return q_equiv


def assemble_load_from_lines(
    x: np.ndarray,
    y: np.ndarray,
    plate: Plate,
    lines: List[LineGeometry],
    params_per_line: List[InherentStrainParams],
) -> np.ndarray:
    """Sum equivalent transverse load fields for all lines."""
    load = np.zeros((y.size, x.size))
    for ln, pr in zip(lines, params_per_line):
        load += band_load_from_inherent(x, y, plate, ln, pr)
    return load


def kappa_fields_for_mesh(
    Xc: np.ndarray,
    Yc: np.ndarray,
    plate: Plate,
    lines: List[LineGeometry],
    params_per_line: List[InherentStrainParams],
    profile: Literal["top_hat", "gaussian"] = "top_hat",
    sigma_mm: float | None = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute imposed curvature tensors (kx, ky, kxy) at element centers.

    Maps the linear-through-thickness inherent strains (S±B) to equivalent
    target curvatures: kx = -2*Bx/t, ky = -2*By/t. Components are rotated by
    theta_rad if provided, otherwise the line orientation.
    """

    kx0 = np.zeros_like(Xc)
    ky0 = np.zeros_like(Yc)
    kxy0 = np.zeros_like(Xc)
    t = plate.thickness

    for ln, pr in zip(lines, params_per_line):
        width = max(1e-6, pr.width_mm)
        dist = _distance_to_polyline_centers(Xc, Yc, ln)
        if profile == "gaussian":
            sigma = sigma_mm or (0.5 * width)
            weight = np.exp(-0.5 * (dist / sigma) ** 2)
        else:
            weight = (dist <= width * 0.5).astype(float)

        theta = pr.theta_rad if pr.theta_rad is not None else _line_orientation(ln)
        kx_local = -2.0 * pr.Bx / t
        ky_local = -2.0 * pr.By / t
        kx_g, ky_g, kxy_g = _rotate_curvatures(kx_local, ky_local, theta)

        kx0 += weight * kx_g
        ky0 += weight * ky_g
        kxy0 += weight * kxy_g

    return kx0, ky0, kxy0


def _element_eigen_load(hx: float, hy: float, t: float, E: float, nu: float, kappa_vec: Tuple[float, float, float]) -> np.ndarray:
    """Consistent nodal load vector for imposed curvature (kx, ky, kxy) on a Mindlin Q4.

    Uses the bending B matrix and Db to compute fe = ∫ Bb^T Db kappa0 dA.
    """

    xi_g, eta_g, w_g = _gauss_points()
    Db = (E * t**3) / (12 * (1 - nu**2)) * np.array(
        [[1, nu, 0], [nu, 1, 0], [0, 0, (1 - nu) / 2]]
    )
    fe = np.zeros(12)

    for i, xi in enumerate(xi_g):
        for j, eta in enumerate(eta_g):
            N, dN_dxi, dN_deta = _shape_functions(float(xi), float(eta))
            detJ = hx * hy / 4.0
            invJ = np.array([[2.0 / hx, 0], [0, 2.0 / hy]])
            dN_dx = invJ[0, 0] * dN_dxi + invJ[0, 1] * dN_deta
            dN_dy = invJ[1, 0] * dN_dxi + invJ[1, 1] * dN_deta

            Bb = np.zeros((3, 12))
            for a in range(4):
                Bb[0, a * 3 + 1] = dN_dx[a]
                Bb[1, a * 3 + 2] = dN_dy[a]
                Bb[2, a * 3 + 1] = dN_dy[a]
                Bb[2, a * 3 + 2] = dN_dx[a]

            weight = w_g[i] * w_g[j]
            fe += Bb.T @ (Db @ np.asarray(kappa_vec, dtype=float)) * detJ * weight

    return fe


def solve_inherent_mindlin(
    plate: Plate,
    lines: List[LineGeometry],
    params_per_line: List[InherentStrainParams],
    mesh_size_mm: float = 20.0,
    boundary_condition: str = "simply",
    profile: Literal["top_hat", "gaussian"] = "top_hat",
    sigma_mm: float | None = None,
) -> FEResult:
    """Solve plate bending with imposed inherent-strain curvatures using Mindlin Q4.

    This maps (Bx, By) to target curvature fields and applies them as initial
    curvature loads (Bb^T Db kappa0). Tx, Ty are ignored here because the
    current plate formulation does not include membrane DOFs.
    """

    mesh = build_structured_mesh(plate.length, plate.width, mesh_size_mm)

    kx0, ky0, kxy0 = kappa_fields_for_mesh(
        Xc=(mesh.nodes[mesh.elements, 0].mean(axis=1)).reshape(mesh.ny - 1, mesh.nx - 1),
        Yc=(mesh.nodes[mesh.elements, 1].mean(axis=1)).reshape(mesh.ny - 1, mesh.nx - 1),
        plate=plate,
        lines=lines,
        params_per_line=params_per_line,
        profile=profile,
        sigma_mm=sigma_mm,
    )

    ke = _element_stiffness_mindlin(mesh.hx, mesh.hy, plate.thickness, plate.material.E, plate.material.nu)
    ndof = mesh.nodes.shape[0] * 3
    import scipy.sparse as sp

    K = sp.lil_matrix((ndof, ndof))
    f = np.zeros(ndof)

    for e_idx, conn in enumerate(mesh.elements):
        dof_indices = []
        for n in conn:
            base = n * 3
            dof_indices.extend([base, base + 1, base + 2])
        dof_indices = np.array(dof_indices)

        K[np.ix_(dof_indices, dof_indices)] += ke

        # Imposed curvature load (consistent nodal forces)
        fe_local = _element_eigen_load(
            mesh.hx,
            mesh.hy,
            plate.thickness,
            plate.material.E,
            plate.material.nu,
            (kx0.ravel()[e_idx], ky0.ravel()[e_idx], kxy0.ravel()[e_idx]),
        )
        f[dof_indices] += fe_local

    # Apply BCs using existing helper
    K_sparse = K.tocsr()
    Kff, ff, free, constrained = apply_boundary_conditions(K_sparse, f, mesh, boundary_condition)

    import scipy.sparse.linalg as spla

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
