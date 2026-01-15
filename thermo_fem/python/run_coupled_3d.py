"""3D coupled thermo-mechanical line-heating demo.

What this script does:
- Builds a 3D tet4 Gmsh mesh of a plate, with local refinement in a band around
    the heating line (top surface, configurable y).
- Solves transient 3D heat diffusion with a moving Gaussian surface heat flux and
  convection on top/bottom surfaces.
- Solves 3D linear thermoelasticity (C++/pybind in thermo_bindings).
- Writes plots and ParaView files.

Notes:
- In this workspace, use python3.11 (python3.14 currently cannot import numpy).
- Units are consistent in mm, s, K, MPa (N/mm^2).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import matplotlib.pyplot as plt
import gmsh


# Add C++ bindings to path (built under thermo_fem/build/cpp)
sys.path.insert(0, str(Path(__file__).parent.parent / "build" / "cpp"))
try:
    import thermo_bindings  # type: ignore
except Exception as exc:  # pragma: no cover
    raise ImportError(
        "Failed to import thermo_bindings. Build the C++ extension under thermo_fem/build/cpp first. "
        "(Use python3.11 in this repo.)"
    ) from exc


def write_vtk_unstructured_grid(
    file_path: Path,
    nodes: np.ndarray,
    tet: np.ndarray,
    point_data: dict[str, np.ndarray],
) -> None:
    """Write legacy VTK unstructured grid with tetrahedra."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    n_points = int(nodes.shape[0])
    n_cells = int(tet.shape[0])

    with file_path.open("w", encoding="utf-8") as f:
        f.write("# vtk DataFile Version 3.0\n")
        f.write("thermo_fem results\n")
        f.write("ASCII\n")
        f.write("DATASET UNSTRUCTURED_GRID\n")

        f.write(f"POINTS {n_points} float\n")
        for p in nodes:
            f.write(f"{p[0]:.9g} {p[1]:.9g} {p[2]:.9g}\n")

        f.write(f"CELLS {n_cells} {n_cells * 5}\n")
        for c in tet:
            f.write(f"4 {int(c[0])} {int(c[1])} {int(c[2])} {int(c[3])}\n")

        f.write(f"CELL_TYPES {n_cells}\n")
        for _ in range(n_cells):
            f.write("10\n")

        if not point_data:
            return

        f.write(f"POINT_DATA {n_points}\n")
        for name, arr in point_data.items():
            arr = np.asarray(arr)
            if arr.ndim == 1:
                f.write(f"SCALARS {name} float 1\n")
                f.write("LOOKUP_TABLE default\n")
                for v in arr:
                    f.write(f"{float(v):.9g}\n")
            elif arr.ndim == 2 and arr.shape[1] == 3:
                f.write(f"VECTORS {name} float\n")
                for v in arr:
                    f.write(f"{float(v[0]):.9g} {float(v[1]):.9g} {float(v[2]):.9g}\n")
            else:
                raise ValueError(f"Unsupported VTK point_data shape for {name}: {arr.shape}")


