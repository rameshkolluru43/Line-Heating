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


def _coerce_line_item(item: object) -> dict[str, float]:
    if isinstance(item, dict):
        if all(k in item for k in ("x0", "y0", "x1", "y1")):
            return {
                "x0": float(item["x0"]),
                "y0": float(item["y0"]),
                "x1": float(item["x1"]),
                "y1": float(item["y1"]),
            }
        if all(k in item for k in ("x_start_mm", "x_end_mm", "y_mm")):
            y = float(item["y_mm"])
            return {
                "x0": float(item["x_start_mm"]),
                "y0": y,
                "x1": float(item["x_end_mm"]),
                "y1": y,
            }
    if isinstance(item, (list, tuple)) and len(item) == 4:
        return {"x0": float(item[0]), "y0": float(item[1]), "x1": float(item[2]), "y1": float(item[3])}
    raise ValueError(f"Invalid heat line item: {item}")


def _load_heat_lines_arg(heat_lines: str | None, heat_lines_file: str | None) -> list[dict[str, float]] | None:
    payload = None
    if heat_lines_file is not None:
        payload = Path(heat_lines_file).read_text(encoding="utf-8")
    elif heat_lines is not None:
        if str(heat_lines).startswith("@"):  # @file.json
            payload = Path(str(heat_lines)[1:]).read_text(encoding="utf-8")
        else:
            path = Path(str(heat_lines))
            if path.exists():
                payload = path.read_text(encoding="utf-8")
            else:
                payload = str(heat_lines)
    if payload is None:
        return None
    data = json.loads(payload)
    if isinstance(data, dict) and "lines" in data:
        data = data["lines"]
    if not isinstance(data, list):
        raise ValueError("heat_lines must be a JSON list")
    return [_coerce_line_item(item) for item in data]


def _build_heat_lines_from_ys(Lx: float, heat_ys: list[float]) -> list[dict[str, float]]:
    return [
        {"x0": 0.0, "y0": float(y), "x1": float(Lx), "y1": float(y)}
        for y in heat_ys
    ]


def _prepare_heat_lines(heat_lines: list[dict[str, float]]) -> list[dict[str, float]]:
    prepared = []
    for ln in heat_lines:
        x0 = float(ln["x0"])
        y0 = float(ln["y0"])
        x1 = float(ln["x1"])
        y1 = float(ln["y1"])
        dx = x1 - x0
        dy = y1 - y0
        length = float(np.hypot(dx, dy))
        if length <= 0.0:
            raise ValueError("Heat line length must be positive")
        prepared.append({"x0": x0, "y0": y0, "x1": x1, "y1": y1, "ux": dx / length, "uy": dy / length, "length": length})
    return prepared


def _active_heat_positions_at_time(
    *,
    t: float,
    velocity: float,
    heat_lines: list[dict[str, float]],
    heat_mode: str,
    pass_gap: float,
) -> list[tuple[float, float]]:
    """Return active source (x,y) positions at time t along each heat line."""
    heat_mode = str(heat_mode).strip().lower()
    if not heat_lines or velocity <= 0.0:
        return []

    if heat_mode == "simultaneous":
        positions: list[tuple[float, float]] = []
        s = float(velocity) * float(t)
        for ln in heat_lines:
            if 0.0 <= s <= float(ln["length"]):
                x = float(ln["x0"]) + float(ln["ux"]) * s
                y = float(ln["y0"]) + float(ln["uy"]) * s
                positions.append((x, y))
        return positions

    if heat_mode == "sequential":
        local_t = float(t)
        gap = float(max(0.0, pass_gap))
        for ln in heat_lines:
            duration = float(ln["length"]) / float(velocity)
            if local_t < duration:
                s = float(velocity) * local_t
                x = float(ln["x0"]) + float(ln["ux"]) * s
                y = float(ln["y0"]) + float(ln["uy"]) * s
                return [(x, y)]
            if local_t < duration + gap:
                return []
            local_t -= duration + gap
        return []

    raise ValueError(f"Unknown heat_mode: {heat_mode} (expected 'simultaneous' or 'sequential')")


def _distance_to_segment(xy: np.ndarray, line: dict[str, float]) -> np.ndarray:
    p0 = np.array([line["x0"], line["y0"]], dtype=float)
    p1 = np.array([line["x1"], line["y1"]], dtype=float)
    v = p1 - p0
    denom = float(np.dot(v, v))
    if denom <= 0.0:
        return np.linalg.norm(xy - p0[None, :], axis=1)
    t = ((xy - p0[None, :]) @ v) / denom
    t = np.clip(t, 0.0, 1.0)
    proj = p0[None, :] + t[:, None] * v[None, :]
    return np.linalg.norm(xy - proj, axis=1)


def _along_line_coordinate(xy: np.ndarray, line: dict[str, float]) -> np.ndarray:
    p0 = np.array([line["x0"], line["y0"]], dtype=float)
    v = np.array([line["ux"], line["uy"]], dtype=float)
    return (xy - p0[None, :]) @ v


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


