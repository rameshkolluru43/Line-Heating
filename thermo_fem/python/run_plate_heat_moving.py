"""Line heating simulation with moving Gaussian heat source.

Implements Step 3 from development plan: moving heat source along centerline.
"""
import argparse
from pathlib import Path
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
import gmsh

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
    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", h)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", h)
    gmsh.model.geo.synchronize()
    gmsh.model.mesh.generate(2)

    node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
    nodes = np.array(node_coords, dtype=float).reshape(-1, 3)[:, :2]

    types, _, node_tags_elem = gmsh.model.mesh.getElements(dim=2)
    tri = np.array(node_tags_elem[0], dtype=int) - 1
    tri = tri.reshape(-1, 3)

    types_1d, _, node_tags_1d = gmsh.model.mesh.getElements(dim=1)
    edges = np.array(node_tags_1d[0], dtype=int) - 1
    edges = edges.reshape(-1, 2) if node_tags_1d[0].size > 0 else np.zeros((0, 2), dtype=int)

    gmsh.finalize()
    return nodes, tri, edges


def assemble_heat_matrices(nodes: np.ndarray, tri: np.ndarray, k: float, rho: float, cp: float):
    """Assemble stiffness K and lumped mass M for 2D heat conduction."""
    n_nodes = nodes.shape[0]
    n_elem = tri.shape[0]
    
    K_data, K_i, K_j = [], [], []
    M_lumped = np.zeros(n_nodes)
    
    for el in tri:
        coords = nodes[el]
        x = coords[:, 0]
        y = coords[:, 1]
        
        area = 0.5 * abs((x[1] - x[0]) * (y[2] - y[0]) - (x[2] - x[0]) * (y[1] - y[0]))
        
        # Gradients
        b = np.array([y[1] - y[2], y[2] - y[0], y[0] - y[1]]) / (2 * area)
        c = np.array([x[2] - x[1], x[0] - x[2], x[1] - x[0]]) / (2 * area)
        
        K_elem = k * area * (np.outer(b, b) + np.outer(c, c))
        
        for i in range(3):
            for j in range(3):
                K_data.append(K_elem[i, j])
                K_i.append(el[i])
                K_j.append(el[j])
        
        M_elem = rho * cp * area / 3.0
        for i in range(3):
            M_lumped[el[i]] += M_elem
    
    K = sp.coo_matrix((K_data, (K_i, K_j)), shape=(n_nodes, n_nodes)).tocsr()
    return K, M_lumped


def moving_gaussian_source(nodes: np.ndarray, x_pos: float, y_pos: float, q0: float, r0: float):
    """Gaussian heat flux: q = q0 * exp(-2*r^2/r0^2)"""
    x = nodes[:, 0]
    y = nodes[:, 1]
    r_sq = (x - x_pos)**2 + (y - y_pos)**2
    q = q0 * np.exp(-2.0 * r_sq / r0**2)
    q[q < q0 * 1e-6] = 0.0
    return q


def boundary_convection(nodes: np.ndarray, edges: np.ndarray, h_conv: float, T_inf: float):
    """Robin BC: h_conv * (T - T_inf) on edges."""
    n = nodes.shape[0]
    data, row, col = [], [], []
    rhs = np.zeros(n)
    
    if edges.size == 0:
        return sp.csr_matrix((n, n)), rhs
    
    for e in edges:
        i, j = int(e[0]), int(e[1])
        L = float(np.linalg.norm(nodes[i] - nodes[j]))
        k_local = h_conv * L / 6.0
        
        for (r, c), val in [((i, i), 2*k_local), ((i, j), k_local), 
                            ((j, i), k_local), ((j, j), 2*k_local)]:
            row.append(r)
            col.append(c)
            data.append(val)
        
        rhs[i] += h_conv * T_inf * L / 2.0
        rhs[j] += h_conv * T_inf * L / 2.0
    
    Kb = sp.coo_matrix((data, (row, col)), shape=(n, n)).tocsr()
    return Kb, rhs


