"""Minimal plate heat solve using gmsh for mesh and thermo_bindings for assembly.

Units: geometry is in mm by default. Provide material/loads in the same system: k [W/mm-K],
rho [kg/mm^3], cp [J/kg-K], q [W/mm^3], line_q [W/mm], h_conv [W/mm^2-K]. Use --si to
enter SI (m, W/m-K, kg/m^3, W/m^3, W/m, W/m^2-K); inputs will be converted internally.

Requirements:
- gmsh Python API (pip install gmsh)
- pybind11 + built thermo_bindings (see ../cpp)
- scipy, numpy

Supports explicit Euler (lumped mass) and backward Euler; Dirichlet or Robin/Neumann boundary inputs on the rectangle.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import gmsh
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import matplotlib.pyplot as plt
import matplotlib.tri as mtri

import thermo_bindings as tb


def build_plate_mesh(Lx: float, Ly: float, h: float):
    gmsh.initialize()
    gmsh.model.add("plate")
    p1 = gmsh.model.geo.addPoint(0, 0, 0, h)
    p2 = gmsh.model.geo.addPoint(Lx, 0, 0, h)
    p3 = gmsh.model.geo.addPoint(Lx, Ly, 0, h)
    p4 = gmsh.model.geo.addPoint(0, Ly, 0, h)
    l1 = gmsh.model.geo.addLine(p1, p2)
    l2 = gmsh.model.geo.addLine(p2, p3)
    l3 = gmsh.model.geo.addLine(p3, p4)
    l4 = gmsh.model.geo.addLine(p4, p1)
    cl = gmsh.model.geo.addCurveLoop([l1, l2, l3, l4])
    s = gmsh.model.geo.addPlaneSurface([cl])
    # Enforce target mesh size for consistency across runs
    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", h)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", h)
    gmsh.model.geo.synchronize()
    gmsh.model.mesh.generate(2)

    node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
    nodes = np.array(node_coords, dtype=float).reshape(-1, 3)[:, :2]

    tri = None
    for elem_type in gmsh.model.mesh.getElementTypes(dim=2):
        name = gmsh.model.mesh.getElementProperties(elem_type)[0]
        if "Triangle" in name:
            elem_tags, elem_node_tags = gmsh.model.mesh.getElementsByType(elem_type)
            conn = np.array(elem_node_tags[0], dtype=int)
            if conn.size >= 3 and conn.size % 3 == 0:
                tri = conn - 1  # zero-based
                tri = tri.reshape(-1, 3)
                break
    if tri is None or tri.size == 0:
        # Fallback: pick first 2D element set divisible by 3
        types, _, node_tags = gmsh.model.mesh.getElements(dim=2)
        for tags in node_tags:
            if len(tags) >= 3 and len(tags) % 3 == 0:
                tri = np.array(tags, dtype=int) - 1
                tri = tri.reshape(-1, 3)
                break

    edges = None
    for elem_type in gmsh.model.mesh.getElementTypes(dim=1):
        name = gmsh.model.mesh.getElementProperties(elem_type)[0]
        if "Line" in name:
            _, edge_node_tags = gmsh.model.mesh.getElementsByType(elem_type)
            conn = np.array(edge_node_tags[0], dtype=int)
            if conn.size >= 2 and conn.size % 2 == 0:
                edges = conn - 1  # zero-based
                edges = edges.reshape(-1, 2)
                break
    gmsh.finalize()
    if tri is None or tri.size == 0:
        raise RuntimeError("No triangle elements found")
    if edges is None:
        edges = np.zeros((0, 2), dtype=int)
    return nodes, tri, edges


def boundary_nodes_rect(nodes: np.ndarray, Lx: float, Ly: float, tol: float) -> np.ndarray:
    """Return indices of nodes on the rectangular boundary within tolerance."""
    x = nodes[:, 0]
    y = nodes[:, 1]
    mask = (np.isclose(x, 0.0, atol=tol) | np.isclose(x, Lx, atol=tol) |
            np.isclose(y, 0.0, atol=tol) | np.isclose(y, Ly, atol=tol))
    return np.nonzero(mask)[0]


def assemble_sparse(nodes: np.ndarray, tri: np.ndarray, k: float, rho: float, cp: float):
    asmbl = tb.assemble_heat_2d(nodes.ravel().tolist(), tri.ravel().tolist(), k, rho, cp)
    K = sp.coo_matrix((asmbl.values, (asmbl.rows, asmbl.cols)), shape=(asmbl.node_count, asmbl.node_count)).tocsr()
    M = np.array(asmbl.mass_lumped)
    return K, M


def boundary_matrices(
    nodes: np.ndarray,
    edges: np.ndarray,
    h_conv: float | None = None,
    T_inf: float = 0.0,
    qn: float | None = None,
):
    """Compute Robin (convection) and Neumann flux contributions on boundary edges.

    For an edge with length L and nodes i,j:
      Robin: add h*L/6 [[2,1],[1,2]] to K, rhs += h*T_inf*L/2 [1,1]
      Neumann: rhs += qn*L/2 [1,1] (qn positive into the domain)
    """
    n = nodes.shape[0]
    data = []
    row = []
    col = []
    rhs = np.zeros(n)

    if edges.size == 0:
        return sp.csr_matrix((n, n)), rhs

    for e in edges:
        i, j = int(e[0]), int(e[1])
        xi, yi = nodes[i]
        xj, yj = nodes[j]
        L = float(np.hypot(xj - xi, yj - yi))

        if h_conv is not None and h_conv != 0.0:
            k_local = h_conv * L / 6.0
            # [[2,1],[1,2]] pattern
            contrib = {
                (i, i): 2 * k_local,
                (i, j): 1 * k_local,
                (j, i): 1 * k_local,
                (j, j): 2 * k_local,
            }
            for (r, c), v in contrib.items():
                row.append(r)
                col.append(c)
                data.append(v)
            rhs[i] += h_conv * T_inf * L / 2.0
            rhs[j] += h_conv * T_inf * L / 2.0

        if qn is not None and qn != 0.0:
            rhs[i] += qn * L / 2.0
            rhs[j] += qn * L / 2.0

    Kb = sp.coo_matrix((data, (row, col)), shape=(n, n)).tocsr()
    return Kb, rhs


def moving_gaussian_source(nodes: np.ndarray, Lx: float, Ly: float, 
                          q0: float, r0: float, x_pos: float, y_pos: float = None) -> np.ndarray:
    """Create a nodal source vector (W) for a moving Gaussian heat source.
    
    q(x,y) = q0 * exp(-2 * r^2 / r0^2)
    where r^2 = (x - x_pos)^2 + (y - y_pos)^2
    
    Parameters:
    - q0: peak heat flux (W/mm^2)
    - r0: Gaussian radius (mm), effective heating radius
    - x_pos: current x position of heat source center
    - y_pos: y position of heat source center (default: Ly/2, centerline)
    
    Returns nodal power (W).
    """
    if y_pos is None:
        y_pos = Ly / 2.0
    
    x = nodes[:, 0]
    y = nodes[:, 1]
    
    r_sq = (x - x_pos)**2 + (y - y_pos)**2
    
    # Gaussian distribution
    q_nodal = q0 * np.exp(-2.0 * r_sq / (r0**2))
    
    # Only apply where significant (avoid tiny values everywhere)
    cutoff = q0 * 1e-6
    q_nodal[q_nodal < cutoff] = 0.0
    
    return q_nodal


def line_source_field(nodes: np.ndarray, Lx: float, Ly: float, q_line: float, width: float, gaussian: bool = True) -> np.ndarray:
    """Create a nodal source vector (W) distributed along the centerline y=Ly/2.

    q_line: W/mm along the line. Total injected power is q_line * Lx. Width: characteristic width (mm).
    Returns nodal power; divide by lumped mass externally if using explicit.
    """
    if q_line == 0.0:
        return np.zeros(nodes.shape[0])
    y = nodes[:, 1]
    dist = np.abs(y - Ly * 0.5)
    if gaussian:
        sigma = max(1e-6, width / 2.355)  # FWHM approx
        weight = np.exp(-0.5 * (dist / sigma) ** 2)
    else:
        weight = (dist <= width * 0.5).astype(float)
    # Normalize weights to integrate to q_line over domain length (Lx implicit via mesh density)
    w_sum = weight.sum()
    if w_sum <= 0:
        return np.zeros_like(weight)
    # Scale by plate length so total power integrates to q_line * Lx
    nodal_power = q_line * Lx * weight / w_sum
    return nodal_power


def compute_thermal_deflection(
    nodes: np.ndarray,
    tri: np.ndarray,
    T: np.ndarray,
    thickness: float,
    Lx: float,
    Ly: float,
    E: float = 210e3,
    nu: float = 0.3,
    alpha: float = 1.2e-5,
    T_ref: float = 293.0,
    boundary: str = "simply",
) -> tuple[np.ndarray, np.ndarray]:
    """Compute thermal deflection using plate theory with proper boundary conditions.
    
    Parameters:
    - boundary: "simply" (simply supported), "clamped", or "free"
    
    Returns (w_therm, thermal_strain) where:
    - w_therm: nodal out-of-plane deflection (mm)
    - thermal_strain: in-plane thermal strain at each node
    
    For simply supported edges: w = 0 and M_n = 0 on boundaries
    The thermal moment causes curvature: kappa = alpha * dT / thickness
    """
    # Compute thermal strain and temperature change
    dT = T - T_ref
    eps_th = alpha * dT
    
    # Compute flexural rigidity
    D = E * thickness**3 / (12 * (1 - nu**2))
    
    # Thermal moment per unit width (assuming uniform temp through thickness initially)
    # For a more accurate model: M_th = E*alpha*dT*thickness/(1-nu) for membrane effect
    # But for bending due to thermal gradient: use curvature approach
    
    n = nodes.shape[0]
    w_therm = np.zeros(n)
    
    # Build a simple finite difference or use analytical approximation
    # For thermal loading, approximate using equivalent transverse load
    # q_equiv ~ -D * nabla^2(kappa) where kappa = alpha*dT/t
    
    # Simplified approach: Use superposition of thermal bending moments
    # For simply supported rectangular plate with distributed load
    
    # Method: Compute equivalent distributed load from thermal curvature
    # then solve plate equation with simply supported BC
    
    x = nodes[:, 0]
    y = nodes[:, 1]
    
    # For each node, compute deflection based on thermal loading
    # Using Navier solution for simply supported plate
    if boundary == "simply":
        # Navier series solution approach (simplified)
        # w(x,y) = sum_{m,n} A_mn * sin(m*pi*x/Lx) * sin(n*pi*y/Ly)
        
        # Compute thermal curvature at each node
        kappa_th = alpha * dT / thickness
        
        # For simply supported: use a simplified formulation
        # The thermal moment creates an equivalent load
        # Approximate: w ~ (alpha * dT * thickness) * (shape function)
        
        for i in range(n):
            xi = x[i]
            yi = y[i]
            
            # Simply supported shape function (1st mode approximation)
            # Enhanced with thermal intensity
            shape = np.sin(np.pi * xi / Lx) * np.sin(np.pi * yi / Ly)
            
            # Thermal deflection magnitude
            # Scale by thermal intensity and geometric factors
            w_thermal_local = (alpha * dT[i] * Lx**2) / (np.pi**2 * thickness) * shape
            
            w_therm[i] = w_thermal_local
        
        # Apply boundary conditions: force w=0 at edges
        tol = 1e-6
        boundary_mask = (
            (np.abs(x) < tol) | (np.abs(x - Lx) < tol) |
            (np.abs(y) < tol) | (np.abs(y - Ly) < tol)
        )
        w_therm[boundary_mask] = 0.0
        
    elif boundary == "clamped":
        # Clamped: w = 0 and dw/dn = 0 on boundaries
        # Use exponential decay from interior
        
        kappa_th = alpha * dT / thickness
        
        for i in range(n):
            xi = x[i]
            yi = y[i]
            
            # Distance from boundaries
            dist_x = min(xi, Lx - xi)
            dist_y = min(yi, Ly - yi)
            
            # Boundary influence (decays near edges)
            boundary_factor = (1 - np.exp(-dist_x / (0.1 * Lx))) * (1 - np.exp(-dist_y / (0.1 * Ly)))
            
            # Thermal deflection
            w_therm[i] = (alpha * dT[i] * Lx**2) / (E * thickness) * boundary_factor
        
        tol = 1e-6
        boundary_mask = (
            (np.abs(x) < tol) | (np.abs(x - Lx) < tol) |
            (np.abs(y) < tol) | (np.abs(y - Ly) < tol)
        )
        w_therm[boundary_mask] = 0.0
        
    else:  # free
        # Free edges: no constraints
        w_therm = (alpha * dT * Lx**2) / (E * thickness)
    
    return w_therm, eps_th


def plot_solution(nodes: np.ndarray, tri: np.ndarray, T: np.ndarray, out_dir: Path, 
                 w_therm: np.ndarray | None = None, thickness: float = 10.0,
                 Lx: float = 1000.0, Ly: float = 500.0):
    out_dir.mkdir(parents=True, exist_ok=True)
    triang = mtri.Triangulation(nodes[:, 0], nodes[:, 1], tri)

    fig_mesh, ax_mesh = plt.subplots(figsize=(6, 5))
    ax_mesh.triplot(triang, color="k", linewidth=0.3)
    ax_mesh.text(0.01, 0.99, f"nodes={nodes.shape[0]}, tris={tri.shape[0]}",
                 ha="left", va="top", transform=ax_mesh.transAxes,
                 fontsize=8, bbox=dict(facecolor="white", alpha=0.7, edgecolor="none"))
    ax_mesh.set_title("Mesh (mm)")
    ax_mesh.set_xlabel("x (mm)")
    ax_mesh.set_ylabel("y (mm)")
    ax_mesh.set_aspect("equal")
    fig_mesh.tight_layout()
    fig_mesh.savefig(out_dir / "mesh.png", dpi=150)
    plt.close(fig_mesh)

    fig_T, ax_T = plt.subplots(figsize=(6, 5))
    tpc = ax_T.tripcolor(triang, T, shading="gouraud", cmap="inferno")
    fig_T.colorbar(tpc, ax=ax_T, label="Temperature (K)")
    ax_T.set_title("Temperature field (mm, K)")
    ax_T.set_xlabel("x (mm)")
    ax_T.set_ylabel("y (mm)")
    ax_T.set_aspect("equal")
    fig_T.tight_layout()
    fig_T.savefig(out_dir / "temperature.png", dpi=150)
    plt.close(fig_T)
    
    # Plot temperature along centerline
    y_center = Ly / 2.0
    tol = Ly / 20.0  # tolerance for selecting centerline nodes
    centerline_mask = np.abs(nodes[:, 1] - y_center) < tol
    centerline_nodes = nodes[centerline_mask]
    centerline_T = T[centerline_mask]
    
    # Sort by x coordinate
    sort_idx = np.argsort(centerline_nodes[:, 0])
    x_center = centerline_nodes[sort_idx, 0]
    T_center = centerline_T[sort_idx]
    
    fig_Tc, ax_Tc = plt.subplots(figsize=(8, 5))
    ax_Tc.plot(x_center, T_center, 'b-', linewidth=2, label='Temperature')
    ax_Tc.set_xlabel('x (mm)')
    ax_Tc.set_ylabel('Temperature (K)')
    ax_Tc.set_title(f'Temperature Distribution along Centerline (y={y_center:.1f}mm)')
    ax_Tc.grid(True, alpha=0.3)
    ax_Tc.legend()
    fig_Tc.tight_layout()
    fig_Tc.savefig(out_dir / "temperature_centerline.png", dpi=150)
    plt.close(fig_Tc)
    
    # Plot deflection if computed
    if w_therm is not None:
        fig_w, ax_w = plt.subplots(figsize=(6, 5))
        wpc = ax_w.tripcolor(triang, w_therm, shading="gouraud", cmap="RdBu_r")
        fig_w.colorbar(wpc, ax=ax_w, label="Deflection w (mm)")
        ax_w.set_title(f"Thermal Deflection (thickness={thickness:.1f}mm)")
        ax_w.set_xlabel("x (mm)")
        ax_w.set_ylabel("y (mm)")
        ax_w.set_aspect("equal")
        fig_w.tight_layout()
        fig_w.savefig(out_dir / "deflection.png", dpi=150)
        plt.close(fig_w)
        
        # 3D surface plot of deflection
        from mpl_toolkits.mplot3d import Axes3D
        fig_3d = plt.figure(figsize=(8, 6))
        ax_3d = fig_3d.add_subplot(111, projection='3d')
        ax_3d.plot_trisurf(nodes[:, 0], nodes[:, 1], w_therm, 
                          triangles=tri, cmap='RdBu_r', alpha=0.8)
        ax_3d.set_xlabel('x (mm)')
        ax_3d.set_ylabel('y (mm)')
        ax_3d.set_zlabel('w (mm)')
        ax_3d.set_title('Thermal Deflection Surface')
        fig_3d.tight_layout()
        fig_3d.savefig(out_dir / "deflection_3d.png", dpi=150)
        plt.close(fig_3d)
        
        # Plot deflection along centerline
        w_center = w_therm[centerline_mask][sort_idx]
        
        fig_wc, ax_wc = plt.subplots(figsize=(8, 5))
        ax_wc.plot(x_center, w_center, 'r-', linewidth=2, label='Deflection')
        ax_wc.set_xlabel('x (mm)')
        ax_wc.set_ylabel('Deflection w (mm)')
        ax_wc.set_title(f'Deflection along Centerline (y={y_center:.1f}mm)')
        ax_wc.grid(True, alpha=0.3)
        ax_wc.legend()
        ax_wc.axhline(y=0, color='k', linestyle='--', linewidth=0.5)
        fig_wc.tight_layout()
        fig_wc.savefig(out_dir / "deflection_centerline.png", dpi=150)
        plt.close(fig_wc)
        
        # Combined plot: Temperature and Deflection
        fig_comb, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
        
        ax1.plot(x_center, T_center, 'b-', linewidth=2)
        ax1.set_ylabel('Temperature (K)', color='b')
        ax1.tick_params(axis='y', labelcolor='b')
        ax1.set_title('Temperature and Deflection along Centerline')
        ax1.grid(True, alpha=0.3)
        
        ax2.plot(x_center, w_center, 'r-', linewidth=2)
        ax2.set_xlabel('x (mm)')
        ax2.set_ylabel('Deflection w (mm)', color='r')
        ax2.tick_params(axis='y', labelcolor='r')
        ax2.axhline(y=0, color='k', linestyle='--', linewidth=0.5)
        ax2.grid(True, alpha=0.3)
        
        fig_comb.tight_layout()
        fig_comb.savefig(out_dir / "centerline_combined.png", dpi=150)
        plt.close(fig_comb)


def explicit_heat(
    K: sp.csr_matrix,
    M: np.ndarray,
    T0: np.ndarray,
    dt: float,
    moving_source: dict | None = None,
    nodes: np.ndarray | None = None,
):
    """Implicit heat solver with optional moving source.
    
    moving_source dict: {'Lx', 'Ly', 'q0', 'r0', 'v', 'y_pos'}
    - v: velocity (mm/s), moves from x=0 to x=Lx
    """
    n = T0.size
    T = T0.copy()
    K_eff = K if Kb is None else K + Kb
    A = sp.diags(M / dt) + K_eff

    rhs_const = np.zeros(n)
    if q_vol is not None and not isinstance(q_vol, dict):
        rhs_const += q_vol
    if rhs_b is not None:
        rhs_const += rhs_b

    if dirichlet_nodes is not None and dirichlet_nodes.size:
        A = A.tolil()
        for idx in dirichlet_nodes:
            A.rows[idx] = [idx]
            A.data[idx] = [1.0]
        A = A.tocsr()
    solver = spla.factorized(A)

    for step in range(steps):
        rhs = (M / dt) * T + rhs_const
        
        # Add moving source if specified
        if moving_source is not None and nodes is not None:
            t = step * dt
            x_pos = moving_source['v'] * t
            if x_pos <= moving_source['Lx']:
                q_moving = moving_gaussian_source(
                    nodes, moving_source['Lx'], moving_source['Ly'],
                    moving_source['q0'], moving_source['r0'], x_pos, 
                    moving_source.get('y_pos')
                )
                rhs += q_moving
        
def implicit_heat(
    K: sp.csr_matrix,
    M: np.ndarray,
    T0: np.ndarray,
    dt: float,
    steps: int,
    q_vol: float | np.ndarray | None = None,
    dirichlet_nodes: np.ndarray | None = None,
    dirichlet_value: float = 0.0,
    Kb: sp.csr_matrix | None = None,
    rhs_b: np.ndarray | None = None,
):
    n = T0.size
    T = T0.copy()
    K_eff = K if Kb is None else K + Kb
    A = sp.diags(M / dt) + K_eff

    rhs_const = np.zeros(n)
    if q_vol is not None:
        rhs_const += q_vol
    if rhs_b is not None:
        rhs_const += rhs_b

    if dirichlet_nodes is not None and dirichlet_nodes.size:
        A = A.tolil()
        for idx in dirichlet_nodes:
            A.rows[idx] = [idx]
            A.data[idx] = [1.0]
        A = A.tocsr()
    solver = spla.factorized(A)

    for _ in range(steps):
        rhs = (M / dt) * T + rhs_const
        if dirichlet_nodes is not None and dirichlet_nodes.size:
            rhs[dirichlet_nodes] = dirichlet_value
        T = solver(rhs)
    return T
moving-source", action="store_true", help="use moving Gaussian heat source")
    parser.add_argument("--q0", type=float, default=5.0, help="peak heat flux for moving source (W/mm^2)")
    parser.add_argument("--r0", type=float, default=15.0, help="Gaussian radius for moving source (mm)")
    parser.add_argument("--velocity", type=float, default=5.0, help="heat source velocity (mm/s)")
    parser.add_argument("--

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--Lx", type=float, default=1.0)
    parser.add_argument("--Ly", type=float, default=1.0)
    parser.add_argument("--h", type=float, default=0.1, help="target element size")
    parser.add_argument("--thickness", type=float, default=10.0, help="plate thickness (mm)")
    parser.add_argument("--k", type=float, default=0.045, help="conductivity (W/mm-K by default)")
    parser.add_argument("--rho", type=float, default=7.85e-6, help="density (kg/mm^3 by default)")
    parser.add_argument("--cp", type=float, default=500.0)
    parser.add_argument("--E", type=float, default=210e3, help="Young's modulus (MPa)")
    parser.add_argument("--nu", type=float, default=0.3, help="Poisson's ratio")
    parser.add_argument("--alpha", type=float, default=1.2e-5, help="thermal expansion coeff (1/K)")
    parser.add_argument("--T-ref", type=float, default=293.0, help="reference temperature (K)")
    parser.add_argument("--dt", type=float, default=1e-4)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--q", type=float, default=0.0, help="volumetric heat source (uniform, W/mm^3)")
    parser.add_argument("--line-q", type=float, default=0.0, help="line heat input (W/mm) applied along centerline")
    parser.add_argument("--line-width", type=float, default=20.0, help="characteristic width (mm) for line heat distribution")
    parser.add_argument("--solver", choices=["explicit", "implicit"], default="explicit")
    parser.add_argument("--bc", action="store_true", help="apply Dirichlet T=bc_value on boundary")
    parser.add_argument("--bc-value", type=float, default=0.0)
    parser.add_argument("--h-conv", type=float, default=0.0, help="convection coefficient (Robin) on boundary; 0 disables")
    parser.add_argument("--T-inf", type=float, default=0.0, help="ambient temperature for convection")
    parser.add_argument("--q-edge", type=float, default=0.0, help="Neumann heat flux on boundary (positive into domain)")
    parser.add_argument("--plot", action="store_true", help="save mesh and temperature plots to outputs/")
    parser.add_argument("--compute-deflection", action="store_true", help="compute and plot thermal deflection")
    parser.afull(nodes.shape[0], args.T_ref if hasattr(args, 'T_ref') else 293.0)
    q_vec = None
    moving_src = None
    
    if args.moving_source:
        # Use moving Gaussian source
        moving_src = {
            'Lx': args.Lx,
            'Ly': args.Ly,
            'q0': args.q0,
            'r0': args.r0,
            'v': args.velocity,
            'y_pos': args.Ly / 2.0
        }
        print(f"Moving source: q0={args.q0} W/mm^2, r0={args.r0} mm, v={args.velocity} mm/s")
        print(f"Scan time: {args.Lx / args.velocity:.2f} s, steps during scan: {int(args.Lx / (args.velocity * args.dt))}")
    elif args.line_q != 0.0:
        q_vec = line_source_field(nodes, args.Lx, args.Ly, args.line_q, args.line_width, gaussian=True)
    elif args.q != 0.0:
        q_vec = np.full(nodes.shape[0], args.q)
    
    bc_nodes = None
    if args.bc:
        bc_nodes = boundary_nodes_rect(nodes, args.Lx, args.Ly, tol=1e-9)

    if args.solver == "explicit":
        T_final = explicit_heat(K, M, T0, args.dt, args.steps, q_vol=q_vec,
                                 dirichlet_nodes=bc_nodes, dirichlet_value=args.bc_value,
                                 Kb=Kb, rhs_b=rhs_b)
    else:
        T_final = implicit_heat(K, M, T0, args.dt, args.steps, q_vol=q_vec,
                                 dirichlet_nodes=bc_nodes, dirichlet_value=args.bc_value,
                                 Kb=Kb, rhs_b=rhs_b, moving_source=moving_src, nodes=nodes
    nodes, tri, edges = build_plate_mesh(args.Lx, args.Ly, args.h)
    K, M = assemble_sparse(nodes, tri, args.k, args.rho, args.cp)

    Kb, rhs_b = boundary_matrices(nodes, edges, h_conv=args.h_conv if args.h_conv != 0.0 else None,
                                  T_inf=args.T_inf, qn=args.q_edge if args.q_edge != 0.0 else None)

    T0 = np.zeros(nodes.shape[0])
    q_vec = None
    if args.line_q != 0.0:
        q_vec = line_source_field(nodes, args.Lx, args.Ly, args.line_q, args.line_width, gaussian=True)
    elif args.q != 0.0:
        q_vec = np.full(nodes.shape[0], args.q)
    bc_nodes = None
    if args.bc:
        bc_nodes = boundary_nodes_rect(nodes, args.Lx, args.Ly, tol=1e-9)

    if args.solver == "explicit":
        T_final = explicit_heat(K, M, T0, args.dt, args.steps, q_vol=q_vec,
                                 dirichlet_nodes=bc_nodes, dirichlet_value=args.bc_value,
                                 Kb=Kb, rhs_b=rhs_b)
    else:
        T_final = implicit_heat(K, M, T0, args.dt, args.steps, q_vol=q_vec,
                                 dirichlet_nodes=bc_nodes, dirichlet_value=args.bc_value,
                                 Kb=Kb, rhs_b=rhs_b)

    print(f"Nodes: {nodes.shape[0]}, Elements: {tri.shape[0]}")
    print(f"Temperature stats: min={T_final.min():.3e}, max={T_final.max():.3e}")

    w_therm = None
    if args.compute_deflection:
        w_therm, eps_th = compute_thermal_deflection(
            nodes, tri, T_final, args.thickness, args.Lx, args.Ly,
            E=args.E, nu=args.nu, alpha=args.alpha, T_ref=args.T_ref,
            boundary=args.boundary
        )
        print(f"Deflection stats: min={w_therm.min():.6e}, max={w_therm.max():.6e}")
        print(f"Thermal strain stats: min={eps_th.min():.6e}, max={eps_th.max():.6e}")

    if args.plot:
        out_dir = Path("outputs")
        plot_solution(nodes, tri, T_final, out_dir, w_therm=w_therm, thickness=args.thickness,
                     Lx=args.Lx, Ly=args.Ly)
        print(f"Saved plots to {out_dir}")

    out = Path("heat_solution.npy")
    np.save(out, T_final)
    print(f"Saved nodal temperatures to {out}")
    
    if w_therm is not None:
        out_w = Path("deflection_solution.npy")
        np.save(out_w, w_therm)
        print(f"Saved nodal deflections to {out_w}")


if __name__ == "__main__":
    main()