def _tetra_volume(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> float:
    return abs(float(np.dot(b - a, np.cross(c - a, d - a)))) / 6.0


def build_plate_mesh_3d(
    Lx: float,
    Ly: float,
    thickness: float,
    h: float,
    h_refine: float | None,
    refine_band: float,
    heat_ys: list[float] | None,
    heat_lines: list[dict[str, float]] | None,
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
        heating_curves: list[int] = []
        if heat_lines:
            for ln in heat_lines:
                p1 = gmsh.model.occ.addPoint(float(ln["x0"]), float(ln["y0"]), float(thickness), float(h_refine))
                p2 = gmsh.model.occ.addPoint(float(ln["x1"]), float(ln["y1"]), float(thickness), float(h_refine))
                heating_curves.append(int(gmsh.model.occ.addLine(p1, p2)))
        else:
            if not heat_ys:
                heat_ys = [float(Ly / 2.0)]
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
    beta: float = 2.0,
) -> np.ndarray:
    """Surface Gaussian heat flux integrated over surface triangles (distributed to nodes)."""
    n = int(nodes.shape[0])
    rhs = np.zeros(n, dtype=float)
    if tri.size == 0 or q0 == 0.0:
        return rhs

    r0_sq = float(r0 * r0)
    beta = float(beta)
    for t in tri:
        i0, i1, i2 = (int(t[0]), int(t[1]), int(t[2]))
        a, b, c = nodes[i0], nodes[i1], nodes[i2]
        area = _triangle_area_3d(a, b, c)
        if area <= 0.0:
            continue

        centroid = (a + b + c) / 3.0
        dx = float(centroid[0] - x_pos)
        dy = float(centroid[1] - y_pos)
        q = float(q0 * np.exp(-beta * (dx * dx + dy * dy) / r0_sq))
        if q < q0 * 1e-9:
            continue

        val = q * area / 3.0
        rhs[i0] += val
        rhs[i1] += val
        rhs[i2] += val

    return rhs


def assemble_line_gaussian_flux_on_triangles(
    nodes: np.ndarray,
    tri: np.ndarray,
    line: dict[str, float],
    q0: float,
    r0: float,
    beta: float = 2.0,
) -> np.ndarray:
    """Surface heat flux from a stationary Gaussian band along a full line segment.

    This models an induction-style line source: the whole heat line is active at once,
    with Gaussian decay normal to the line rather than a moving point source.
    """
    n = int(nodes.shape[0])
    rhs = np.zeros(n, dtype=float)
    if tri.size == 0 or q0 == 0.0:
        return rhs

    r0_sq = float(r0 * r0)
    beta = float(beta)
    for t in tri:
        i0, i1, i2 = (int(t[0]), int(t[1]), int(t[2]))
        a, b, c = nodes[i0], nodes[i1], nodes[i2]
        area = _triangle_area_3d(a, b, c)
        if area <= 0.0:
            continue

        centroid = (a + b + c) / 3.0
        dist = float(_distance_to_segment(centroid[None, :2], line)[0])
        q = float(q0 * np.exp(-beta * (dist * dist) / r0_sq))
        if q < q0 * 1e-9:
            continue

        val = q * area / 3.0
        rhs[i0] += val
        rhs[i1] += val
        rhs[i2] += val

    return rhs


def induction_skin_depth_mm(
    frequency_hz: float,
    electrical_resistivity_ohm_m: float,
    relative_permeability: float,
) -> float:
    """Return induction skin depth in mm from delta=sqrt(rho_e/(pi*f*mu))."""
    mu0 = 4.0e-7 * np.pi
    f = max(1e-12, float(frequency_hz))
    rho_e = max(1e-18, float(electrical_resistivity_ohm_m))
    mu_r = max(1e-9, float(relative_permeability))
    delta_m = float(np.sqrt(rho_e / (np.pi * f * mu0 * mu_r)))
    return 1000.0 * delta_m


def assemble_induction_skin_source_on_tets(
    nodes: np.ndarray,
    tet: np.ndarray,
    line: dict[str, float],
    q0: float,
    r0: float,
    beta: float,
    thickness: float,
    skin_depth_mm: float,
    efficiency: float = 1.0,
) -> np.ndarray:
    """Volumetric induction source distributed with lateral Gaussian and skin-depth decay.

    q0 is interpreted as absorbed peak areal power density (W/mm^2). It is
    normalized over thickness so the depth integral recovers q0 at the line
    center before lateral Gaussian decay.
    """
    n = int(nodes.shape[0])
    rhs = np.zeros(n, dtype=float)
    if tet.size == 0 or q0 == 0.0:
        return rhs

    r0_sq = float(r0 * r0)
    beta = float(beta)
    delta = max(1e-9, float(skin_depth_mm))
    thickness = max(1e-9, float(thickness))
    z_top = thickness
    depth_norm = delta * (1.0 - float(np.exp(-thickness / delta)))
    q0_absorbed = float(q0) * float(np.clip(efficiency, 0.0, None))

    for e in tet:
        i0, i1, i2, i3 = (int(e[0]), int(e[1]), int(e[2]), int(e[3]))
        a, b, c, d = nodes[i0], nodes[i1], nodes[i2], nodes[i3]
        vol = _tetra_volume(a, b, c, d)
        if vol <= 0.0:
            continue

        centroid = (a + b + c + d) / 4.0
        dist = float(_distance_to_segment(centroid[None, :2], line)[0])
        lateral = float(np.exp(-beta * (dist * dist) / r0_sq))
        if lateral < 1e-9:
            continue

        depth = float(np.clip(z_top - centroid[2], 0.0, thickness))
        depth_weight = float(np.exp(-depth / delta)) / max(1e-12, depth_norm)
        qv = q0_absorbed * lateral * depth_weight
        val = qv * vol / 4.0
        rhs[i0] += val
        rhs[i1] += val
        rhs[i2] += val
        rhs[i3] += val

    return rhs


def _active_heat_lines_at_time(
    *,
    t: float,
    velocity: float,
    heat_lines: list[dict[str, float]],
    heat_mode: str,
    pass_gap: float,
) -> list[dict[str, float]]:
    """Return active full-line sources for an induction-style line heat source."""
    heat_mode = str(heat_mode).strip().lower()
    if not heat_lines or velocity <= 0.0:
        return []

    if heat_mode == "simultaneous":
        active: list[dict[str, float]] = []
        for ln in heat_lines:
            duration = float(ln["length"]) / float(velocity)
            if 0.0 <= float(t) <= duration:
                active.append(ln)
        return active

    if heat_mode == "sequential":
        local_t = float(t)
        gap = float(max(0.0, pass_gap))
        for ln in heat_lines:
            duration = float(ln["length"]) / float(velocity)
            if local_t < duration:
                return [ln]
            if local_t < duration + gap:
                return []
            local_t -= duration + gap
        return []

    raise ValueError(f"Unknown heat_mode: {heat_mode} (expected 'simultaneous' or 'sequential')")


def _active_heat_sources_at_time(
    *,
    t: float,
    velocity: float,
    heat_lines: list[dict[str, float]],
    heat_mode: str,
    pass_gap: float,
) -> list[tuple[float, float]]:
    """Backward-compatible wrapper returning active (x,y) positions."""
    return _active_heat_positions_at_time(
        t=t,
        velocity=velocity,
        heat_lines=heat_lines,
        heat_mode=heat_mode,
        pass_gap=pass_gap,
    )


def _parse_temp_table(table_str: str | None) -> tuple[np.ndarray, np.ndarray] | None:
    if table_str is None:
        return None
    items = []
    for token in str(table_str).split(","):
        token = token.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError(f"Invalid table token '{token}'. Expected 'T:value'.")
        t_s, v_s = token.split(":", 1)
        items.append((float(t_s), float(v_s)))
    if not items:
        return None
    items.sort(key=lambda tv: tv[0])
    temps_c = np.array([t for t, _ in items], dtype=float)
    values = np.array([v for _, v in items], dtype=float)
    return temps_c, values


def _interp_table(temps_k: np.ndarray, table: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    temps_c = temps_k - 273.15
    t_tab, v_tab = table
    return np.interp(temps_c, t_tab, v_tab, left=v_tab[0], right=v_tab[-1])


def solve_thermal_3d(
    nodes: np.ndarray,
    tet: np.ndarray,
    top_tri: np.ndarray,
    bottom_tri: np.ndarray,
    Lx: float,
    Ly: float,
    heat_ys: list[float],
    heat_lines: list[dict[str, float]] | None,
    dt: float,
    steps: int,
    conductivity: float,
    density: float,
    heat_capacity: float,
    q0: float,
    r0: float,
    velocity: float,
    h_conv_top: float,
    h_conv_bottom: float,
    ambient_temperature: float,
    reference_temperature: float,
    k_slope: float = 0.0,
    cp_slope: float = 0.0,
    radiation_emissivity: float = 0.0,
    sigma_sb: float = 5.670374419e-14,
    picard_iters: int = 1,
    quench_start: float | None = None,
    quench_h_conv_top: float | None = None,
    quench_h_conv_bottom: float | None = None,
    quench_ambient_temperature: float | None = None,
    heat_mode: str = "simultaneous",
    pass_gap: float = 0.0,
    gaussian_beta: float = 2.0,
    heat_source_mode: str = "moving_gaussian",
    induction_frequency: float = 10000.0,
    induction_relative_permeability: float = 100.0,
    induction_electrical_resistivity: float = 2.5e-7,
    induction_efficiency: float = 1.0,
) -> np.ndarray:
    temperature = np.full(nodes.shape[0], float(reference_temperature), dtype=float)
    if heat_lines is None:
        heat_lines = _build_heat_lines_from_ys(float(Lx), [float(y) for y in heat_ys])
    heat_lines = _prepare_heat_lines(list(heat_lines))
    source_mode = str(heat_source_mode).strip().lower()
    line_source_modes = {"line_gaussian", "induction_skin"}
    skin_depth = induction_skin_depth_mm(
        induction_frequency,
        induction_electrical_resistivity,
        induction_relative_permeability,
    )

    for step in range(int(steps)):
        t = step * dt
        active_positions = _active_heat_sources_at_time(
            t=float(t),
            velocity=float(velocity),
            heat_lines=heat_lines,
            heat_mode=str(heat_mode),
            pass_gap=float(pass_gap),
        )
        active_lines: list[dict[str, float]] = []
        if source_mode in line_source_modes:
            active_lines = _active_heat_lines_at_time(
                t=float(t),
                velocity=float(velocity),
                heat_lines=heat_lines,
                heat_mode=str(heat_mode),
                pass_gap=float(pass_gap),
            )

        # Optional uniform quench phase (stronger convection / different ambient)
        h_conv_top_step = float(h_conv_top)
        h_conv_bottom_step = float(h_conv_bottom)
        ambient_step = float(ambient_temperature)
        if (
            quench_start is not None
            and quench_h_conv_top is not None
            and quench_h_conv_bottom is not None
            and quench_ambient_temperature is not None
        ):
            if float(t) >= float(quench_start):
                h_conv_top_step = float(quench_h_conv_top)
                h_conv_bottom_step = float(quench_h_conv_bottom)
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

            Kb_top, rhs_top = assemble_convection_on_triangles(nodes, top_tri, h_conv_top_step, ambient_step)
            Kb_bot, rhs_bot = assemble_convection_on_triangles(nodes, bottom_tri, h_conv_bottom_step, ambient_step)
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
            if source_mode == "line_gaussian":
                for ln in active_lines:
                    rhs += assemble_line_gaussian_flux_on_triangles(
                        nodes, top_tri, ln, q0, r0, gaussian_beta
                    )
            elif source_mode == "induction_skin":
                for ln in active_lines:
                    rhs += assemble_induction_skin_source_on_tets(
                        nodes,
                        tet,
                        ln,
                        q0,
                        r0,
                        gaussian_beta,
                        thickness=float(np.max(nodes[:, 2]) - np.min(nodes[:, 2])),
                        skin_depth_mm=skin_depth,
                        efficiency=induction_efficiency,
                    )
            elif active_positions:
                for x_pos, y_pos in active_positions:
                    rhs += assemble_gaussian_flux_on_triangles(
                        nodes, top_tri, float(x_pos), float(y_pos), q0, r0, gaussian_beta
                    )
            T_iter = solver(rhs)

        temperature = np.asarray(T_iter, dtype=float)

        if step % max(1, steps // 10) == 0:
            if source_mode in line_source_modes and active_lines:
                x_disp = 0.5 * (float(active_lines[0]["x0"]) + float(active_lines[0]["x1"]))
            else:
                x_disp = -1.0 if not active_positions else float(active_positions[0][0])
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
    heat_lines: list[dict[str, float]] | None,
    dt: float,
    steps: int,
    conductivity: float,
    density: float,
    heat_capacity: float,
    q0: float,
    r0: float,
    velocity: float,
    h_conv_top: float,
    h_conv_bottom: float,
    ambient_temperature: float,
    reference_temperature: float,
    k_slope: float = 0.0,
    cp_slope: float = 0.0,
    radiation_emissivity: float = 0.0,
    sigma_sb: float = 5.670374419e-14,
    picard_iters: int = 1,
    quench_start: float | None = None,
    quench_h_conv_top: float | None = None,
    quench_h_conv_bottom: float | None = None,
    quench_ambient_temperature: float | None = None,
    heat_mode: str = "simultaneous",
    pass_gap: float = 0.0,
    gaussian_beta: float = 2.0,
    adaptive_dt: bool = False,
    total_time: float | None = None,
    dt_min: float | None = None,
    dt_max: float | None = None,
    return_history: bool = False,
    track_energy_balance: bool = False,
    heat_source_mode: str = "moving_gaussian",
    induction_frequency: float = 10000.0,
    induction_relative_permeability: float = 100.0,
    induction_electrical_resistivity: float = 2.5e-7,
    induction_efficiency: float = 1.0,
) -> tuple[np.ndarray, dict[str, float]] | tuple[np.ndarray, dict[str, float], list[np.ndarray], list[float]]:
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
    if heat_lines is None:
        heat_lines = _build_heat_lines_from_ys(float(Lx), [float(y) for y in heat_ys])
    heat_lines = _prepare_heat_lines(list(heat_lines))
    source_mode = str(heat_source_mode).strip().lower()
    line_source_modes = {"line_gaussian", "induction_skin"}
    skin_depth = induction_skin_depth_mm(
        induction_frequency,
        induction_electrical_resistivity,
        induction_relative_permeability,
    )

    T_max_global = -np.inf
    t_at = 0.0
    x_src_at = 0.0
    y_src_at = 0.0
    idx_at = 0

    temps_history: list[np.ndarray] = []
    times_history: list[float] = []

    # Optional energy-balance tracking (scalar totals). All quantities are in Joules (J) when
    # using the internal mm/s/K unit system.
    Q_in_total_J = 0.0
    Q_conv_total_J = 0.0
    Q_rad_total_J = 0.0
    U_sensible_J = 0.0

    t = 0.0
    step = 0
    if adaptive_dt and total_time is None:
        raise ValueError("total_time is required when adaptive_dt is True")

    next_log = 0.0
    log_every = 0.0
    if adaptive_dt:
        log_every = max(1e-9, float(total_time) / 10.0)
    else:
        log_every = float(steps)

    while True:
        if adaptive_dt:
            if t >= float(total_time) - 1e-12:
                break
            active_positions = _active_heat_sources_at_time(
                t=float(t),
                velocity=float(velocity),
                heat_lines=heat_lines,
                heat_mode=str(heat_mode),
                pass_gap=float(pass_gap),
            )
            active_lines: list[dict[str, float]] = []
            if source_mode in line_source_modes:
                active_lines = _active_heat_lines_at_time(
                    t=float(t),
                    velocity=float(velocity),
                    heat_lines=heat_lines,
                    heat_mode=str(heat_mode),
                    pass_gap=float(pass_gap),
                )
            dt_step = float(dt_min if dt_min is not None else dt)
            is_active = bool(active_lines) if source_mode in line_source_modes else bool(active_positions)
            if not is_active:
                dt_step = float(dt_max if dt_max is not None else dt_step)
        else:
            if step >= int(steps):
                break
            dt_step = float(dt)
            active_positions = _active_heat_sources_at_time(
                t=float(t),
                velocity=float(velocity),
                heat_lines=heat_lines,
                heat_mode=str(heat_mode),
                pass_gap=float(pass_gap),
            )
            active_lines = []
            if source_mode in line_source_modes:
                active_lines = _active_heat_lines_at_time(
                    t=float(t),
                    velocity=float(velocity),
                    heat_lines=heat_lines,
                    heat_mode=str(heat_mode),
                    pass_gap=float(pass_gap),
                )
        # Optional uniform quench phase (stronger convection / different ambient)
        h_conv_top_step = float(h_conv_top)
        h_conv_bottom_step = float(h_conv_bottom)
        ambient_step = float(ambient_temperature)
        if (
            quench_start is not None
            and quench_h_conv_top is not None
            and quench_h_conv_bottom is not None
            and quench_ambient_temperature is not None
        ):
            if float(t) >= float(quench_start):
                h_conv_top_step = float(quench_h_conv_top)
                h_conv_bottom_step = float(quench_h_conv_bottom)
                ambient_step = float(quench_ambient_temperature)

        # Picard iterations for temp-dependent K/M and linearized radiation
        T_iter = temperature.copy()

        # Keep last-iteration operators for optional energy accounting.
        M_last = None
        Kb_top_last = None
        rhs_top_last = None
        Kb_bot_last = None
        rhs_bot_last = None
        Kr_top_last = None
        rr_top_last = None
        Kr_bot_last = None
        rr_bot_last = None

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

            M_last = M

            Kb_top, rhs_top = assemble_convection_on_triangles(nodes, top_tri, h_conv_top_step, ambient_step)
            Kb_bot, rhs_bot = assemble_convection_on_triangles(nodes, bottom_tri, h_conv_bottom_step, ambient_step)
            Kb = Kb_top + Kb_bot
            rhs_b = rhs_top + rhs_bot

            Kb_top_last, rhs_top_last = Kb_top, rhs_top
            Kb_bot_last, rhs_bot_last = Kb_bot, rhs_bot

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

                Kr_top_last, rr_top_last = Kr_top, rr_top
                Kr_bot_last, rr_bot_last = Kr_bot, rr_bot

            A = sp.diags(M / dt_step) + K + Kb
            solver = spla.factorized(A.tocsc())

            rhs = (M / dt_step) * temperature + rhs_b
            if source_mode == "line_gaussian":
                for ln in active_lines:
                    rhs += assemble_line_gaussian_flux_on_triangles(
                        nodes, top_tri, ln, q0, r0, gaussian_beta
                    )
            elif source_mode == "induction_skin":
                for ln in active_lines:
                    rhs += assemble_induction_skin_source_on_tets(
                        nodes,
                        tet,
                        ln,
                        q0,
                        r0,
                        gaussian_beta,
                        thickness=float(np.max(nodes[:, 2]) - np.min(nodes[:, 2])),
                        skin_depth_mm=skin_depth,
                        efficiency=induction_efficiency,
                    )
            elif active_positions:
                for x_pos, y_pos in active_positions:
                    rhs += assemble_gaussian_flux_on_triangles(
                        nodes, top_tri, float(x_pos), float(y_pos), q0, r0, gaussian_beta
                    )
            T_iter = solver(rhs)

        temperature = np.asarray(T_iter, dtype=float)

        if track_energy_balance:
            # Heat input (Gaussian surface flux): total power is the sum of the assembled nodal flux vector.
            heat_power_W = 0.0
            if source_mode == "line_gaussian":
                for ln in active_lines:
                    heat_power_W += float(
                        np.sum(
                            assemble_line_gaussian_flux_on_triangles(
                                nodes, top_tri, ln, q0, r0, gaussian_beta
                            )
                        )
                    )
            elif source_mode == "induction_skin":
                for ln in active_lines:
                    heat_power_W += float(
                        np.sum(
                            assemble_induction_skin_source_on_tets(
                                nodes,
                                tet,
                                ln,
                                q0,
                                r0,
                                gaussian_beta,
                                thickness=float(np.max(nodes[:, 2]) - np.min(nodes[:, 2])),
                                skin_depth_mm=skin_depth,
                                efficiency=induction_efficiency,
                            )
                        )
                    )
            elif active_positions:
                for x_pos, y_pos in active_positions:
                    heat_power_W += float(
                        np.sum(
                            assemble_gaussian_flux_on_triangles(
                                nodes, top_tri, float(x_pos), float(y_pos), q0, r0, gaussian_beta
                            )
                        )
                    )

            # Convection loss power: ∫ h (T - T_inf) dA, using the assembled Robin operators.
            conv_power_W = 0.0
            if Kb_top_last is not None and rhs_top_last is not None:
                conv_power_W += float(np.sum(Kb_top_last.dot(temperature) - rhs_top_last))
            if Kb_bot_last is not None and rhs_bot_last is not None:
                conv_power_W += float(np.sum(Kb_bot_last.dot(temperature) - rhs_bot_last))

            # Radiation loss power (linearized): treated as an equivalent Robin term.
            rad_power_W = 0.0
            if radiation_emissivity > 0.0:
                if Kr_top_last is not None and rr_top_last is not None:
                    rad_power_W += float(np.sum(Kr_top_last.dot(temperature) - rr_top_last))
                if Kr_bot_last is not None and rr_bot_last is not None:
                    rad_power_W += float(np.sum(Kr_bot_last.dot(temperature) - rr_bot_last))

            Q_in_total_J += float(dt_step) * float(heat_power_W)
            Q_conv_total_J += float(dt_step) * float(conv_power_W)
            Q_rad_total_J += float(dt_step) * float(rad_power_W)

            # Sensible thermal energy relative to reference: U = Σ M_i (T_i - T_ref).
            # Note: When cp_slope != 0, M depends on temperature (approximate accounting).
            if M_last is not None:
                U_sensible_J = float(np.sum(np.asarray(M_last, dtype=float) * (temperature - float(reference_temperature))))

        # Track global peak temperature over time
        step_idx = int(np.argmax(temperature))
        step_max = float(temperature[step_idx])
        if step_max > float(T_max_global):
            T_max_global = step_max
            t_at = float(t)
            if source_mode in line_source_modes and active_lines:
                x_src_at = 0.5 * (float(active_lines[0]["x0"]) + float(active_lines[0]["x1"]))
                y_src_at = 0.5 * (float(active_lines[0]["y0"]) + float(active_lines[0]["y1"]))
            elif active_positions:
                x_src_at = float(active_positions[0][0])
                y_src_at = float(active_positions[0][1])
            idx_at = step_idx

        if return_history:
            temps_history.append(temperature.copy())
            times_history.append(float(t))

        if float(t) >= next_log:
            if source_mode in line_source_modes and active_lines:
                x_disp = 0.5 * (float(active_lines[0]["x0"]) + float(active_lines[0]["x1"]))
            else:
                x_disp = -1.0 if not active_positions else float(active_positions[0][0])
            if adaptive_dt:
                print(
                    f"  Thermal step {step:5d}, t={t:.2f}s, dt={dt_step:.3g}s, x={x_disp:.1f}mm, T_max={float(np.max(temperature)):.2f}K"
                )
            else:
                print(
                    f"  Thermal step {step:5d}/{steps}, t={t:.2f}s, x={x_disp:.1f}mm, T_max={float(np.max(temperature)):.2f}K"
                )
            next_log += log_every

        step += 1
        t += dt_step

    xyz = nodes[int(idx_at)]
    peak = {
        "T_max_global": float(T_max_global),
        "t_at_T_max_global": float(t_at),
        "x_source_at_T_max_global": float(x_src_at),
        "y_source_at_T_max_global": float(y_src_at),
        "idx_at_T_max_global": float(idx_at),
        "x_at_T_max_global": float(xyz[0]),
        "y_at_T_max_global": float(xyz[1]),
        "z_at_T_max_global": float(xyz[2]),
        "induction_skin_depth_mm": float(skin_depth) if source_mode == "induction_skin" else 0.0,
    }

    if track_energy_balance:
        residual_J = float(Q_in_total_J - Q_conv_total_J - Q_rad_total_J - U_sensible_J)
        denom = max(1e-12, float(Q_in_total_J))
        peak.update(
            {
                "Q_in_total_J": float(Q_in_total_J),
                "Q_conv_total_J": float(Q_conv_total_J),
                "Q_rad_total_J": float(Q_rad_total_J),
                "U_sensible_J": float(U_sensible_J),
                "energy_balance_residual_J": residual_J,
                "energy_balance_residual_pct": float(100.0 * residual_J / denom),
            }
        )

    if return_history:
        return np.asarray(temperature, dtype=float), peak, temps_history, times_history
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
    E_elem: np.ndarray | None = None,
    nu_elem: np.ndarray | None = None,
    alpha_elem: np.ndarray | None = None,
    eps_inherent: np.ndarray | None = None,
) -> np.ndarray:
    n_nodes = int(nodes.shape[0])
    n_dof = 3 * n_nodes

    nodes_flat = nodes.reshape(-1).tolist()
    tet_flat = tet.reshape(-1).tolist()

    print("  Assembling elasticity stiffness (C++)...")
    if E_elem is None or nu_elem is None:
        asm = thermo_bindings.assemble_elasticity_3d(nodes_flat, tet_flat, float(E), float(nu))
    else:
        asm = thermo_bindings.assemble_elasticity_3d_per_element(
            nodes_flat,
            tet_flat,
            np.asarray(E_elem, dtype=float).tolist(),
            np.asarray(nu_elem, dtype=float).tolist(),
        )
    K = sp.coo_matrix((asm.values, (asm.rows, asm.cols)), shape=(asm.dof_count, asm.dof_count)).tocsr()

    print("  Computing load vector (C++)...")
    if eps_inherent is None:
        if alpha_elem is None or E_elem is None or nu_elem is None:
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
                thermo_bindings.thermal_load_3d_per_element(
                    nodes_flat,
                    tet_flat,
                    np.asarray(temperature, dtype=float).tolist(),
                    np.asarray(E_elem, dtype=float).tolist(),
                    np.asarray(nu_elem, dtype=float).tolist(),
                    np.asarray(alpha_elem, dtype=float).tolist(),
                    float(reference_temperature),
                ),
                dtype=float,
            )
    else:
        if alpha_elem is None or E_elem is None or nu_elem is None:
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
        else:
            F_th = np.asarray(
                thermo_bindings.thermal_load_3d_with_inherent_per_element(
                    nodes_flat,
                    tet_flat,
                    np.asarray(temperature, dtype=float).tolist(),
                    np.asarray(eps_inherent, dtype=float).tolist(),
                    np.asarray(E_elem, dtype=float).tolist(),
                    np.asarray(nu_elem, dtype=float).tolist(),
                    np.asarray(alpha_elem, dtype=float).tolist(),
                    float(reference_temperature),
                ),
                dtype=float,
            )

    fixed, free = _resolve_mechanics_dofs(nodes, bottom_nodes, Lx, Ly, bc)

    print(f"  Solving mechanics: {free.size} free DOFs ({n_dof} total)")
    u_free = spla.spsolve(K[free, :][:, free], F_th[free])

    u = np.zeros(n_dof, dtype=float)
    u[free] = u_free
    return u.reshape(-1, 3)


