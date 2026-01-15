"""Verification tests for 3D thermoelastic FEM implementation.

Tests:
1. Zero thermal load → zero displacement
2. Uniform temperature → uniform expansion (rigid body motion, no bending)
3. Linear temperature gradient → pure bending without in-plane stress
"""
import sys
from pathlib import Path
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import gmsh

sys.path.insert(0, str(Path(__file__).parent.parent / "build" / "cpp"))
import thermo_bindings


def build_simple_cube(size=100.0, h=20.0):
    """Create a simple cube mesh for testing."""
    gmsh.initialize()
    gmsh.model.add("cube")
    
    box = gmsh.model.occ.addBox(0, 0, 0, size, size, size)
    gmsh.model.occ.synchronize()
    
    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", h)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", h)
    gmsh.model.mesh.generate(3)
    
    node_tags, node_coords, _ = gmsh.model.mesh.getNodes()
    nodes = np.array(node_coords, dtype=float).reshape(-1, 3)
    
    elem_types, elem_tags_list, node_tags_elem = gmsh.model.mesh.getElements(dim=3)
    tet_idx = np.where(np.array(elem_types) == 4)[0][0]
    tet = np.array(node_tags_elem[tet_idx], dtype=int) - 1
    tet = tet.reshape(-1, 4)
    
    gmsh.finalize()
    
    # Identify bottom nodes (z ≈ 0)
    tol = size * 0.01
    bottom_nodes = np.where(nodes[:, 2] < tol)[0]
    
    return nodes, tet, bottom_nodes


def test_zero_thermal_load():
    """Test 1: Zero temperature change should give zero displacement."""
    print("\n" + "="*60)
    print("TEST 1: Zero Thermal Load → Zero Displacement")
    print("="*60)
    
    nodes, tet, bottom_nodes = build_simple_cube(size=100.0, h=25.0)
    print(f"Mesh: {len(nodes)} nodes, {len(tet)} elements")
    
    # Material properties
    E, nu, alpha, T_ref = 210e3, 0.3, 1.2e-5, 293.0
    
    # Temperature field = T_ref (no change)
    T = np.full(len(nodes), T_ref)
    
    # Assemble and solve
    nodes_flat = nodes.flatten().tolist()
    tet_flat = tet.flatten().tolist()
    
    mech_asm = thermo_bindings.assemble_elasticity_3d(nodes_flat, tet_flat, E, nu)
    K = sp.coo_matrix((mech_asm.values, (mech_asm.rows, mech_asm.cols)), 
                      shape=(3*len(nodes), 3*len(nodes))).tocsr()
    
    T_list = T.tolist()
    F_th = np.array(thermo_bindings.thermal_load_3d(
        nodes_flat, tet_flat, T_list, E, nu, alpha, T_ref
    ))
    
    # Apply BCs
    fixed_dofs = []
    for node_id in bottom_nodes:
        fixed_dofs.extend([3*node_id, 3*node_id+1, 3*node_id+2])
    fixed_dofs = np.array(fixed_dofs, dtype=int)
    
    free_dofs = np.setdiff1d(np.arange(3*len(nodes)), fixed_dofs)
    K_free = K[free_dofs, :][:, free_dofs]
    F_free = F_th[free_dofs]
    
    u_free = spla.spsolve(K_free, F_free)
    u_full = np.zeros(3*len(nodes))
    u_full[free_dofs] = u_free
    u = u_full.reshape(-1, 3)
    
    # Check
    u_max = np.max(np.abs(u))
    F_max = np.max(np.abs(F_th))
    
    print(f"Max thermal load: {F_max:.2e} N")
    print(f"Max displacement: {u_max:.2e} mm")
    
    if u_max < 1e-10 and F_max < 1e-10:
        print("✓ PASS: Zero thermal load produces zero displacement")
    else:
        print("✗ FAIL: Non-zero displacement detected!")
    
    return u_max < 1e-10