def _triangle_area_3d(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    return 0.5 * float(np.linalg.norm(np.cross(b - a, c - a)))


def build_plate_mesh_3d(
    Lx: float,
    Ly: float,
    thickness: float,
    h: float,
    h_refine: float | None,
    refine_band: float,
    heat_ys: list[float] | None,
    out_dir: Path,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Create 3D plate mesh (tet4) with a refinement band around the heating line."""
    if h_refine is None:
        h_refine = h / 3.0

    out_dir.mkdir(parents=True, exist_ok=True)

    gmsh.initialize()
    try:
        gmsh.model.add("plate_3d")

        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", float(min(h_refine, h)))
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", float(max(h_refine, h)))

        gmsh.model.occ.addBox(0.0, 0.0, 0.0, float(Lx), float(Ly), float(thickness))

        # Create OCC curve(s) along the heating line(s) on the top face.
        if not heat_ys:
            heat_ys = [float(Ly / 2.0)]

        heating_curves: list[int] = []
        for y in heat_ys:
            p1 = gmsh.model.occ.addPoint(0.0, float(y), float(thickness), float(h_refine))
            p2 = gmsh.model.occ.addPoint(float(Lx), float(y), float(thickness), float(h_refine))
            heating_curves.append(int(gmsh.model.occ.addLine(p1, p2)))

        gmsh.model.occ.synchronize()

        dist = gmsh.model.mesh.field.add("Distance")
        gmsh.model.mesh.field.setNumbers(dist, "CurvesList", heating_curves)
        gmsh.model.mesh.field.setNumber(dist, "Sampling", 200)

        thr = gmsh.model.mesh.field.add("Threshold")
        gmsh.model.mesh.field.setNumber(thr, "InField", dist)
        gmsh.model.mesh.field.setNumber(thr, "SizeMin", float(h_refine))
        gmsh.model.mesh.field.setNumber(thr, "SizeMax", float(h))
        gmsh.model.mesh.field.setNumber(thr, "DistMin", float(refine_band))
        gmsh.model.mesh.field.setNumber(thr, "DistMax", float(3.0 * refine_band))
        gmsh.model.mesh.field.setAsBackgroundMesh(thr)

        gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
        gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)

        gmsh.model.mesh.generate(3)
        gmsh.write(str(out_dir / "mesh.msh"))

        node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
        node_tags = np.asarray(node_tags, dtype=int)
        nodes_all = np.asarray(node_coords, dtype=float).reshape(-1, 3)
        tag_to_all_index = {int(t): int(i) for i, t in enumerate(node_tags)}

        elem_types, _, elem_node_tags = gmsh.model.mesh.getElements(dim=3)
        elem_types = np.asarray(elem_types, dtype=int)
        if not np.any(elem_types == 4):
            raise RuntimeError("Expected tet4 elements (type 4) but none were found")
        tet_idx = int(np.where(elem_types == 4)[0][0])
        tet_tags = np.asarray(elem_node_tags[tet_idx], dtype=int).reshape(-1, 4)
        tet = np.fromiter((tag_to_all_index[int(t)] for t in tet_tags.ravel()), dtype=int).reshape(-1, 4)

        surf_types, _, surf_node_tags = gmsh.model.mesh.getElements(dim=2)
        surf_types = np.asarray(surf_types, dtype=int)
        tri = np.empty((0, 3), dtype=int)
        if np.any(surf_types == 2):
            tri_idx = int(np.where(surf_types == 2)[0][0])
            tri_tags = np.asarray(surf_node_tags[tri_idx], dtype=int).reshape(-1, 3)
            tri = np.fromiter((tag_to_all_index[int(t)] for t in tri_tags.ravel()), dtype=int).reshape(-1, 3)

    finally:
        gmsh.finalize()

    # Compact to only nodes referenced by volume elements.
    used = np.unique(tet.ravel())
    all_to_used = -np.ones(nodes_all.shape[0], dtype=int)
    all_to_used[used] = np.arange(used.size, dtype=int)

    nodes = nodes_all[used]
    tet = all_to_used[tet]

    if tri.size:
        tri = all_to_used[tri]
        tri = tri[np.all(tri >= 0, axis=1)]

    tol_z = max(1e-9, thickness * 1e-3)
    top_nodes = np.where(nodes[:, 2] > thickness - tol_z)[0]
    bottom_nodes = np.where(nodes[:, 2] < tol_z)[0]

    if tri.shape[0] > 0:
        z_tri = nodes[tri, 2]
        top_tri = tri[np.all(z_tri > thickness - tol_z, axis=1)]
        bottom_tri = tri[np.all(z_tri < tol_z, axis=1)]
    else:
        top_tri = np.empty((0, 3), dtype=int)
        bottom_tri = np.empty((0, 3), dtype=int)

    return nodes, tet, top_nodes, bottom_nodes, top_tri, bottom_tri


def assemble_heat_3d(
    nodes: np.ndarray,
    tet: np.ndarray,
    conductivity: float,
    density: float,
    heat_capacity: float,
) -> tuple[sp.csr_matrix, np.ndarray]:
    """Assemble 3D conduction stiffness K and lumped mass M for tet4."""
    n_nodes = int(nodes.shape[0])
    data: list[float] = []
    rows: list[int] = []
    cols: list[int] = []
    mass_lumped = np.zeros(n_nodes, dtype=float)

    dN_ref = np.array(
        [
            [-1.0, -1.0, -1.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )

    for el in tet:
        coords = nodes[el]
        J = np.column_stack((coords[1] - coords[0], coords[2] - coords[0], coords[3] - coords[0]))
        detJ = float(np.linalg.det(J))
        vol = abs(detJ) / 6.0
        if vol <= 0.0:
            continue

        gradN = dN_ref @ np.linalg.inv(J)
        for a in range(4):
            for b in range(4):
                data.append(conductivity * vol * float(np.dot(gradN[a], gradN[b])))
                rows.append(int(el[a]))
                cols.append(int(el[b]))

        m = density * heat_capacity * vol / 4.0
        for a in range(4):
            mass_lumped[int(el[a])] += m

    K = sp.coo_matrix((data, (rows, cols)), shape=(n_nodes, n_nodes)).tocsr()
    return K, mass_lumped


def _k_of_T(T: np.ndarray, k0: float, k_slope: float, T_ref: float) -> np.ndarray:
    return k0 * (1.0 + k_slope * (np.asarray(T, dtype=float) - float(T_ref)))


def _cp_of_T(T: np.ndarray, cp0: float, cp_slope: float, T_ref: float) -> np.ndarray:
    return cp0 * (1.0 + cp_slope * (np.asarray(T, dtype=float) - float(T_ref)))


def assemble_heat_3d_temp_dependent(
    nodes: np.ndarray,
    tet: np.ndarray,
    k0: float,
    k_slope: float,
    rho: float,
    cp0: float,
    cp_slope: float,
    T: np.ndarray,
    T_ref: float,
) -> tuple[sp.csr_matrix, np.ndarray]:
    """Assemble K(T) and M(T) using element-averaged temperature.

    This is a simple Picard-style (fixed-point) linearization that is good enough
    for sweeps and demonstration purposes.
    """
    n_nodes = int(nodes.shape[0])
    data: list[float] = []
    rows: list[int] = []
    cols: list[int] = []
    mass_lumped = np.zeros(n_nodes, dtype=float)

    dN_ref = np.array(
        [
            [-1.0, -1.0, -1.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )

    T = np.asarray(T, dtype=float)
    for el in tet:
        coords = nodes[el]
        J = np.column_stack((coords[1] - coords[0], coords[2] - coords[0], coords[3] - coords[0]))
        detJ = float(np.linalg.det(J))
        vol = abs(detJ) / 6.0
        if vol <= 0.0:
            continue

        T_elem = 0.25 * float(T[int(el[0])] + T[int(el[1])] + T[int(el[2])] + T[int(el[3])])
        k_elem = float(_k_of_T(np.array([T_elem]), k0, k_slope, T_ref)[0])
        cp_elem = float(_cp_of_T(np.array([T_elem]), cp0, cp_slope, T_ref)[0])

        gradN = dN_ref @ np.linalg.inv(J)
        for a in range(4):
            for b in range(4):
                data.append(k_elem * vol * float(np.dot(gradN[a], gradN[b])))
                rows.append(int(el[a]))
                cols.append(int(el[b]))

        m = rho * cp_elem * vol / 4.0
        for a in range(4):
            mass_lumped[int(el[a])] += m

    K = sp.coo_matrix((data, (rows, cols)), shape=(n_nodes, n_nodes)).tocsr()
    return K, mass_lumped


def assemble_convection_on_triangles(
    nodes: np.ndarray,
    tri: np.ndarray,
    h_conv: float,
    ambient_temperature: float,
) -> tuple[sp.csr_matrix, np.ndarray]:
    """Robin BC on a surface triangulation: q = h (T - T_inf)."""
    n = int(nodes.shape[0])
    if tri.size == 0 or h_conv == 0.0:
        return sp.csr_matrix((n, n)), np.zeros(n, dtype=float)

    rhs = np.zeros(n, dtype=float)
    data: list[float] = []
    rows: list[int] = []
    cols: list[int] = []

    Mhat = np.array([[2, 1, 1], [1, 2, 1], [1, 1, 2]], dtype=float) / 12.0

    for t in tri:
        i0, i1, i2 = (int(t[0]), int(t[1]), int(t[2]))
        a, b, c = nodes[i0], nodes[i1], nodes[i2]
        area = _triangle_area_3d(a, b, c)
        if area <= 0.0:
            continue

        k_loc = h_conv * area
        idx = [i0, i1, i2]
        for a_loc in range(3):
            for b_loc in range(3):
                rows.append(idx[a_loc])
                cols.append(idx[b_loc])
                data.append(k_loc * Mhat[a_loc, b_loc])

        # ∫ h T_inf N_i dS = h*T_inf*area/3
        rhs[i0] += h_conv * ambient_temperature * area / 3.0
        rhs[i1] += h_conv * ambient_temperature * area / 3.0
        rhs[i2] += h_conv * ambient_temperature * area / 3.0

    Kb = sp.coo_matrix((data, (rows, cols)), shape=(n, n)).tocsr()
    return Kb, rhs


def assemble_radiation_on_triangles(
    nodes: np.ndarray,
    tri: np.ndarray,
    emissivity: float,
    sigma_sb: float,
    ambient_temperature: float,
    T_linearize: float,
) -> tuple[sp.csr_matrix, np.ndarray]:
    """Linearized radiation: q = eps*sigma*(T^4 - T_inf^4) ≈ h_rad*(T - T_inf).

    h_rad = 4 * eps * sigma * T_linearize^3
    (consistent with a Newton linearization around T_linearize).
    """
    h_rad = 4.0 * float(emissivity) * float(sigma_sb) * float(T_linearize) ** 3
    return assemble_convection_on_triangles(nodes, tri, h_rad, ambient_temperature)


def assemble_gaussian_flux_on_triangles(
    nodes: np.ndarray,
    tri: np.ndarray,
    x_pos: float,
    y_pos: float,
    q0: float,
    r0: float,
) -> np.ndarray:
    """Surface Gaussian heat flux integrated over surface triangles (distributed to nodes)."""
    n = int(nodes.shape[0])
    rhs = np.zeros(n, dtype=float)
    if tri.size == 0 or q0 == 0.0:
        return rhs

    r0_sq = float(r0 * r0)
    for t in tri:
        i0, i1, i2 = (int(t[0]), int(t[1]), int(t[2]))
        a, b, c = nodes[i0], nodes[i1], nodes[i2]
        area = _triangle_area_3d(a, b, c)
        if area <= 0.0:
            continue

        centroid = (a + b + c) / 3.0
        dx = float(centroid[0] - x_pos)
        dy = float(centroid[1] - y_pos)
        q = float(q0 * np.exp(-2.0 * (dx * dx + dy * dy) / r0_sq))
        if q < q0 * 1e-9:
            continue

        val = q * area / 3.0
        rhs[i0] += val
        rhs[i1] += val
        rhs[i2] += val

    return rhs


def _active_heat_sources_at_time(
    *,
    t: float,
    Lx: float,
    velocity: float,
    heat_ys: list[float],
    heat_mode: str,
    pass_gap: float,
) -> tuple[float | None, list[float]]:
    """Return active source x position and list of active y-lines at time t.

    Modes:
    - simultaneous: all y lines are active together, scanning once.
    - sequential: one y line is active per pass, scanning from x=0..Lx each pass.
    """
    heat_mode = str(heat_mode).strip().lower()
    if not heat_ys:
        return None, []

    if velocity <= 0.0:
        return None, []

    if heat_mode == "simultaneous":
        x_pos = float(velocity) * float(t)
        if 0.0 <= x_pos <= float(Lx):
            return x_pos, list(heat_ys)
        return None, []

    if heat_mode == "sequential":
        scan_time = float(Lx) / float(velocity)
        cycle = scan_time + float(max(0.0, pass_gap))
        if cycle <= 0.0:
            return None, []

        pass_idx = int(np.floor(float(t) / cycle))
        if pass_idx < 0 or pass_idx >= len(heat_ys):
            return None, []

        local_t = float(t) - float(pass_idx) * cycle
        if local_t < 0.0 or local_t > scan_time:
            # In the gap between passes.
            return None, []

        x_pos = float(velocity) * local_t
        if 0.0 <= x_pos <= float(Lx):
            return x_pos, [float(heat_ys[pass_idx])]
        return None, []

    raise ValueError(f"Unknown heat_mode: {heat_mode} (expected 'simultaneous' or 'sequential')")


def solve_thermal_3d(
    nodes: np.ndarray,
    tet: np.ndarray,
    top_tri: np.ndarray,
    bottom_tri: np.ndarray,
    Lx: float,
    Ly: float,
    heat_ys: list[float],
    dt: float,
    steps: int,
    conductivity: float,
    density: float,
    heat_capacity: float,
    q0: float,
    r0: float,
    velocity: float,
    h_conv: float,
    ambient_temperature: float,
    reference_temperature: float,
    k_slope: float = 0.0,
    cp_slope: float = 0.0,
    radiation_emissivity: float = 0.0,
    sigma_sb: float = 5.670374419e-14,
    picard_iters: int = 1,
    quench_start: float | None = None,
    quench_h_conv: float | None = None,
    quench_ambient_temperature: float | None = None,
    heat_mode: str = "simultaneous",
    pass_gap: float = 0.0,
) -> np.ndarray:
    temperature = np.full(nodes.shape[0], float(reference_temperature), dtype=float)
    heat_ys = [float(y) for y in heat_ys]

    for step in range(int(steps)):
        t = step * dt
        x_pos, active_ys = _active_heat_sources_at_time(
            t=float(t),
            Lx=float(Lx),
            velocity=float(velocity),
            heat_ys=heat_ys,
            heat_mode=str(heat_mode),
            pass_gap=float(pass_gap),
        )

        # Optional uniform quench phase (stronger convection / different ambient)
        h_conv_step = float(h_conv)
        ambient_step = float(ambient_temperature)
        if quench_start is not None and quench_h_conv is not None and quench_ambient_temperature is not None:
            if float(t) >= float(quench_start):
                h_conv_step = float(quench_h_conv)
                ambient_step = float(quench_ambient_temperature)

        # Picard iterations for temp-dependent K/M and linearized radiation
        T_iter = temperature.copy()
        for _ in range(max(1, int(picard_iters))):
            if k_slope != 0.0 or cp_slope != 0.0:
                K, M = assemble_heat_3d_temp_dependent(
                    nodes,
                    tet,
                    conductivity,
                    k_slope,
                    density,
                    heat_capacity,
                    cp_slope,
                    T_iter,
                    reference_temperature,
                )
            else:
                K, M = assemble_heat_3d(nodes, tet, conductivity, density, heat_capacity)

            Kb_top, rhs_top = assemble_convection_on_triangles(nodes, top_tri, h_conv_step, ambient_step)
            Kb_bot, rhs_bot = assemble_convection_on_triangles(nodes, bottom_tri, h_conv_step, ambient_step)
            Kb = Kb_top + Kb_bot
            rhs_b = rhs_top + rhs_bot

            if radiation_emissivity > 0.0:
                T_lin = float(np.clip(np.max(T_iter), ambient_temperature, 3000.0))
                Kr_top, rr_top = assemble_radiation_on_triangles(
                    nodes, top_tri, radiation_emissivity, sigma_sb, ambient_temperature, T_lin
                )
                Kr_bot, rr_bot = assemble_radiation_on_triangles(
                    nodes, bottom_tri, radiation_emissivity, sigma_sb, ambient_temperature, T_lin
                )
                Kb = Kb + Kr_top + Kr_bot
                rhs_b = rhs_b + rr_top + rr_bot

            A = sp.diags(M / dt) + K + Kb
            solver = spla.factorized(A.tocsc())

            rhs = (M / dt) * temperature + rhs_b
            if x_pos is not None and active_ys:
                for y in active_ys:
                    rhs += assemble_gaussian_flux_on_triangles(nodes, top_tri, float(x_pos), float(y), q0, r0)
            T_iter = solver(rhs)

        temperature = np.asarray(T_iter, dtype=float)

        if step % max(1, steps // 10) == 0:
            x_disp = -1.0 if x_pos is None else float(x_pos)
            print(
                f"  Thermal step {step:5d}/{steps}, t={t:.2f}s, x={x_disp:.1f}mm, T_max={float(np.max(temperature)):.2f}K"
            )

    return np.asarray(temperature, dtype=float)


def solve_thermal_3d_with_peak(
    nodes: np.ndarray,
    tet: np.ndarray,
    top_tri: np.ndarray,
    bottom_tri: np.ndarray,
    Lx: float,
    Ly: float,
    heat_ys: list[float],
    dt: float,
    steps: int,
    conductivity: float,
    density: float,
    heat_capacity: float,
    q0: float,
    r0: float,
    velocity: float,
    h_conv: float,
    ambient_temperature: float,
    reference_temperature: float,
    k_slope: float = 0.0,
    cp_slope: float = 0.0,
    radiation_emissivity: float = 0.0,
    sigma_sb: float = 5.670374419e-14,
    picard_iters: int = 1,
    quench_start: float | None = None,
    quench_h_conv: float | None = None,
    quench_ambient_temperature: float | None = None,
    heat_mode: str = "simultaneous",
    pass_gap: float = 0.0,
) -> tuple[np.ndarray, dict[str, float]]:
    """Solve thermal problem and also track global peak temperature over time.

    Returns:
      temperature_final, peak_stats

    peak_stats contains:
      - T_max_global (K)
      - t_at_T_max_global (s)
      - x_source_at_T_max_global (mm)
      - idx_at_T_max_global (node index)
      - x_at_T_max_global, y_at_T_max_global, z_at_T_max_global (mm)
    """
    temperature = np.full(nodes.shape[0], float(reference_temperature), dtype=float)
    heat_ys = [float(y) for y in heat_ys]

    T_max_global = -np.inf
    t_at = 0.0
    x_src_at = 0.0
    idx_at = 0

    for step in range(int(steps)):
        t = step * dt
        x_pos, active_ys = _active_heat_sources_at_time(
            t=float(t),
            Lx=float(Lx),
            velocity=float(velocity),
            heat_ys=heat_ys,
            heat_mode=str(heat_mode),
            pass_gap=float(pass_gap),
        )

        # Optional uniform quench phase (stronger convection / different ambient)
        h_conv_step = float(h_conv)
        ambient_step = float(ambient_temperature)
        if quench_start is not None and quench_h_conv is not None and quench_ambient_temperature is not None:
            if float(t) >= float(quench_start):
                h_conv_step = float(quench_h_conv)
                ambient_step = float(quench_ambient_temperature)

        # Picard iterations for temp-dependent K/M and linearized radiation
        T_iter = temperature.copy()
        for _ in range(max(1, int(picard_iters))):
            if k_slope != 0.0 or cp_slope != 0.0:
                K, M = assemble_heat_3d_temp_dependent(
                    nodes,
                    tet,
                    conductivity,
                    k_slope,
                    density,
                    heat_capacity,
                    cp_slope,
                    T_iter,
                    reference_temperature,
                )
            else:
                K, M = assemble_heat_3d(nodes, tet, conductivity, density, heat_capacity)

            Kb_top, rhs_top = assemble_convection_on_triangles(nodes, top_tri, h_conv_step, ambient_step)
            Kb_bot, rhs_bot = assemble_convection_on_triangles(nodes, bottom_tri, h_conv_step, ambient_step)
            Kb = Kb_top + Kb_bot
            rhs_b = rhs_top + rhs_bot

            if radiation_emissivity > 0.0:
                T_lin = float(np.clip(np.max(T_iter), ambient_step, 3000.0))
                Kr_top, rr_top = assemble_radiation_on_triangles(
                    nodes, top_tri, radiation_emissivity, sigma_sb, ambient_step, T_lin
                )
                Kr_bot, rr_bot = assemble_radiation_on_triangles(
                    nodes, bottom_tri, radiation_emissivity, sigma_sb, ambient_step, T_lin
                )
                Kb = Kb + Kr_top + Kr_bot
                rhs_b = rhs_b + rr_top + rr_bot

            A = sp.diags(M / dt) + K + Kb
            solver = spla.factorized(A.tocsc())

            rhs = (M / dt) * temperature + rhs_b
            if x_pos is not None and active_ys:
                for y in active_ys:
                    rhs += assemble_gaussian_flux_on_triangles(nodes, top_tri, float(x_pos), float(y), q0, r0)
            T_iter = solver(rhs)

        temperature = np.asarray(T_iter, dtype=float)

        # Track global peak temperature over time
        step_idx = int(np.argmax(temperature))
        step_max = float(temperature[step_idx])
        if step_max > float(T_max_global):
            T_max_global = step_max
            t_at = float(t)
            x_src_at = -1.0 if x_pos is None else float(x_pos)
            idx_at = step_idx

        if step % max(1, steps // 10) == 0:
            x_disp = -1.0 if x_pos is None else float(x_pos)
            print(
                f"  Thermal step {step:5d}/{steps}, t={t:.2f}s, x={x_disp:.1f}mm, T_max={float(np.max(temperature)):.2f}K"
            )

    xyz = nodes[int(idx_at)]
    peak = {
        "T_max_global": float(T_max_global),
        "t_at_T_max_global": float(t_at),
        "x_source_at_T_max_global": float(x_src_at),
        "idx_at_T_max_global": float(idx_at),
        "x_at_T_max_global": float(xyz[0]),
        "y_at_T_max_global": float(xyz[1]),
        "z_at_T_max_global": float(xyz[2]),
    }

    return np.asarray(temperature, dtype=float), peak


def solve_mechanics_3d(
    nodes: np.ndarray,
    tet: np.ndarray,
    temperature: np.ndarray,
    bottom_nodes: np.ndarray,
    Lx: float,
    Ly: float,
    thickness: float,
    bc: str,
    E: float,
    nu: float,
    alpha: float,
    reference_temperature: float,
    eps_inherent: np.ndarray | None = None,
) -> np.ndarray:
    n_nodes = int(nodes.shape[0])
    n_dof = 3 * n_nodes

    nodes_flat = nodes.reshape(-1).tolist()
    tet_flat = tet.reshape(-1).tolist()

    print("  Assembling elasticity stiffness (C++)...")
    asm = thermo_bindings.assemble_elasticity_3d(nodes_flat, tet_flat, float(E), float(nu))
    K = sp.coo_matrix((asm.values, (asm.rows, asm.cols)), shape=(asm.dof_count, asm.dof_count)).tocsr()

    print("  Computing load vector (C++)...")
    if eps_inherent is None:
        F_th = np.asarray(
            thermo_bindings.thermal_load_3d(
                nodes_flat,
                tet_flat,
                np.asarray(temperature, dtype=float).tolist(),
                float(E),
                float(nu),
                float(alpha),
                float(reference_temperature),
            ),
            dtype=float,
        )
    else:
        F_th = np.asarray(
            thermo_bindings.thermal_load_3d_with_inherent(
                nodes_flat,
                tet_flat,
                np.asarray(temperature, dtype=float).tolist(),
                np.asarray(eps_inherent, dtype=float).tolist(),
                float(E),
                float(nu),
                float(alpha),
                float(reference_temperature),
            ),
            dtype=float,
        )

    def _nearest_node(candidates: np.ndarray, target_xyz: tuple[float, float, float], exclude: set[int]) -> int:
        tgt = np.array(target_xyz, dtype=float)
        best = None
        best_d2 = np.inf
        for nid in candidates:
            i = int(nid)
            if i in exclude:
                continue
            d2 = float(np.sum((nodes[i] - tgt) ** 2))
            if d2 < best_d2:
                best_d2 = d2
                best = i
        if best is None:
            raise RuntimeError("Failed to select constraint node for corner-pins BC")
        return int(best)

    fixed: list[int] = []
    bc_mode = str(bc).strip().lower()
    if bc_mode == "bottom_fixed":
        for nid in bottom_nodes:
            nid_int = int(nid)
            fixed.extend([3 * nid_int + 0, 3 * nid_int + 1, 3 * nid_int + 2])
    elif bc_mode == "corner_pins":
        # Ship-like: minimally constrain rigid body motion using 3 bottom-corner pins.
        # A: fix (ux,uy,uz), B: fix (uy,uz), C: fix (uz)
        exclude: set[int] = set()
        a = _nearest_node(bottom_nodes, (0.0, 0.0, 0.0), exclude)
        exclude.add(a)
        b = _nearest_node(bottom_nodes, (float(Lx), 0.0, 0.0), exclude)
        exclude.add(b)
        c = _nearest_node(bottom_nodes, (0.0, float(Ly), 0.0), exclude)

        fixed.extend([3 * a + 0, 3 * a + 1, 3 * a + 2])
        fixed.extend([3 * b + 1, 3 * b + 2])
        fixed.extend([3 * c + 2])
    else:
        raise ValueError(f"Unknown bc mode: {bc}. Use bottom_fixed or corner_pins")

    fixed = np.asarray(sorted(set(fixed)), dtype=int)

    all_dofs = np.arange(n_dof, dtype=int)
    free = np.setdiff1d(all_dofs, fixed)

    print(f"  Solving mechanics: {free.size} free DOFs ({n_dof} total)")
    u_free = spla.spsolve(K[free, :][:, free], F_th[free])

    u = np.zeros(n_dof, dtype=float)
    u[free] = u_free
    return u.reshape(-1, 3)


def plot_outputs(
    nodes: np.ndarray,
    tet: np.ndarray,
    top_tri: np.ndarray,
    temperature: np.ndarray,
    displacement: np.ndarray,
    Lx: float,
    Ly: float,
    thickness: float,
    heat_ys: list[float],
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Sign convention: negative deflection = downward.
    w = -displacement[:, 2]

    # Mesh preview (sample tet edges)
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection="3d")
    sample = max(1, tet.shape[0] // 120)
    for e in range(0, tet.shape[0], sample):
        el = tet[e]
        edges = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
        for a, b in edges:
            p = nodes[[el[a], el[b]]]
            ax.plot(p[:, 0], p[:, 1], p[:, 2], color="navy", linewidth=0.3, alpha=0.35)
    ax.set_title(f"3D mesh preview (showing ~{max(1, tet.shape[0] // sample)} tets)")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.set_zlabel("z (mm)")
    plt.tight_layout()
    plt.savefig(out_dir / "mesh_3d.png", dpi=160)
    plt.close()

    tol = max(1e-9, thickness * 1e-3)
    top_mask = nodes[:, 2] > thickness - tol
    x_top = nodes[top_mask, 0]
    y_top = nodes[top_mask, 1]
    T_top = temperature[top_mask]
    w_top = w[top_mask]

    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(x_top, y_top, c=T_top, cmap="inferno", s=18, edgecolors="k", linewidths=0.15)
    plt.colorbar(sc, ax=ax, label="Temperature (K)")
    ax.set_aspect("equal")
    ax.set_title("Temperature on top surface")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    plt.tight_layout()
    plt.savefig(out_dir / "temperature_top.png", dpi=160)
    plt.close()

    fig, ax = plt.subplots(figsize=(10, 6))
    sc = ax.scatter(x_top, y_top, c=w_top, cmap="RdBu_r", s=18, edgecolors="k", linewidths=0.15)
    plt.colorbar(sc, ax=ax, label="w (mm)")
    ax.set_aspect("equal")
    ax.set_title("Out-of-plane deflection on top surface (negative = downward)")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    plt.tight_layout()
    plt.savefig(out_dir / "deflection_top.png", dpi=160)
    plt.close()

    # 3D deflected surface (triangulate from the existing top surface triangles)
    if top_tri.size:
        # Keep only triangles fully on top surface
        top_node_set = set(np.where(top_mask)[0].tolist())
        tri_top = np.asarray([t for t in top_tri if int(t[0]) in top_node_set and int(t[1]) in top_node_set and int(t[2]) in top_node_set], dtype=int)
        if tri_top.size:
            # remap to local indexing for plot_trisurf
            top_global = np.where(top_mask)[0]
            global_to_local = -np.ones(nodes.shape[0], dtype=int)
            global_to_local[top_global] = np.arange(top_global.size, dtype=int)
            tri_local = global_to_local[tri_top]

            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")
            scale = max(1.0, 0.05 * Lx / (float(np.max(np.abs(w_top))) + 1e-12))
            surf = ax.plot_trisurf(
                x_top,
                y_top,
                w_top * scale,
                triangles=tri_local,
                cmap="RdBu_r",
                linewidth=0.15,
                edgecolor="k",
                alpha=0.9,
            )
            fig.colorbar(surf, ax=ax, shrink=0.55, label=f"w (mm) × {scale:.1f} (neg=down)")
            ax.set_title(f"Deflected top surface (scaled by {scale:.1f}×)")
            ax.set_xlabel("x (mm)")
            ax.set_ylabel("y (mm)")
            ax.set_zlabel("scaled w")
            plt.tight_layout()
            plt.savefig(out_dir / "deflection_3d.png", dpi=160)
            plt.close()

            # Overlay undeformed vs deformed (scaled) top surface
            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")
            ax.plot_trisurf(
                x_top,
                y_top,
                np.zeros_like(w_top),
                triangles=tri_local,
                color="lightgray",
                linewidth=0.15,
                edgecolor="k",
                alpha=0.25,
            )
            surf2 = ax.plot_trisurf(
                x_top,
                y_top,
                w_top * scale,
                triangles=tri_local,
                cmap="RdBu_r",
                linewidth=0.0,
                antialiased=True,
                alpha=0.9,
            )
            fig.colorbar(surf2, ax=ax, shrink=0.55, label=f"w (mm) × {scale:.1f} (neg=down)")
            ax.set_title(f"Undeformed (gray) vs deformed (scaled {scale:.1f}×)")
            ax.set_xlabel("x (mm)")
            ax.set_ylabel("y (mm)")
            ax.set_zlabel("scaled w")
            plt.tight_layout()
            plt.savefig(out_dir / "deflection_3d_overlay.png", dpi=160)
            plt.close()

    # Heating line profiles (top surface near each heat y)
    heat_ys = [float(y) for y in heat_ys]
    band = max(Ly / 40.0, 1e-9)
    colors = ["tab:blue", "tab:green", "tab:orange", "tab:purple", "tab:red"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    any_line = False
    for i, y_center in enumerate(heat_ys):
        line_mask = top_mask & (np.abs(nodes[:, 1] - y_center) < band)
        x_c = nodes[line_mask, 0]
        if x_c.size < 3:
            continue
        any_line = True
        sort_idx = np.argsort(x_c)
        x_c = x_c[sort_idx]
        T_c = temperature[line_mask][sort_idx]
        w_c = w[line_mask][sort_idx]

        c = colors[i % len(colors)]
        ax1.plot(x_c, T_c, ".-", color=c, linewidth=2, label=f"y≈{y_center:.0f} mm")
        ax2.plot(x_c, w_c, ".-", color=c, linewidth=2, label=f"y≈{y_center:.0f} mm")

    if any_line:
        ax1.set_ylabel("T (K)")
        ax1.grid(True, alpha=0.3)
        ax1.set_title("Along heating line(s) (top surface)")
        ax1.legend(loc="best")

        ax2.set_xlabel("x (mm)")
        ax2.set_ylabel("w (mm)")
        ax2.axhline(0.0, color="k", linestyle="--", linewidth=0.8)
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc="best")

        plt.tight_layout()
        plt.savefig(out_dir / "heating_line_profiles.png", dpi=160)
        plt.close()
    else:
        plt.close(fig)

    # Width-wise camber profile near midspan (x ≈ Lx/2). Use mid-surface deflection
    # (avg of top/bottom) to avoid thickness distortion affecting the camber measure.
    tol_z = max(1e-9, thickness * 1e-3)
    top_mask = nodes[:, 2] > thickness - tol_z
    bot_mask = nodes[:, 2] < tol_z

    x0 = 0.5 * float(Lx)
    x_band = max(float(Lx) / 80.0, 25.0)
    mid_mask_top = top_mask & (np.abs(nodes[:, 0] - x0) < x_band)
    mid_mask_bot = bot_mask & (np.abs(nodes[:, 0] - x0) < x_band)

    n_bins = 60
    edges = np.linspace(0.0, float(Ly), n_bins + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])
    w_top_mean = np.full(n_bins, np.nan, dtype=float)
    w_bot_mean = np.full(n_bins, np.nan, dtype=float)

    uz = displacement[:, 2]
    for i in range(n_bins):
        y0, y1 = edges[i], edges[i + 1]
        mtop = mid_mask_top & (nodes[:, 1] >= y0) & (nodes[:, 1] < y1)
        mbot = mid_mask_bot & (nodes[:, 1] >= y0) & (nodes[:, 1] < y1)
        if np.any(mtop):
            w_top_mean[i] = -float(np.mean(uz[mtop]))
        if np.any(mbot):
            w_bot_mean[i] = -float(np.mean(uz[mbot]))

    w_mid = 0.5 * (w_top_mean + w_bot_mean)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(centers, w_mid, "k-", linewidth=2, label="mid-surface w (avg top/bottom)")
    ax.plot(centers, w_top_mean, color="tab:blue", alpha=0.6, linewidth=1.5, label="top w")
    ax.plot(centers, w_bot_mean, color="tab:orange", alpha=0.6, linewidth=1.5, label="bottom w")
    ax.axhline(0.0, color="k", linestyle="--", linewidth=0.8)
    ax.set_xlabel("y (mm)")
    ax.set_ylabel("w (mm)")
    ax.set_title(f"Width camber profile near x≈{x0:.1f} mm (band ±{x_band:.1f} mm)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    plt.tight_layout()
    plt.savefig(out_dir / "camber_width_profile.png", dpi=160)
    plt.close()


def compute_edge_to_edge_camber_midspan(
    nodes: np.ndarray,
    displacement: np.ndarray,
    Lx: float,
    Ly: float,
    thickness: float,
    x_band: float | None = None,
    y_band: float | None = None,
) -> dict[str, float]:
    """Compute edge-to-edge camber across width at midspan using mid-surface w.

    We estimate mid-surface deflection as the average of top & bottom mean deflections
    within small edge strips near y=0 and y=Ly, and an x-strip around x=Lx/2.
    This makes the camber metric robust to thickness-wise distortion/strain.
    """
    tol_z = max(1e-9, float(thickness) * 1e-3)
    top_mask = nodes[:, 2] > float(thickness) - tol_z
    bot_mask = nodes[:, 2] < tol_z

    x0 = 0.5 * float(Lx)
    xb0 = float(x_band) if x_band is not None else max(float(Lx) / 80.0, 25.0)
    yb0 = float(y_band) if y_band is not None else max(float(Ly) / 80.0, 25.0)

    uz = np.asarray(displacement[:, 2], dtype=float)

    def _mid_w(mask_y: np.ndarray) -> tuple[float, float, int]:
        xb = xb0
        for _ in range(8):
            mt = top_mask & mask_y & (np.abs(nodes[:, 0] - x0) < xb)
            mb = bot_mask & mask_y & (np.abs(nodes[:, 0] - x0) < xb)
            if np.count_nonzero(mt) >= 3 and np.count_nonzero(mb) >= 3:
                w_top = -float(np.mean(uz[mt]))
                w_bot = -float(np.mean(uz[mb]))
                return 0.5 * (w_top + w_bot), xb, int(np.count_nonzero(mt) + np.count_nonzero(mb))
            xb *= 1.6
        raise RuntimeError("Not enough nodes in x-strip for camber computation")

    yb = yb0
    for _ in range(8):
        try:
            w_mid_y0, xb_used_0, n0 = _mid_w(nodes[:, 1] < yb)
            w_mid_yLy, xb_used_1, n1 = _mid_w(nodes[:, 1] > float(Ly) - yb)
            xb_used = max(xb_used_0, xb_used_1)
            yb_used = yb
            n_used = min(n0, n1)
            break
        except RuntimeError:
            yb *= 1.6
    else:
        raise RuntimeError("Not enough nodes near y-edges for camber computation")

    camber = w_mid_yLy - w_mid_y0

    return {
        "camber_midspan_edge_to_edge_mm": float(camber),
        "w_mid_edge_y0_mm": float(w_mid_y0),
        "w_mid_edge_yLy_mm": float(w_mid_yLy),
        "x_midspan_mm": float(x0),
        "x_band_mm": float(xb_used),
        "y_band_mm": float(yb_used),
        "camber_nodes_used_min": float(n_used),
    }


def compute_camber_field_widthwise_midspan(
    nodes: np.ndarray,
    displacement: np.ndarray,
    Lx: float,
    Ly: float,
    thickness: float,
    n_bins: int = 80,
    x_band: float | None = None,
) -> np.ndarray:
    """Compute a width-wise camber field w_mid(y) from the midspan strip.

    Returns an array camber_w (mm) for every node, where camber_w is the
    mid-surface deflection (avg top/bottom) binned by y.

    This is meant for visualization: applying this as a z-translation to the
    full solid keeps thickness essentially constant.
    """
    tol_z = max(1e-9, float(thickness) * 1e-3)
    top_mask = nodes[:, 2] > float(thickness) - tol_z
    bot_mask = nodes[:, 2] < tol_z

    x0 = 0.5 * float(Lx)
    xb = float(x_band) if x_band is not None else max(float(Lx) / 80.0, 25.0)
    x_strip_top = top_mask & (np.abs(nodes[:, 0] - x0) < xb)
    x_strip_bot = bot_mask & (np.abs(nodes[:, 0] - x0) < xb)

    edges = np.linspace(0.0, float(Ly), max(2, int(n_bins)) + 1)
    centers = 0.5 * (edges[:-1] + edges[1:])

    uz = np.asarray(displacement[:, 2], dtype=float)
    w_top_mean = np.full(centers.size, np.nan, dtype=float)
    w_bot_mean = np.full(centers.size, np.nan, dtype=float)

    for i in range(centers.size):
        y0, y1 = edges[i], edges[i + 1]
        mtop = x_strip_top & (nodes[:, 1] >= y0) & (nodes[:, 1] < y1)
        mbot = x_strip_bot & (nodes[:, 1] >= y0) & (nodes[:, 1] < y1)
        if np.count_nonzero(mtop) >= 2:
            w_top_mean[i] = -float(np.mean(uz[mtop]))
        if np.count_nonzero(mbot) >= 2:
            w_bot_mean[i] = -float(np.mean(uz[mbot]))

    w_mid = 0.5 * (w_top_mean + w_bot_mean)

    # Fill missing bins by linear interpolation in y (fallback to nearest).
    ok = np.isfinite(w_mid)
    if np.count_nonzero(ok) < 2:
        # Worst case: no reliable camber; return zeros.
        return np.zeros(nodes.shape[0], dtype=float)
    w_mid_filled = w_mid.copy()
    w_mid_filled[~ok] = np.interp(centers[~ok], centers[ok], w_mid[ok])

    # Assign every node by its y-bin.
    y = np.asarray(nodes[:, 1], dtype=float)
    bin_idx = np.clip(np.searchsorted(edges, y, side="right") - 1, 0, centers.size - 1)
    return np.asarray(w_mid_filled[bin_idx], dtype=float)


def main() -> None:
    parser = argparse.ArgumentParser(description="3D thermo-mechanical line heating")
    parser.add_argument("--Lx", type=float, default=1000.0, help="plate length (mm)")
    parser.add_argument("--Ly", type=float, default=900.0, help="plate width (mm)")
    parser.add_argument("--thickness", type=float, default=12.0, help="plate thickness (mm)")

    parser.add_argument("--h", type=float, default=50.0, help="global mesh size (mm)")
    parser.add_argument(
        "--h-refine",
        type=float,
        default=None,
        help="refined mesh size near heating line (mm), default h/3",
    )
    parser.add_argument(
        "--refine-band",
        type=float,
        default=80.0,
        help="half-width refinement band around heating line (mm)",
    )

    parser.add_argument("--q0", type=float, default=10.0, help="peak heat flux (W/mm^2)")
    parser.add_argument("--r0", type=float, default=20.0, help="Gaussian radius (mm)")
    parser.add_argument("--velocity", type=float, default=10.0, help="scan velocity (mm/s)")

    parser.add_argument(
        "--heat-y",
        type=float,
        default=None,
        help="Heating-line y position (mm). Default: Ly/2 (centerline).",
    )
    parser.add_argument(
        "--heat-y-list",
        type=str,
        default=None,
        help="Comma-separated heating-line y positions (mm) to apply simultaneously, e.g. '250,500,750'.",
    )

    parser.add_argument(
        "--heat-mode",
        type=str,
        default="simultaneous",
        choices=["simultaneous", "sequential"],
        help="Heating mode: simultaneous (all lines at once) or sequential (multi-pass, one line after another).",
    )
    parser.add_argument(
        "--pass-gap",
        type=float,
        default=0.0,
        help="Gap time between sequential passes (s). Ignored in simultaneous mode.",
    )

    parser.add_argument(
        "--target-Tmax",
        type=float,
        default=None,
        help="If set, auto-tune q0 to reach this global peak temperature (K).",
    )
    parser.add_argument("--target-Tmax-tol", type=float, default=20.0, help="tolerance for target peak temperature (K)")
    parser.add_argument("--target-Tmax-iters", type=int, default=3, help="max q0 auto-tune iterations")

    parser.add_argument("--dt", type=float, default=0.5, help="time step (s)")
    parser.add_argument("--extra-time", type=float, default=50.0, help="extra time after scanning (s)")

    parser.add_argument("--k", type=float, default=0.045, help="thermal conductivity (W/mm/K)")
    parser.add_argument("--k-slope", type=float, default=0.0, help="linear k(T) slope: k=k0*(1+k_slope*(T-T_ref))")
    parser.add_argument("--rho", type=float, default=7.85e-6, help="density (kg/mm^3)")
    parser.add_argument("--cp", type=float, default=500.0, help="specific heat (J/kg/K)")
    parser.add_argument("--cp-slope", type=float, default=0.0, help="linear cp(T) slope: cp=cp0*(1+cp_slope*(T-T_ref))")

    parser.add_argument("--h-conv", type=float, default=5e-5, help="convective coefficient (W/mm^2/K)")
    parser.add_argument("--quench", action="store_true", help="enable uniform quench phase after heating")
    parser.add_argument(
        "--quench-start",
        type=float,
        default=None,
        help="quench start time (s). Default: end of scan (Lx/velocity) when --quench is set.",
    )
    parser.add_argument(
        "--quench-h-conv",
        type=float,
        default=None,
        help="quench convection coefficient (W/mm^2/K). Example: 5e-3 for strong quench.",
    )
    parser.add_argument(
        "--quench-T-inf",
        type=float,
        default=None,
        help="quench ambient temperature (K). Default: T_inf.",
    )
    parser.add_argument("--emissivity", type=float, default=0.0, help="radiation emissivity (0 disables radiation)")
    parser.add_argument("--picard", type=int, default=1, help="Picard iterations per time step for k(T)/cp(T)/radiation")
    parser.add_argument("--T-inf", type=float, default=293.0, help="ambient temperature (K)")
    parser.add_argument("--T-ref", type=float, default=293.0, help="reference temperature (K)")

    parser.add_argument("--E", type=float, default=210e3, help="Young's modulus (MPa)")
    parser.add_argument("--nu", type=float, default=0.3, help="Poisson's ratio")
    parser.add_argument("--alpha", type=float, default=1.2e-5, help="thermal expansion coefficient (1/K)")

    parser.add_argument(
        "--bc",
        type=str,
        default="bottom_fixed",
        choices=["bottom_fixed", "corner_pins"],
        help="Mechanical boundary condition: bottom_fixed (legacy) or corner_pins (ship-like free plate).",
    )

    # Inherent strain (plasticity surrogate)
    parser.add_argument("--use-inherent", action="store_true", help="enable inherent strain residual mode")
    parser.add_argument("--eps0", type=float, default=0.0, help="peak inherent isotropic strain (dimensionless, e.g., 2e-4)")
    parser.add_argument("--inh-sigma", type=float, default=20.0, help="inherent band half-width (mm) around heating line")
    parser.add_argument("--inh-zfrac", type=float, default=0.5, help="inherent depth fraction (0..1 of thickness from top)")

    parser.add_argument("--out", type=str, default="outputs_3d", help="output directory")

    parser.add_argument(
        "--vtk-deform-scale",
        type=float,
        default=1.0,
        help="Scale factor for writing deformed VTK geometry (points = x + scale*u).",
    )

    args = parser.parse_args()
    out_dir = Path(args.out)

    print("=" * 60)
    print("3D COUPLED THERMO-MECHANICAL SIMULATION")
    print("=" * 60)
    print(f"Geometry: {args.Lx}×{args.Ly}×{args.thickness} mm")
    effective_h_refine = args.h_refine if args.h_refine is not None else args.h / 3.0
    print(f"Mesh: h={args.h} mm, h_refine={effective_h_refine:.2f} mm, refine_band={args.refine_band} mm")
    heat_ys: list[float] = []
    if args.heat_y_list is not None:
        for token in str(args.heat_y_list).split(","):
            token = token.strip()
            if token:
                heat_ys.append(float(token))
    if args.heat_y is not None:
        heat_ys.append(float(args.heat_y))
    if not heat_ys:
        heat_ys = [float(args.Ly / 2.0)]

    # remove duplicates while preserving order
    seen: set[float] = set()
    heat_ys_unique: list[float] = []
    for y in heat_ys:
        key = float(y)
        if key in seen:
            continue
        seen.add(key)
        heat_ys_unique.append(key)
    heat_ys = heat_ys_unique

    print(f"Heating line(s): y={', '.join(f'{y:.3g}' for y in heat_ys)} mm")
    print(f"BC: {args.bc}")

    print("\nStep 1: Meshing...")
    nodes, tet, top_nodes, bottom_nodes, top_tri, bottom_tri = build_plate_mesh_3d(
        args.Lx,
        args.Ly,
        args.thickness,
        args.h,
        args.h_refine,
        args.refine_band,
        heat_ys,
        out_dir,
    )
    print(f"  Nodes={nodes.shape[0]} Tets={tet.shape[0]} TopTri={top_tri.shape[0]} BottomTri={bottom_tri.shape[0]}")

    scan_time_per_pass = args.Lx / args.velocity
    if str(args.heat_mode).lower() == "sequential":
        n_passes = int(len(heat_ys))
        scan_time_total = float(n_passes) * float(scan_time_per_pass) + float(max(0.0, n_passes - 1)) * float(
            max(0.0, args.pass_gap)
        )
    else:
        scan_time_total = float(scan_time_per_pass)

    # Backward-compatible name used in summary/metadata
    scan_time = float(scan_time_total)

    total_time = float(scan_time_total) + float(args.extra_time)
    steps = int(np.ceil(total_time / args.dt))

    quench_start = None
    quench_h_conv = None
    quench_T_inf = None
    if args.quench:
        quench_start = float(scan_time_total) if args.quench_start is None else float(args.quench_start)
        quench_h_conv = float(args.quench_h_conv) if args.quench_h_conv is not None else float(args.h_conv)
        quench_T_inf = float(args.T_inf) if args.quench_T_inf is None else float(args.quench_T_inf)

    print("\nStep 2: Thermal solve...")
    print(
        f"  scan_time_per_pass={scan_time_per_pass:.2f}s scan_time_total={scan_time_total:.2f}s total_time={total_time:.2f}s steps={steps}"
    )
    q0_used = float(args.q0)
    temperature = None
    thermal_peak = None

    if args.target_Tmax is not None:
        target = float(args.target_Tmax)
        tol = float(args.target_Tmax_tol)
        print(f"  Auto-tuning q0 to target peak ~{target:.1f}K (tol {tol:.1f}K)")

        for it in range(max(1, int(args.target_Tmax_iters))):
            temperature, thermal_peak = solve_thermal_3d_with_peak(
                nodes=nodes,
                tet=tet,
                top_tri=top_tri,
                bottom_tri=bottom_tri,
                Lx=args.Lx,
                Ly=args.Ly,
                heat_ys=heat_ys,
                heat_mode=str(args.heat_mode),
                pass_gap=float(args.pass_gap),
                dt=args.dt,
                steps=steps,
                conductivity=args.k,
                density=args.rho,
                heat_capacity=args.cp,
                q0=q0_used,
                r0=args.r0,
                velocity=args.velocity,
                h_conv=args.h_conv,
                ambient_temperature=args.T_inf,
                reference_temperature=args.T_ref,
                k_slope=args.k_slope,
                cp_slope=args.cp_slope,
                radiation_emissivity=args.emissivity,
                picard_iters=args.picard,
                quench_start=quench_start,
                quench_h_conv=quench_h_conv,
                quench_ambient_temperature=quench_T_inf,
            )

            peak = float(thermal_peak["T_max_global"])
            err = peak - target
            print(f"    tune iter {it+1}: q0={q0_used:.6g}, peak={peak:.2f}K, err={err:+.2f}K")
            if abs(err) <= tol:
                break

            # Scale q0 assuming approximately linear response in (T_peak - T_ref)
            denom = max(1e-9, peak - float(args.T_ref))
            numer = max(1e-9, target - float(args.T_ref))
            scale = numer / denom
            scale = float(np.clip(scale, 0.2, 5.0))
            q0_used *= scale

        print(f"  Tuned q0_used={q0_used:.6g} (initial {float(args.q0):.6g})")
    else:
        temperature, thermal_peak = solve_thermal_3d_with_peak(
            nodes=nodes,
            tet=tet,
            top_tri=top_tri,
            bottom_tri=bottom_tri,
            Lx=args.Lx,
            Ly=args.Ly,
            heat_ys=heat_ys,
            heat_mode=str(args.heat_mode),
            pass_gap=float(args.pass_gap),
            dt=args.dt,
            steps=steps,
            conductivity=args.k,
            density=args.rho,
            heat_capacity=args.cp,
            q0=q0_used,
            r0=args.r0,
            velocity=args.velocity,
            h_conv=args.h_conv,
            ambient_temperature=args.T_inf,
            reference_temperature=args.T_ref,
            k_slope=args.k_slope,
            cp_slope=args.cp_slope,
            radiation_emissivity=args.emissivity,
            picard_iters=args.picard,
            quench_start=quench_start,
            quench_h_conv=quench_h_conv,
            quench_ambient_temperature=quench_T_inf,
        )

    assert temperature is not None
    assert thermal_peak is not None
    print(f"  T range: [{float(np.min(temperature)):.2f}, {float(np.max(temperature)):.2f}] K")

    print("\nStep 3: Mechanics solve...")
    eps_inherent = None
    if args.use_inherent and args.eps0 != 0.0:
        # Simple inherent strain field: band around heating line on the top portion of thickness.
        band = float(args.inh_sigma)
        band_w = np.zeros(nodes.shape[0], dtype=float)
        for y_center in heat_ys:
            y_dist = np.abs(nodes[:, 1] - float(y_center))
            band_w += np.exp(-0.5 * (y_dist / max(1e-9, band)) ** 2)

        z_cut = float(args.thickness) * float(np.clip(args.inh_zfrac, 0.0, 1.0))
        z_mask = (nodes[:, 2] >= float(args.thickness) - z_cut).astype(float)

        eps_inherent = float(args.eps0) * band_w * z_mask

    displacement = solve_mechanics_3d(
        nodes,
        tet,
        temperature,
        bottom_nodes,
        args.Lx,
        args.Ly,
        args.thickness,
        args.bc,
        args.E,
        args.nu,
        args.alpha,
        args.T_ref,
        eps_inherent=eps_inherent,
    )
    w = -displacement[:, 2]
    print(f"  w range (negative = downward): [{float(np.min(w)):.6g}, {float(np.max(w)):.6g}] mm")

    print("\nStep 4: Write outputs...")
    plot_outputs(nodes, tet, top_tri, temperature, displacement, args.Lx, args.Ly, args.thickness, heat_ys, out_dir)

    np.save(out_dir / "nodes.npy", nodes)
    np.save(out_dir / "tet.npy", tet)
    np.save(out_dir / "temperature.npy", temperature)
    np.save(out_dir / "displacement.npy", displacement)

    camber = compute_edge_to_edge_camber_midspan(
        nodes=nodes,
        displacement=displacement,
        Lx=float(args.Lx),
        Ly=float(args.Ly),
        thickness=float(args.thickness),
    )

    # Small machine-readable summary for sweeps/validation.
    w_min_idx = int(np.argmin(w))
    w_max_idx = int(np.argmax(w))
    wmin_xyz = nodes[w_min_idx]
    wmax_xyz = nodes[w_max_idx]
    summary = {
        "inputs": {
            "Lx": float(args.Lx),
            "Ly": float(args.Ly),
            "thickness": float(args.thickness),
            "h": float(args.h),
            "h_refine": float(effective_h_refine),
            "refine_band": float(args.refine_band),
            "q0": float(q0_used),
            "r0": float(args.r0),
            "velocity": float(args.velocity),
            "heat_mode": str(args.heat_mode),
            "pass_gap": float(args.pass_gap),
            "heat_y": float(heat_ys[0]),
            "heat_y_list": [float(y) for y in heat_ys],
            "target_Tmax": (None if args.target_Tmax is None else float(args.target_Tmax)),
            "dt": float(args.dt),
            "steps": float(steps),
            "scan_time": float(scan_time),
            "scan_time_per_pass": float(scan_time_per_pass),
            "scan_time_total": float(scan_time_total),
            "total_time": float(total_time),
            "k": float(args.k),
            "k_slope": float(args.k_slope),
            "rho": float(args.rho),
            "cp": float(args.cp),
            "cp_slope": float(args.cp_slope),
            "h_conv": float(args.h_conv),
            "quench": bool(args.quench),
            "quench_start": (None if quench_start is None else float(quench_start)),
            "quench_h_conv": (None if quench_h_conv is None else float(quench_h_conv)),
            "quench_T_inf": (None if quench_T_inf is None else float(quench_T_inf)),
            "emissivity": float(args.emissivity),
            "picard": float(args.picard),
            "T_inf": float(args.T_inf),
            "T_ref": float(args.T_ref),
            "E": float(args.E),
            "nu": float(args.nu),
            "alpha": float(args.alpha),
            "bc": str(args.bc),
            "use_inherent": bool(args.use_inherent),
            "eps0": float(args.eps0),
            "inh_sigma": float(args.inh_sigma),
            "inh_zfrac": float(args.inh_zfrac),
        },
        "thermal": {
            "T_min_final": float(np.min(temperature)),
            "T_max_final": float(np.max(temperature)),
            **{k: float(v) for k, v in thermal_peak.items()},
        },
        "mechanics": {
            "w_min": float(np.min(w)),
            "w_max": float(np.max(w)),
            "idx_w_min": float(w_min_idx),
            "x_w_min": float(wmin_xyz[0]),
            "y_w_min": float(wmin_xyz[1]),
            "z_w_min": float(wmin_xyz[2]),
            "idx_w_max": float(w_max_idx),
            "x_w_max": float(wmax_xyz[0]),
            "y_w_max": float(wmax_xyz[1]),
            "z_w_max": float(wmax_xyz[2]),
            **camber,
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    point_data = {
        "Temperature": temperature,
        "Displacement": displacement,
        "DisplacementDown": np.column_stack([displacement[:, 0], displacement[:, 1], -displacement[:, 2]]),
        "w": -displacement[:, 2],
        "uz": displacement[:, 2],
        "eps_inherent": (np.zeros(nodes.shape[0]) if eps_inherent is None else np.asarray(eps_inherent, dtype=float)),
    }

    # Camber-only field for visualization (mid-surface width-wise camber from midspan strip)
    w_camber_mid = compute_camber_field_widthwise_midspan(
        nodes=nodes,
        displacement=displacement,
        Lx=float(args.Lx),
        Ly=float(args.Ly),
        thickness=float(args.thickness),
    )
    point_data["w_camber_midspan"] = np.asarray(w_camber_mid, dtype=float)
    point_data["DisplacementCamberDown"] = np.column_stack(
        [np.zeros(nodes.shape[0]), np.zeros(nodes.shape[0]), np.asarray(w_camber_mid, dtype=float)]
    )

    # Undeformed + deformed VTK (both written for convenience)
    write_vtk_unstructured_grid(out_dir / "results.vtk", nodes, tet, point_data)
    write_vtk_unstructured_grid(out_dir / "results_undeformed.vtk", nodes, tet, point_data)
    deform_scale = float(args.vtk_deform_scale)
    # Use the same sign convention as plots/summary: negative deflection is downward.
    disp_down = np.column_stack([displacement[:, 0], displacement[:, 1], -displacement[:, 2]])
    nodes_def_down = nodes + deform_scale * disp_down
    write_vtk_unstructured_grid(out_dir / "results_deformed.vtk", nodes_def_down, tet, point_data)

    # Also write a "raw" deformed mesh using the solver's displacement vector (uz as computed).
    nodes_def_raw = nodes + deform_scale * displacement
    write_vtk_unstructured_grid(out_dir / "results_deformed_raw.vtk", nodes_def_raw, tet, point_data)

    # Camber-only deformed mesh: translate in z by w_camber_midspan (thickness preserved)
    nodes_def_camber = nodes + deform_scale * np.column_stack(
        [np.zeros(nodes.shape[0]), np.zeros(nodes.shape[0]), np.asarray(w_camber_mid, dtype=float)]
    )
    write_vtk_unstructured_grid(out_dir / "results_camber_only_deformed.vtk", nodes_def_camber, tet, point_data)

    print(f"  ParaView mesh: {out_dir / 'mesh.msh'}")
    print(f"  ParaView results (undeformed): {out_dir / 'results_undeformed.vtk'}")
    print(f"  ParaView results (deformed):   {out_dir / 'results_deformed.vtk'} (uses DisplacementDown; scale={deform_scale:g})")
    print(f"  ParaView results (deformed raw): {out_dir / 'results_deformed_raw.vtk'}")
    print(f"  ParaView results (camber-only): {out_dir / 'results_camber_only_deformed.vtk'} (uses w_camber_midspan; scale={deform_scale:g})")
    print(f"  Plots: {out_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