def solve_moving_heat(nodes, tri, edges, Lx, Ly, k, rho, cp, dt, steps, 
                     q0, r0, velocity, h_conv, T_inf, T_ref):
    """Transient heat solve with moving source."""
    K, M = assemble_heat_matrices(nodes, tri, k, rho, cp)
    Kb, rhs_b = boundary_convection(nodes, edges, h_conv, T_inf)
    
    A = sp.diags(M / dt) + K + Kb
    solver = spla.factorized(A)
    
    T = np.full(nodes.shape[0], T_ref)
    y_center = Ly / 2.0
    
    for step in range(steps):
        t = step * dt
        x_pos = velocity * t
        
        rhs = (M / dt) * T + rhs_b
        
        if x_pos <= Lx:
            q_moving = moving_gaussian_source(nodes, x_pos, y_center, q0, r0)
            rhs += q_moving
        
        T = solver(rhs)
        
        if step % 50 == 0:
            print(f"Step {step}/{steps}, t={t:.2f}s, x_pos={x_pos:.1f}mm, T_max={T.max():.1f}K")
    
    return T


def compute_deflection_simple(nodes, tri, T, thickness, Lx, Ly, E, nu, alpha, T_ref):
    """Simplified thermal deflection for free plate."""
    dT = T - T_ref
    eps_th = alpha * dT
    
    x = nodes[:, 0]
    y = nodes[:, 1]
    
    # Simple analytical approximation for thermal bending
    w = np.zeros(len(nodes))
    for i in range(len(nodes)):
        # Shape function (free plate, thermal moment)
        shape = (1 - (2*x[i]/Lx - 1)**2) * (1 - (2*y[i]/Ly - 1)**2)
        w[i] = (alpha * dT[i] * Lx**2) / (E * thickness) * shape * 100  # scale factor
    
    return w, eps_th