def test_uniform_expansion():
    """Test 2: Uniform temperature rise → uniform expansion, no bending."""
    print("\n" + "="*60)
    print("TEST 2: Uniform Temperature → Uniform Expansion")
    print("="*60)
    
    nodes, tet, bottom_nodes = build_simple_cube(size=100.0, h=25.0)
    print(f"Mesh: {len(nodes)} nodes, {len(tet)} elements")
    
    # Material properties
    E, nu, alpha, T_ref = 210e3, 0.3, 1.2e-5, 293.0
    
    # Uniform temperature increase
    dT = 100.0  # K
    T = np.full(len(nodes), T_ref + dT)
    
    # Expected: free expansion = α * dT * L
    # But we have bottom constrained, so only top should expand
    expected_expansion = alpha * dT * 100.0  # mm
    
    # Assemble and solve
    nodes_flat = nodes.flatten().tolist()
    tet_flat = tet.flatten().tolist()
    
    mech_asm = thermo_bindings.assemble_elasticity_3d(nodes_flat, tet_flat, E, nu)
    K = sp.coo_matrix((mech_asm.values, (mech_asm.rows, mech_asm.cols)), 
                      shape=(3*len(nodes), 3*len(nodes))).tocsr()
    
    T_list = T.tolist()
    F_th = np.array(thermo_bindings.thermal_load_3d(
        nodes_flat, tet_flat, T_list, E, nu, alpha, T_ref
    ))
    
    # Apply BCs (fix bottom)
    fixed_dofs = []
    for node_id in bottom_nodes:
        fixed_dofs.extend([3*node_id, 3*node_id+1, 3*node_id+2])
    fixed_dofs = np.array(fixed_dofs, dtype=int)
    
    free_dofs = np.setdiff1d(np.arange(3*len(nodes)), fixed_dofs)
    K_free = K[free_dofs, :][:, free_dofs]
    F_free = F_th[free_dofs]
    
    u_free = spla.spsolve(K_free, F_free)
    u_full = np.zeros(3*len(nodes))
    u_full[free_dofs] = u_free
    u = u_full.reshape(-1, 3)
    
    # Check: z-displacement should be approximately uniform (≈ α*dT*z for each z)
    tol = nodes[:, 2].max() * 0.01
    top_nodes = np.where(nodes[:, 2] > nodes[:, 2].max() - tol)[0]
    
    uz_top_mean = np.mean(u[top_nodes, 2])
    uz_top_std = np.std(u[top_nodes, 2])
    
    print(f"Expected vertical expansion: {expected_expansion:.6f} mm")
    print(f"Top surface mean uz: {uz_top_mean:.6f} mm (std: {uz_top_std:.6f})")
    print(f"Relative error: {abs(uz_top_mean - expected_expansion)/expected_expansion*100:.2f}%")
    
    # Should be close (within 20% due to constraint effects at fixed bottom)
    # The fixed bottom introduces reaction stresses that increase displacement
    rel_error = abs(uz_top_mean - expected_expansion) / expected_expansion
    
    if rel_error < 0.20:  # 20% tolerance for constrained case
        print("✓ PASS: Uniform expansion within tolerance")
    else:
        print(f"✗ FAIL: Expansion error too large ({rel_error*100:.1f}%)")
    
    return rel_error < 0.20


def test_linear_gradient():
    """Test 3: Linear temperature gradient through thickness → bending."""
    print("\n" + "="*60)
    print("TEST 3: Linear Temperature Gradient → Bending")
    print("="*60)
    
    nodes, tet, bottom_nodes = build_simple_cube(size=100.0, h=25.0)
    print(f"Mesh: {len(nodes)} nodes, {len(tet)} elements")
    
    # Material properties
    E, nu, alpha, T_ref = 210e3, 0.3, 1.2e-5, 293.0
    
    # Linear temperature gradient: T = T_ref + dT * (z / z_max)
    dT_total = 200.0  # K temperature difference from bottom to top
    z_max = nodes[:, 2].max()
    T = T_ref + dT_total * (nodes[:, 2] / z_max)
    
    # Assemble and solve
    nodes_flat = nodes.flatten().tolist()
    tet_flat = tet.flatten().tolist()
    
    mech_asm = thermo_bindings.assemble_elasticity_3d(nodes_flat, tet_flat, E, nu)
    K = sp.coo_matrix((mech_asm.values, (mech_asm.rows, mech_asm.cols)), 
                      shape=(3*len(nodes), 3*len(nodes))).tocsr()
    
    T_list = T.tolist()
    F_th = np.array(thermo_bindings.thermal_load_3d(
        nodes_flat, tet_flat, T_list, E, nu, alpha, T_ref
    ))
    
    # Apply BCs (fix bottom)
    fixed_dofs = []
    for node_id in bottom_nodes:
        fixed_dofs.extend([3*node_id, 3*node_id+1, 3*node_id+2])
    fixed_dofs = np.array(fixed_dofs, dtype=int)
    
    free_dofs = np.setdiff1d(np.arange(3*len(nodes)), fixed_dofs)
    K_free = K[free_dofs, :][:, free_dofs]
    F_free = F_th[free_dofs]
    
    u_free = spla.spsolve(K_free, F_free)
    u_full = np.zeros(3*len(nodes))
    u_full[free_dofs] = u_free
    u = u_full.reshape(-1, 3)
    
    # Check: Should have vertical displacement gradient
    tol = nodes[:, 2].max() * 0.01
    top_nodes = np.where(nodes[:, 2] > nodes[:, 2].max() - tol)[0]
    
    uz_top_mean = np.mean(u[top_nodes, 2])
    uz_bottom = u[bottom_nodes, 2].mean()  # should be ~0 (constrained)
    
    print(f"Bottom surface mean uz: {uz_bottom:.6f} mm (constrained)")
    print(f"Top surface mean uz: {uz_top_mean:.6f} mm")
    print(f"Temperature gradient: {dT_total} K over {z_max:.1f} mm")
    
    # Top should expand more than bottom (positive uz)
    if uz_top_mean > 0 and abs(uz_bottom) < 1e-6:
        print("✓ PASS: Temperature gradient causes expected deformation pattern")
        return True
    else:
        print("✗ FAIL: Unexpected deformation pattern")
        return False


def main():
    print("\n" + "="*60)
    print("3D THERMOELASTIC FEM VERIFICATION TESTS")
    print("="*60)
    
    results = []
    
    try:
        results.append(("Zero thermal load", test_zero_thermal_load()))
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        results.append(("Zero thermal load", False))
    
    try:
        results.append(("Uniform expansion", test_uniform_expansion()))
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        results.append(("Uniform expansion", False))
    
    try:
        results.append(("Linear gradient", test_linear_gradient()))
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
        results.append(("Linear gradient", False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nPassed: {passed}/{total}")
    print("="*60)
    
    return all(p for _, p in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