def _resolve_mechanics_dofs(
    nodes: np.ndarray,
    bottom_nodes: np.ndarray,
    Lx: float,
    Ly: float,
    bc: str,
) -> tuple[np.ndarray, np.ndarray]:
    n_nodes = int(nodes.shape[0])
    n_dof = 3 * n_nodes

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
    elif bc_mode == "bottom_frictionless":
        for nid in bottom_nodes:
            nid_int = int(nid)
            fixed.append(3 * nid_int + 2)

        exclude: set[int] = set()
        a = _nearest_node(bottom_nodes, (0.0, 0.0, 0.0), exclude)
        exclude.add(a)
        b = _nearest_node(bottom_nodes, (float(Lx), 0.0, 0.0), exclude)

        fixed.extend([3 * a + 0, 3 * a + 1])
        fixed.extend([3 * b + 1])
    elif bc_mode == "centerline_fixed":
        tol_y = max(1e-6, float(Ly) * 1e-4)
        center_nodes = np.where(np.isclose(nodes[:, 1], float(Ly) / 2.0, atol=tol_y))[0]
        for nid in center_nodes:
            nid_int = int(nid)
            fixed.extend([3 * nid_int + 0, 3 * nid_int + 1, 3 * nid_int + 2])
    elif bc_mode == "corner_pins":
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
        raise ValueError(
            f"Unknown bc mode: {bc}. Use bottom_fixed, bottom_frictionless, centerline_fixed, or corner_pins"
        )

    fixed = np.asarray(sorted(set(fixed)), dtype=int)
    all_dofs = np.arange(n_dof, dtype=int)
    free = np.setdiff1d(all_dofs, fixed)
    return fixed, free


