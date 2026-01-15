#pragma once

#include <cstddef>
#include <vector>

namespace thermo
{

    struct MechanicsAssembly
    {
        std::vector<int> rows;
        std::vector<int> cols;
        std::vector<double> values;
        std::size_t dof_count{}; // 3 * n_nodes for 3D
    };

    // Assemble 3D linear tetrahedral stiffness matrix (elastic).
    // nodes: flat array [x0, y0, z0, x1, y1, z1, ...], tet: [n0, n1, n2, n3, ...]
    // Returns stiffness matrix in COO format (3*n_nodes DOFs)
    MechanicsAssembly assemble_elasticity_3d(const std::vector<double> &nodes,
                                             const std::vector<int> &tet,
                                             double E,
                                             double nu);

    // Compute thermal load vector F_th from thermal strain: eps_th = alpha * (T - T_ref)
    // Returns force vector of size 3*n_nodes
    std::vector<double> thermal_load_3d(const std::vector<double> &nodes,
                                        const std::vector<int> &tet,
                                        const std::vector<double> &temperature,
                                        double E,
                                        double nu,
                                        double alpha,
                                        double T_ref);

    // Compute load vector from combined isotropic eigenstrain:
    //   eps_iso = alpha * (T - T_ref) + eps_inherent
    // where eps_inherent is a nodal scalar isotropic strain (dimensionless).
    // Returns force vector of size 3*n_nodes.
    std::vector<double> thermal_load_3d_with_inherent(const std::vector<double> &nodes,
                                                      const std::vector<int> &tet,
                                                      const std::vector<double> &temperature,
                                                      const std::vector<double> &eps_inherent,
                                                      double E,
                                                      double nu,
                                                      double alpha,
                                                      double T_ref);

} // namespace thermo