def plot_results(nodes, tri, T, w, Lx, Ly, thickness, out_dir):
    """Generate all output plots."""
    out_dir.mkdir(parents=True, exist_ok=True)
    triang = mtri.Triangulation(nodes[:, 0], nodes[:, 1], tri)
    
    # Temperature field
    fig, ax = plt.subplots(figsize=(10, 6))
    tpc = ax.tripcolor(triang, T, shading='gouraud', cmap='inferno')
    plt.colorbar(tpc, ax=ax, label='Temperature (K)')
    ax.set_xlabel('x (mm)')
    ax.set_ylabel('y (mm)')
    ax.set_title(f'Temperature (plate {Lx}×{Ly}×{thickness}mm)')
    ax.set_aspect('equal')
    plt.tight_layout()
    plt.savefig(out_dir / 'temperature.png', dpi=150)
    plt.close()
    
    # Deflection field
    if w is not None:
        fig, ax = plt.subplots(figsize=(10, 6))
        wpc = ax.tripcolor(triang, w, shading='gouraud', cmap='RdBu_r')
        plt.colorbar(wpc, ax=ax, label='Deflection (mm)')
        ax.set_xlabel('x (mm)')
        ax.set_ylabel('y (mm)')
        ax.set_title('Thermal Deflection')
        ax.set_aspect('equal')
        plt.tight_layout()
        plt.savefig(out_dir / 'deflection.png', dpi=150)
        plt.close()
        
        # 3D deflection
        from mpl_toolkits.mplot3d import Axes3D
        fig = plt.figure(figsize=(10, 7))
        ax = fig.add_subplot(111, projection='3d')
        ax.plot_trisurf(nodes[:, 0], nodes[:, 1], w, triangles=tri, cmap='RdBu_r', alpha=0.9)
        ax.set_xlabel('x (mm)')
        ax.set_ylabel('y (mm)')
        ax.set_zlabel('w (mm)')
        ax.set_title('Deflection Surface')
        plt.tight_layout()
        plt.savefig(out_dir / 'deflection_3d.png', dpi=150)
        plt.close()
    
    # Centerline profiles
    y_center = Ly / 2.0
    tol = Ly / 15.0
    mask = np.abs(nodes[:, 1] - y_center) < tol
    x_c = nodes[mask, 0]
    T_c = T[mask]
    sort_idx = np.argsort(x_c)
    x_c = x_c[sort_idx]
    T_c = T_c[sort_idx]
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
    
    ax1.plot(x_c, T_c, 'b-', linewidth=2)
    ax1.set_ylabel('Temperature (K)', color='b')
    ax1.tick_params(axis='y', labelcolor='b')
    ax1.set_title('Temperature and Deflection along Centerline')
    ax1.grid(True, alpha=0.3)
    
    if w is not None:
        w_c = w[mask][sort_idx]
        ax2.plot(x_c, w_c, 'r-', linewidth=2)
        ax2.set_ylabel('Deflection (mm)', color='r')
        ax2.tick_params(axis='y', labelcolor='r')
        ax2.axhline(y=0, color='k', linestyle='--', linewidth=0.5)
    
    ax2.set_xlabel('x (mm)')
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_dir / 'centerline.png', dpi=150)
    plt.close()
    
    print(f"Plots saved to {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Moving heat source line heating simulation")
    parser.add_argument("--Lx", type=float, default=1000, help="plate length (mm)")
    parser.add_argument("--Ly", type=float, default=900, help="plate width (mm)")
    parser.add_argument("--thickness", type=float, default=12, help="plate thickness (mm)")
    parser.add_argument("--h", type=float, default=40, help="mesh size (mm)")
    parser.add_argument("--q0", type=float, default=10.0, help="peak heat flux (W/mm^2)")
    parser.add_argument("--r0", type=float, default=20.0, help="Gaussian radius (mm)")
    parser.add_argument("--velocity", type=float, default=10.0, help="scan velocity (mm/s)")
    parser.add_argument("--dt", type=float, default=0.5, help="time step (s)")
    parser.add_argument("--extra-time", type=float, default=50.0, help="extra cooling time (s)")
    parser.add_argument("--k", type=float, default=0.045, help="thermal conductivity (W/mm-K)")
    parser.add_argument("--rho", type=float, default=7.85e-6, help="density (kg/mm^3)")
    parser.add_argument("--cp", type=float, default=500.0, help="specific heat (J/kg-K)")
    parser.add_argument("--h-conv", type=float, default=5e-5, help="convection coeff (W/mm^2-K)")
    parser.add_argument("--T-inf", type=float, default=293.0, help="ambient temp (K)")
    parser.add_argument("--T-ref", type=float, default=293.0, help="reference temp (K)")
    parser.add_argument("--E", type=float, default=210e3, help="Young's modulus (MPa)")
    parser.add_argument("--nu", type=float, default=0.3, help="Poisson's ratio")
    parser.add_argument("--alpha", type=float, default=1.2e-5, help="thermal expansion (1/K)")
    args = parser.parse_args()
    
    print(f"=== Line Heating Simulation ===")
    print(f"Plate: {args.Lx}×{args.Ly}×{args.thickness} mm")
    print(f"Heat source: q0={args.q0} W/mm^2, r0={args.r0} mm, v={args.velocity} mm/s")
    
    # Mesh
    nodes, tri, edges = build_plate_mesh(args.Lx, args.Ly, args.h)
    print(f"Mesh: {nodes.shape[0]} nodes, {tri.shape[0]} elements")
    
    # Time integration
    scan_time = args.Lx / args.velocity
    total_time = scan_time + args.extra_time
    steps = int(total_time / args.dt)
    print(f"Scan time: {scan_time:.1f}s, total time: {total_time:.1f}s, steps: {steps}")
    
    # Solve thermal
    T_final = solve_moving_heat(
        nodes, tri, edges, args.Lx, args.Ly, args.k, args.rho, args.cp,
        args.dt, steps, args.q0, args.r0, args.velocity, 
        args.h_conv, args.T_inf, args.T_ref
    )
    
    print(f"Temperature: min={T_final.min():.1f}K, max={T_final.max():.1f}K")
    
    # Compute deflection
    w, eps_th = compute_deflection_simple(
        nodes, tri, T_final, args.thickness, args.Lx, args.Ly,
        args.E, args.nu, args.alpha, args.T_ref
    )
    print(f"Deflection: min={w.min():.6f}mm, max={w.max():.6f}mm")
    
    # Plot
    out_dir = Path("outputs")
    plot_results(nodes, tri, T_final, w, args.Lx, args.Ly, args.thickness, out_dir)
    
    # Save data
    np.save("heat_solution.npy", T_final)
    np.save("deflection_solution.npy", w)
    print("Solutions saved")


if __name__ == "__main__":
    main()