def solve_mechanics_3d_elastoplastic(
    nodes: np.ndarray,
    tet: np.ndarray,
    temperature: np.ndarray,
    bottom_nodes: np.ndarray,
    Lx: float,
    Ly: float,
    thickness: float,
    bc: str,
    reference_temperature: float,
    E_elem: np.ndarray,
    nu_elem: np.ndarray,
    alpha_elem: np.ndarray,
    sigma_y0: float,
    H_iso: float,
    max_iters: int = 3,
    tol: float = 1e-6,
    u_prev: np.ndarray | None = None,
    epsp_state: np.ndarray | None = None,
    epbar_state: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n_nodes = int(nodes.shape[0])
    n_dof = 3 * n_nodes
    n_elem = int(tet.shape[0])

    nodes_flat = nodes.reshape(-1).tolist()
    tet_flat = tet.reshape(-1).tolist()

    if epsp_state is None:
        epsp_state = np.zeros((n_elem, 6), dtype=float)
    if epbar_state is None:
        epbar_state = np.zeros(n_elem, dtype=float)

    fixed, free = _resolve_mechanics_dofs(nodes, bottom_nodes, Lx, Ly, bc)

    print(f"  Solving elastoplastic mechanics: {free.size} free DOFs ({n_dof} total)")

    F_th = np.asarray(
        thermo_bindings.thermal_load_3d_per_element(
            nodes_flat,
            tet_flat,
            np.asarray(temperature, dtype=float).tolist(),
            np.asarray(E_elem, dtype=float).tolist(),
            np.asarray(nu_elem, dtype=float).tolist(),
            np.asarray(alpha_elem, dtype=float).tolist(),
            float(reference_temperature),
        ),
        dtype=float,
    )

    if u_prev is None:
        u = np.zeros(n_dof, dtype=float)
    else:
        u = np.asarray(u_prev, dtype=float).reshape(-1)
    for it in range(max(1, int(max_iters))):
        asm = thermo_bindings.assemble_elastoplastic_3d_step(
            nodes_flat,
            tet_flat,
            u.tolist(),
            np.asarray(temperature, dtype=float).tolist(),
            np.asarray(epsp_state, dtype=float).reshape(-1).tolist(),
            np.asarray(epbar_state, dtype=float).tolist(),
            np.asarray(E_elem, dtype=float).tolist(),
            np.asarray(nu_elem, dtype=float).tolist(),
            np.asarray(alpha_elem, dtype=float).tolist(),
            float(reference_temperature),
            float(sigma_y0),
            float(H_iso),
        )

        K = sp.coo_matrix(
            (asm.stiffness.values, (asm.stiffness.rows, asm.stiffness.cols)),
            shape=(asm.stiffness.dof_count, asm.stiffness.dof_count),
        ).tocsr()
        F_int = np.asarray(asm.internal_force, dtype=float)

        epsp_state = np.asarray(asm.epsp, dtype=float).reshape(n_elem, 6)
        epbar_state = np.asarray(asm.epbar, dtype=float)

        rhs = F_th - F_int
        du_free = spla.spsolve(K[free, :][:, free], rhs[free])
        u[free] += du_free

        du_norm = float(np.linalg.norm(du_free))
        u_norm = max(1e-12, float(np.linalg.norm(u[free])))
        print(f"    ep-iter {it+1}: |du|={du_norm:.3e}, rel={du_norm / u_norm:.3e}")
        if du_norm / u_norm <= tol:
            break

    return u.reshape(-1, 3), epsp_state, epbar_state


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
    heat_lines: list[dict[str, float]] | None,
    out_dir: Path,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if heat_lines is None:
        heat_lines = _build_heat_lines_from_ys(float(Lx), [float(y) for y in heat_ys])
    heat_lines = _prepare_heat_lines(list(heat_lines))

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
    plt.colorbar(sc, ax=ax, label="w (mm, negative = downward)")
    ax.set_aspect("equal")
    ax.set_title("Out-of-plane deflection on top surface (negative = downward)")
    ax.set_xlabel("x (mm)")
    ax.set_ylabel("y (mm)")
    ax.annotate(
        "down (−)",
        xy=(0.96, 0.08),
        xytext=(0.96, 0.22),
        xycoords="axes fraction",
        textcoords="axes fraction",
        arrowprops=dict(arrowstyle="-|>", color="black", lw=1.0),
        ha="center",
        va="bottom",
        fontsize=9,
    )
    plt.tight_layout()
    plt.savefig(out_dir / "deflection_top.png", dpi=160)
    plt.close()

    # 3D deflected surface (triangulate from the existing top surface triangles)
    if top_tri.size:
        # Keep only triangles fully on top surface
        top_node_set = set(np.where(top_mask)[0].tolist())
        tri_top = np.asarray(
            [t for t in top_tri if int(t[0]) in top_node_set and int(t[1]) in top_node_set and int(t[2]) in top_node_set],
            dtype=int,
        )
        if tri_top.size:
            # remap to local indexing for plot_trisurf
            top_global = np.where(top_mask)[0]
            global_to_local = -np.ones(nodes.shape[0], dtype=int)
            global_to_local[top_global] = np.arange(top_global.size, dtype=int)
            tri_local = global_to_local[tri_top]

            fig = plt.figure(figsize=(12, 8))
            ax = fig.add_subplot(111, projection="3d")
            scale = 1.0
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
            fig.colorbar(surf, ax=ax, shrink=0.55, label="w (mm, negative = downward)")
            ax.set_title("Deflected top surface (no scaling)")
            ax.set_xlabel("x (mm)")
            ax.set_ylabel("y (mm)")
            ax.set_zlabel("w (mm, negative = downward)")
            ax.invert_zaxis()
            ax.quiver(
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                -0.1,
                color="black",
                linewidth=1.0,
                arrow_length_ratio=0.2,
            )
            ax.text(0.0, 0.0, -0.12, "down (−)", color="black", fontsize=9)
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
            fig.colorbar(surf2, ax=ax, shrink=0.55, label="w (mm, negative = downward)")
            ax.set_title("Undeformed (gray) vs deformed (no scaling)")
            ax.set_xlabel("x (mm)")
            ax.set_ylabel("y (mm)")
            ax.set_zlabel("w (mm, negative = downward)")
            ax.invert_zaxis()
            ax.quiver(
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                -0.1,
                color="black",
                linewidth=1.0,
                arrow_length_ratio=0.2,
            )
            ax.text(0.0, 0.0, -0.12, "down (−)", color="black", fontsize=9)
            plt.tight_layout()
            plt.savefig(out_dir / "deflection_3d_overlay.png", dpi=160)
            plt.close()

    # Heating line profiles (top surface near each heat line)
    band = max(Ly / 40.0, 1e-9)
    colors = ["tab:blue", "tab:green", "tab:orange", "tab:purple", "tab:red"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    any_line = False
    xy_top = np.column_stack([x_top, y_top])
    for i, ln in enumerate(heat_lines):
        dist = _distance_to_segment(xy_top, ln)
        mask = dist < band
        if np.count_nonzero(mask) < 3:
            continue
        any_line = True
        s = _along_line_coordinate(xy_top[mask], ln)
        sort_idx = np.argsort(s)
        s = s[sort_idx]
        T_c = T_top[mask][sort_idx]
        w_c = w_top[mask][sort_idx]

        label = f"({ln['x0']:.0f},{ln['y0']:.0f})→({ln['x1']:.0f},{ln['y1']:.0f})"
        c = colors[i % len(colors)]
        ax1.plot(s, T_c, ".-", color=c, linewidth=2, label=label)
        ax2.plot(s, w_c, ".-", color=c, linewidth=2, label=label)

    if any_line:
        ax1.set_ylabel("T (K)")
        ax1.grid(True, alpha=0.3)
        ax1.set_title("Along heating line(s) (top surface)")
        ax1.legend(loc="best")

        ax2.set_xlabel("s along line (mm)")
        ax2.set_ylabel("w (mm, negative = downward)")
        ax2.axhline(0.0, color="k", linestyle="--", linewidth=0.8)
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc="best")
        ax2.annotate(
            "down (−)",
            xy=(0.98, 0.12),
            xytext=(0.98, 0.28),
            xycoords="axes fraction",
            textcoords="axes fraction",
            arrowprops=dict(arrowstyle="-|>", color="black", lw=1.0),
            ha="center",
            va="bottom",
            fontsize=9,
        )

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
    ax.set_ylabel("w (mm, negative = downward)")
    ax.set_title(f"Width camber profile near x≈{x0:.1f} mm (band ±{x_band:.1f} mm)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    ax.annotate(
        "down (−)",
        xy=(0.98, 0.12),
        xytext=(0.98, 0.28),
        xycoords="axes fraction",
        textcoords="axes fraction",
        arrowprops=dict(arrowstyle="-|>", color="black", lw=1.0),
        ha="center",
        va="bottom",
        fontsize=9,
    )
    plt.tight_layout()
    plt.savefig(out_dir / "camber_width_profile.png", dpi=160)
    csv_path = out_dir / "camber_width_profile.csv"
    header = "y_mm,w_mid_mm,w_top_mm,w_bot_mm"
    np.savetxt(csv_path, np.column_stack([centers, w_mid, w_top_mean, w_bot_mean]), delimiter=",", header=header)
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
        "--heat-lines",
        type=str,
        default=None,
        help=(
            "JSON list of line segments for arbitrary orientations. "
            "Each item can be [x0,y0,x1,y1] or {x0,y0,x1,y1}. "
            "You can also pass a file path or '@file.json'."
        ),
    )
    parser.add_argument(
        "--heat-lines-file",
        type=str,
        default=None,
        help="Path to JSON file containing a list of heat line segments.",
    )

    parser.add_argument(
        "--heat-mode",
        type=str,
        default="simultaneous",
        choices=["simultaneous", "sequential"],
        help="Heating mode: simultaneous (all lines at once) or sequential (multi-pass, one line after another).",
    )
    parser.add_argument(
        "--heat-source-mode",
        type=str,
        default="moving_gaussian",
        choices=["moving_gaussian", "line_gaussian", "induction_skin"],
        help=(
            "Heat source model: moving_gaussian scans a localized source along each line; "
            "line_gaussian applies a stationary Gaussian band along each active full line "
            "(induction-style heating); induction_skin applies a volumetric skin-depth "
            "Joule heat source below the active full line."
        ),
    )
    parser.add_argument("--induction-frequency", type=float, default=10000.0, help="induction frequency (Hz)")
    parser.add_argument(
        "--induction-relative-permeability",
        type=float,
        default=100.0,
        help="relative magnetic permeability used for skin-depth estimate",
    )
    parser.add_argument(
        "--induction-electrical-resistivity",
        type=float,
        default=2.5e-7,
        help="electrical resistivity for skin-depth estimate (ohm m)",
    )
    parser.add_argument(
        "--induction-efficiency",
        type=float,
        default=1.0,
        help="absorbed fraction applied to q0 for induction_skin source",
    )
    parser.add_argument(
        "--pass-repeats",
        type=int,
        default=1,
        help="Repeat the sequential pass list N times (ignored in simultaneous mode).",
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
    parser.add_argument("--adaptive-dt", action="store_true", help="enable adaptive thermal time stepping")
    parser.add_argument("--dt-min", type=float, default=None, help="minimum adaptive dt (s)")
    parser.add_argument("--dt-max", type=float, default=None, help="maximum adaptive dt (s)")
    parser.add_argument("--extra-time", type=float, default=50.0, help="extra time after scanning (s)")

    parser.add_argument("--k", type=float, default=0.045, help="thermal conductivity (W/mm/K)")
    parser.add_argument("--k-slope", type=float, default=0.0, help="linear k(T) slope: k=k0*(1+k_slope*(T-T_ref))")
    parser.add_argument("--rho", type=float, default=7.85e-6, help="density (kg/mm^3)")
    parser.add_argument("--cp", type=float, default=500.0, help="specific heat (J/kg/K)")
    parser.add_argument("--cp-slope", type=float, default=0.0, help="linear cp(T) slope: cp=cp0*(1+cp_slope*(T-T_ref))")

    parser.add_argument("--h-conv", type=float, default=5e-5, help="convective coefficient (W/mm^2/K)")
    parser.add_argument(
        "--h-conv-top",
        type=float,
        default=None,
        help="top-surface convection (W/mm^2/K). Overrides --h-conv for top if set.",
    )
    parser.add_argument(
        "--h-conv-bottom",
        type=float,
        default=None,
        help="bottom-surface convection (W/mm^2/K). Overrides --h-conv for bottom if set.",
    )
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
        "--quench-h-conv-top",
        type=float,
        default=None,
        help="quench convection on top surface (W/mm^2/K). Overrides --quench-h-conv for top if set.",
    )
    parser.add_argument(
        "--quench-h-conv-bottom",
        type=float,
        default=None,
        help="quench convection on bottom surface (W/mm^2/K). Overrides --quench-h-conv for bottom if set.",
    )
    parser.add_argument(
        "--quench-T-inf",
        type=float,
        default=None,
        help="quench ambient temperature (K). Default: T_inf.",
    )
    parser.add_argument("--emissivity", type=float, default=0.0, help="radiation emissivity (0 disables radiation)")
    parser.add_argument(
        "--gaussian-beta",
        type=float,
        default=2.0,
        help="Gaussian heat flux exponent beta in exp(-beta*r^2/r0^2). Use 3.0 for Li et al. (2023).",
    )
    parser.add_argument("--picard", type=int, default=1, help="Picard iterations per time step for k(T)/cp(T)/radiation")

    parser.add_argument(
        "--energy-balance",
        action="store_true",
        help="Track and report thermal energy balance (input vs convection/radiation losses vs sensible energy).",
    )
    parser.add_argument("--T-inf", type=float, default=293.0, help="ambient temperature (K)")
    parser.add_argument("--T-ref", type=float, default=293.0, help="reference temperature (K)")

    parser.add_argument(
        "--E-table",
        type=str,
        default=None,
        help="Temperature-dependent E table as 'T_C:MPa,...' (e.g., '20:205000,250:187000').",
    )
    parser.add_argument(
        "--nu-table",
        type=str,
        default=None,
        help="Temperature-dependent nu table as 'T_C:nu,...'",
    )
    parser.add_argument(
        "--alpha-table",
        type=str,
        default=None,
        help="Temperature-dependent alpha table as 'T_C:alpha,...' (1/K).",
    )

    parser.add_argument("--E", type=float, default=210e3, help="Young's modulus (MPa)")
    parser.add_argument("--nu", type=float, default=0.3, help="Poisson's ratio")
    parser.add_argument("--alpha", type=float, default=1.2e-5, help="thermal expansion coefficient (1/K)")

    parser.add_argument(
        "--bc",
        type=str,
        default="bottom_fixed",
        choices=["bottom_fixed", "bottom_frictionless", "centerline_fixed", "corner_pins"],
        help=(
            "Mechanical boundary condition: bottom_fixed (table clamped), "
            "bottom_frictionless (table support with in-plane slip), "
            "centerline_fixed (fix along y=Ly/2), or corner_pins (ship-like free plate)."
        ),
    )

    # Inherent strain (plasticity surrogate)
    parser.add_argument("--use-inherent", action="store_true", help="enable inherent strain residual mode")
    parser.add_argument("--eps0", type=float, default=0.0, help="peak inherent isotropic strain (dimensionless, e.g., 2e-4)")
    parser.add_argument("--inh-sigma", type=float, default=20.0, help="inherent band half-width (mm) around heating line")
    parser.add_argument("--inh-zfrac", type=float, default=0.5, help="inherent depth fraction (0..1 of thickness from top)")

    # Elastoplastic (J2) integration
    parser.add_argument("--use-elastoplastic", action="store_true", help="enable J2 elastoplastic mechanics")
    parser.add_argument("--sigma-y0", type=float, default=250.0, help="yield stress at reference temperature (MPa)")
    parser.add_argument("--hardening-H", type=float, default=1000.0, help="isotropic hardening modulus H (MPa)")
    parser.add_argument("--plastic-iters", type=int, default=3, help="max elastoplastic Newton iterations")
    parser.add_argument("--plastic-tol", type=float, default=1e-6, help="relative tolerance for elastoplastic solve")
    parser.add_argument("--strong-coupling", action="store_true", help="advance elastoplastic state each thermal step")
    parser.add_argument("--coupling-mech-iters", type=int, default=1, help="mechanical iterations per thermal step")

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
    heat_lines_raw = _load_heat_lines_arg(args.heat_lines, args.heat_lines_file)
    if heat_lines_raw is None:
        if args.heat_y_list is not None:
            for token in str(args.heat_y_list).split(","):
                token = token.strip()
                if token:
                    heat_ys.append(float(token))
        if args.heat_y is not None:
            heat_ys.append(float(args.heat_y))
        if not heat_ys:
            heat_ys = [float(args.Ly / 2.0)]

        if str(args.heat_mode).lower() == "simultaneous":
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
        else:
            repeats = max(1, int(args.pass_repeats))
            heat_ys = [float(y) for y in heat_ys] * repeats

        heat_lines = _build_heat_lines_from_ys(float(args.Lx), heat_ys)
    else:
        heat_lines = heat_lines_raw
        if str(args.heat_mode).lower() == "sequential":
            repeats = max(1, int(args.pass_repeats))
            heat_lines = list(heat_lines) * repeats
        heat_ys = [float(ln["y0"]) for ln in heat_lines if abs(float(ln["y0"]) - float(ln["y1"])) < 1e-9]

    if heat_lines_raw is None:
        print(f"Heating line(s): y={', '.join(f'{y:.3g}' for y in heat_ys)} mm")
    else:
        print(f"Heating line(s): {len(heat_lines)} segments")
    print(f"BC: {args.bc}")
    print(f"Heat source: {args.heat_source_mode}")

    print("\nStep 1: Meshing...")
    nodes, tet, top_nodes, bottom_nodes, top_tri, bottom_tri = build_plate_mesh_3d(
        args.Lx,
        args.Ly,
        args.thickness,
        args.h,
        args.h_refine,
        args.refine_band,
        heat_ys,
        heat_lines,
        out_dir,
    )
    print(f"  Nodes={nodes.shape[0]} Tets={tet.shape[0]} TopTri={top_tri.shape[0]} BottomTri={bottom_tri.shape[0]}")

    prepared_lines = _prepare_heat_lines(list(heat_lines))
    lengths = [float(ln["length"]) for ln in prepared_lines]
    max_len = max(lengths) if lengths else float(args.Lx)
    scan_time_per_pass = float(max_len) / float(args.velocity)
    if str(args.heat_mode).lower() == "sequential":
        n_passes = int(len(prepared_lines))
        scan_time_total = sum(float(ln["length"]) / float(args.velocity) for ln in prepared_lines)
        if n_passes > 1:
            scan_time_total += float(max(0.0, n_passes - 1)) * float(max(0.0, args.pass_gap))
    else:
        scan_time_total = float(scan_time_per_pass)

    # Backward-compatible name used in summary/metadata
    scan_time = float(scan_time_total)

    total_time = float(scan_time_total) + float(args.extra_time)
    steps = int(np.ceil(total_time / args.dt))

    h_conv_top = float(args.h_conv_top) if args.h_conv_top is not None else float(args.h_conv)
    h_conv_bottom = float(args.h_conv_bottom) if args.h_conv_bottom is not None else float(args.h_conv)

    quench_start = None
    quench_h_conv_top = None
    quench_h_conv_bottom = None
    quench_T_inf = None
    if args.quench:
        quench_start = float(scan_time_total) if args.quench_start is None else float(args.quench_start)
        if args.quench_h_conv_top is not None:
            quench_h_conv_top = float(args.quench_h_conv_top)
        elif args.quench_h_conv is not None:
            quench_h_conv_top = float(args.quench_h_conv)
        else:
            quench_h_conv_top = float(h_conv_top)

        if args.quench_h_conv_bottom is not None:
            quench_h_conv_bottom = float(args.quench_h_conv_bottom)
        elif args.quench_h_conv is not None:
            quench_h_conv_bottom = float(args.quench_h_conv)
        else:
            quench_h_conv_bottom = float(h_conv_bottom)
        quench_T_inf = float(args.T_inf) if args.quench_T_inf is None else float(args.quench_T_inf)

    print("\nStep 2: Thermal solve...")
    print(
        f"  scan_time_per_pass={scan_time_per_pass:.2f}s scan_time_total={scan_time_total:.2f}s total_time={total_time:.2f}s steps={steps}"
    )
    q0_used = float(args.q0)
    temperature = None
    thermal_peak = None
    temps_history: list[np.ndarray] | None = None
    times_history: list[float] | None = None

    if args.target_Tmax is not None:
        target = float(args.target_Tmax)
        tol = float(args.target_Tmax_tol)
        print(f"  Auto-tuning q0 to target peak ~{target:.1f}K (tol {tol:.1f}K)")

        max_tune_iters = max(1, int(args.target_Tmax_iters))
        for it in range(max_tune_iters):
            temperature, thermal_peak = solve_thermal_3d_with_peak(
                nodes=nodes,
                tet=tet,
                top_tri=top_tri,
                bottom_tri=bottom_tri,
                Lx=args.Lx,
                Ly=args.Ly,
                heat_ys=heat_ys,
                heat_lines=heat_lines,
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
                h_conv_top=h_conv_top,
                h_conv_bottom=h_conv_bottom,
                ambient_temperature=args.T_inf,
                reference_temperature=args.T_ref,
                k_slope=args.k_slope,
                cp_slope=args.cp_slope,
                radiation_emissivity=args.emissivity,
                picard_iters=args.picard,
                quench_start=quench_start,
                quench_h_conv_top=quench_h_conv_top,
                quench_h_conv_bottom=quench_h_conv_bottom,
                quench_ambient_temperature=quench_T_inf,
                gaussian_beta=args.gaussian_beta,
                adaptive_dt=bool(args.adaptive_dt),
                total_time=total_time,
                dt_min=args.dt_min,
                dt_max=args.dt_max,
                track_energy_balance=bool(args.energy_balance),
                heat_source_mode=str(args.heat_source_mode),
                induction_frequency=float(args.induction_frequency),
                induction_relative_permeability=float(args.induction_relative_permeability),
                induction_electrical_resistivity=float(args.induction_electrical_resistivity),
                induction_efficiency=float(args.induction_efficiency),
            )

            peak = float(thermal_peak["T_max_global"])
            err = peak - target
            print(f"    tune iter {it+1}: q0={q0_used:.6g}, peak={peak:.2f}K, err={err:+.2f}K")
            if abs(err) <= tol:
                break
            if it == max_tune_iters - 1:
                break

            # Scale q0 assuming approximately linear response in (T_peak - T_ref)
            denom = max(1e-9, peak - float(args.T_ref))
            numer = max(1e-9, target - float(args.T_ref))
            scale = numer / denom
            scale = float(np.clip(scale, 0.2, 5.0))
            q0_used *= scale

        print(f"  Tuned q0_used={q0_used:.6g} (initial {float(args.q0):.6g})")

        if args.use_elastoplastic and args.strong_coupling:
            temperature, thermal_peak, temps_history, times_history = solve_thermal_3d_with_peak(
                nodes=nodes,
                tet=tet,
                top_tri=top_tri,
                bottom_tri=bottom_tri,
                Lx=args.Lx,
                Ly=args.Ly,
                heat_ys=heat_ys,
                heat_lines=heat_lines,
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
                h_conv_top=h_conv_top,
                h_conv_bottom=h_conv_bottom,
                ambient_temperature=args.T_inf,
                reference_temperature=args.T_ref,
                k_slope=args.k_slope,
                cp_slope=args.cp_slope,
                radiation_emissivity=args.emissivity,
                picard_iters=args.picard,
                quench_start=quench_start,
                quench_h_conv_top=quench_h_conv_top,
                quench_h_conv_bottom=quench_h_conv_bottom,
                quench_ambient_temperature=quench_T_inf,
                gaussian_beta=args.gaussian_beta,
                adaptive_dt=bool(args.adaptive_dt),
                total_time=total_time,
                dt_min=args.dt_min,
                dt_max=args.dt_max,
                return_history=True,
                track_energy_balance=bool(args.energy_balance),
                heat_source_mode=str(args.heat_source_mode),
                induction_frequency=float(args.induction_frequency),
                induction_relative_permeability=float(args.induction_relative_permeability),
                induction_electrical_resistivity=float(args.induction_electrical_resistivity),
                induction_efficiency=float(args.induction_efficiency),
            )
    else:
        if args.use_elastoplastic and args.strong_coupling:
            temperature, thermal_peak, temps_history, times_history = solve_thermal_3d_with_peak(
                nodes=nodes,
                tet=tet,
                top_tri=top_tri,
                bottom_tri=bottom_tri,
                Lx=args.Lx,
                Ly=args.Ly,
                heat_ys=heat_ys,
                heat_lines=heat_lines,
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
                h_conv_top=h_conv_top,
                h_conv_bottom=h_conv_bottom,
                ambient_temperature=args.T_inf,
                reference_temperature=args.T_ref,
                k_slope=args.k_slope,
                cp_slope=args.cp_slope,
                radiation_emissivity=args.emissivity,
                picard_iters=args.picard,
                quench_start=quench_start,
                quench_h_conv_top=quench_h_conv_top,
                quench_h_conv_bottom=quench_h_conv_bottom,
                quench_ambient_temperature=quench_T_inf,
                gaussian_beta=args.gaussian_beta,
                adaptive_dt=bool(args.adaptive_dt),
                total_time=total_time,
                dt_min=args.dt_min,
                dt_max=args.dt_max,
                return_history=True,
                track_energy_balance=bool(args.energy_balance),
                heat_source_mode=str(args.heat_source_mode),
                induction_frequency=float(args.induction_frequency),
                induction_relative_permeability=float(args.induction_relative_permeability),
                induction_electrical_resistivity=float(args.induction_electrical_resistivity),
                induction_efficiency=float(args.induction_efficiency),
            )
        else:
            temperature, thermal_peak = solve_thermal_3d_with_peak(
                nodes=nodes,
                tet=tet,
                top_tri=top_tri,
                bottom_tri=bottom_tri,
                Lx=args.Lx,
                Ly=args.Ly,
                heat_ys=heat_ys,
                heat_lines=heat_lines,
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
                h_conv_top=h_conv_top,
                h_conv_bottom=h_conv_bottom,
                ambient_temperature=args.T_inf,
                reference_temperature=args.T_ref,
                k_slope=args.k_slope,
                cp_slope=args.cp_slope,
                radiation_emissivity=args.emissivity,
                picard_iters=args.picard,
                quench_start=quench_start,
                quench_h_conv_top=quench_h_conv_top,
                quench_h_conv_bottom=quench_h_conv_bottom,
                quench_ambient_temperature=quench_T_inf,
                gaussian_beta=args.gaussian_beta,
                adaptive_dt=bool(args.adaptive_dt),
                total_time=total_time,
                dt_min=args.dt_min,
                dt_max=args.dt_max,
                track_energy_balance=bool(args.energy_balance),
                heat_source_mode=str(args.heat_source_mode),
                induction_frequency=float(args.induction_frequency),
                induction_relative_permeability=float(args.induction_relative_permeability),
                induction_electrical_resistivity=float(args.induction_electrical_resistivity),
                induction_efficiency=float(args.induction_efficiency),
            )

    assert temperature is not None
    assert thermal_peak is not None
    print(f"  T range: [{float(np.min(temperature)):.2f}, {float(np.max(temperature)):.2f}] K")

    print("\nStep 3: Mechanics solve...")
    if args.strong_coupling and not args.use_elastoplastic:
        print("  Note: strong_coupling is only applied with elastoplastic mode; using single-step elasticity.")
    eps_inherent = None
    epsp_state = None
    epbar_state = None
    if args.use_elastoplastic and args.use_inherent:
        print("  Note: use_elastoplastic overrides use_inherent; ignoring inherent strain.")
    if (not args.use_elastoplastic) and args.use_inherent and args.eps0 != 0.0:
        # Simple inherent strain field: band around heating line on the top portion of thickness.
        band = float(args.inh_sigma)
        band_w = np.zeros(nodes.shape[0], dtype=float)
        xy = nodes[:, :2]
        for ln in _prepare_heat_lines(list(heat_lines)):
            dist = _distance_to_segment(xy, ln)
            band_w += np.exp(-0.5 * (dist / max(1e-9, band)) ** 2)

        z_cut = float(args.thickness) * float(np.clip(args.inh_zfrac, 0.0, 1.0))
        z_mask = (nodes[:, 2] >= float(args.thickness) - z_cut).astype(float)

        eps_inherent = float(args.eps0) * band_w * z_mask

    E_table = _parse_temp_table(args.E_table)
    nu_table = _parse_temp_table(args.nu_table)
    alpha_table = _parse_temp_table(args.alpha_table)

    E_elem = None
    nu_elem = None
    alpha_elem = None
    if E_table is not None or nu_table is not None or alpha_table is not None:
        if E_table is None or nu_table is None or alpha_table is None:
            raise ValueError("E_table, nu_table, and alpha_table must all be set together.")
        if tet.size % 4 != 0:
            raise ValueError("Invalid tet connectivity for element mapping")
        tet_nodes = tet.reshape(-1, 4)
        t_elem = 0.25 * (temperature[tet_nodes[:, 0]] + temperature[tet_nodes[:, 1]] +
                         temperature[tet_nodes[:, 2]] + temperature[tet_nodes[:, 3]])
        E_elem = _interp_table(t_elem, E_table)
        nu_elem = _interp_table(t_elem, nu_table)
        alpha_elem = _interp_table(t_elem, alpha_table)

    if args.use_elastoplastic and args.strong_coupling:
        if temps_history is None:
            raise RuntimeError("Strong coupling requested but thermal history is missing")
        u_prev = None
        for T_step in temps_history:
            if E_table is None or nu_table is None or alpha_table is None:
                n_elem = int(tet.shape[0])
                E_elem_step = np.full(n_elem, float(args.E), dtype=float)
                nu_elem_step = np.full(n_elem, float(args.nu), dtype=float)
                alpha_elem_step = np.full(n_elem, float(args.alpha), dtype=float)
            else:
                tet_nodes = tet.reshape(-1, 4)
                t_elem = 0.25 * (T_step[tet_nodes[:, 0]] + T_step[tet_nodes[:, 1]] +
                                 T_step[tet_nodes[:, 2]] + T_step[tet_nodes[:, 3]])
                E_elem_step = _interp_table(t_elem, E_table)
                nu_elem_step = _interp_table(t_elem, nu_table)
                alpha_elem_step = _interp_table(t_elem, alpha_table)

            displacement, epsp_state, epbar_state = solve_mechanics_3d_elastoplastic(
                nodes,
                tet,
                T_step,
                bottom_nodes,
                args.Lx,
                args.Ly,
                args.thickness,
                args.bc,
                args.T_ref,
                E_elem=E_elem_step,
                nu_elem=nu_elem_step,
                alpha_elem=alpha_elem_step,
                sigma_y0=args.sigma_y0,
                H_iso=args.hardening_H,
                max_iters=args.coupling_mech_iters,
                tol=args.plastic_tol,
                u_prev=u_prev,
                epsp_state=epsp_state,
                epbar_state=epbar_state,
            )
            u_prev = displacement
    elif args.use_elastoplastic:
        if E_elem is None or nu_elem is None or alpha_elem is None:
            n_elem = int(tet.shape[0])
            E_elem = np.full(n_elem, float(args.E), dtype=float)
            nu_elem = np.full(n_elem, float(args.nu), dtype=float)
            alpha_elem = np.full(n_elem, float(args.alpha), dtype=float)

        displacement, epsp_state, epbar_state = solve_mechanics_3d_elastoplastic(
            nodes,
            tet,
            temperature,
            bottom_nodes,
            args.Lx,
            args.Ly,
            args.thickness,
            args.bc,
            args.T_ref,
            E_elem=E_elem,
            nu_elem=nu_elem,
            alpha_elem=alpha_elem,
            sigma_y0=args.sigma_y0,
            H_iso=args.hardening_H,
            max_iters=args.plastic_iters,
            tol=args.plastic_tol,
        )
    else:
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
            E_elem=E_elem,
            nu_elem=nu_elem,
            alpha_elem=alpha_elem,
            eps_inherent=eps_inherent,
        )
    w = -displacement[:, 2]
    print(f"  w range (negative = downward): [{float(np.min(w)):.6g}, {float(np.max(w)):.6g}] mm")

    print("\nStep 4: Write outputs...")
    plot_outputs(
        nodes,
        tet,
        top_tri,
        temperature,
        displacement,
        args.Lx,
        args.Ly,
        args.thickness,
        heat_ys,
        heat_lines,
        out_dir,
    )

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
            "heat_source_mode": str(args.heat_source_mode),
            "induction_frequency_Hz": float(args.induction_frequency),
            "induction_relative_permeability": float(args.induction_relative_permeability),
            "induction_electrical_resistivity_ohm_m": float(args.induction_electrical_resistivity),
            "induction_efficiency": float(args.induction_efficiency),
            "pass_gap": float(args.pass_gap),
            "pass_repeats": float(args.pass_repeats),
            "heat_y": (None if not heat_ys else float(heat_ys[0])),
            "heat_y_list": [float(y) for y in heat_ys],
            "heat_lines": [
                {"x0": float(ln["x0"]), "y0": float(ln["y0"]), "x1": float(ln["x1"]), "y1": float(ln["y1"])}
                for ln in heat_lines
            ],
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
            "h_conv_top": float(h_conv_top),
            "h_conv_bottom": float(h_conv_bottom),
            "quench": bool(args.quench),
            "quench_start": (None if quench_start is None else float(quench_start)),
            "quench_h_conv": (None if args.quench_h_conv is None else float(args.quench_h_conv)),
            "quench_h_conv_top": (None if quench_h_conv_top is None else float(quench_h_conv_top)),
            "quench_h_conv_bottom": (None if quench_h_conv_bottom is None else float(quench_h_conv_bottom)),
            "quench_T_inf": (None if quench_T_inf is None else float(quench_T_inf)),
            "gaussian_beta": float(args.gaussian_beta),
            "emissivity": float(args.emissivity),
            "picard": float(args.picard),
            "T_inf": float(args.T_inf),
            "T_ref": float(args.T_ref),
            "E_table": (None if args.E_table is None else str(args.E_table)),
            "nu_table": (None if args.nu_table is None else str(args.nu_table)),
            "alpha_table": (None if args.alpha_table is None else str(args.alpha_table)),
            "E": float(args.E),
            "nu": float(args.nu),
            "alpha": float(args.alpha),
            "adaptive_dt": bool(args.adaptive_dt),
            "dt_min": (None if args.dt_min is None else float(args.dt_min)),
            "dt_max": (None if args.dt_max is None else float(args.dt_max)),
            "bc": str(args.bc),
            "use_inherent": bool(args.use_inherent),
            "use_elastoplastic": bool(args.use_elastoplastic),
            "strong_coupling": bool(args.strong_coupling),
            "coupling_mech_iters": int(args.coupling_mech_iters),
            "sigma_y0": float(args.sigma_y0),
            "hardening_H": float(args.hardening_H),
            "plastic_iters": int(args.plastic_iters),
            "plastic_tol": float(args.plastic_tol),
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
            **(
                {
                    "plastic_epbar_min": float(np.min(epbar_state)),
                    "plastic_epbar_max": float(np.max(epbar_state)),
                    "plastic_epbar_mean": float(np.mean(epbar_state)),
                    "plastic_epbar_p95": float(np.percentile(epbar_state, 95.0)),
                    "plastic_elements_active": float(np.count_nonzero(np.asarray(epbar_state) > 0.0)),
                    "plastic_elements_total": float(np.asarray(epbar_state).size),
                }
                if epbar_state is not None
                else {}
            ),
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
