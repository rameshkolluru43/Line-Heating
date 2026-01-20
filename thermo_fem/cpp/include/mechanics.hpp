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

    struct ElastoplasticAssembly
    {
        MechanicsAssembly stiffness;
        std::vector<double> internal_force; // size = 3 * n_nodes
        std::vector<double> epsp;           // size = 6 * n_elem (Voigt, engineering shear)
        std::vector<double> epbar;          // size = n_elem
    };

    // Assemble 3D linear tetrahedral stiffness matrix (elastic).
    // nodes: flat array [x0, y0, z0, x1, y1, z1, ...], tet: [n0, n1, n2, n3, ...]
    // Returns stiffness matrix in COO format (3*n_nodes DOFs)
    MechanicsAssembly assemble_elasticity_3d(const std::vector<double> &nodes,
                                             const std::vector<int> &tet,
                                             double E,
                                             double nu);

    // Assemble 3D linear tetrahedral stiffness matrix with per-element properties.
    // E_elem and nu_elem are per-element arrays (size = tet.size()/4).
    MechanicsAssembly assemble_elasticity_3d_per_element(const std::vector<double> &nodes,
                                                         const std::vector<int> &tet,
                                                         const std::vector<double> &E_elem,
                                                         const std::vector<double> &nu_elem);

    // Compute thermal load vector F_th from thermal strain: eps_th = alpha * (T - T_ref)
    // Returns force vector of size 3*n_nodes
    std::vector<double> thermal_load_3d(const std::vector<double> &nodes,
                                        const std::vector<int> &tet,
                                        const std::vector<double> &temperature,
                                        double E,
                                        double nu,
                                        double alpha,
                                        double T_ref);

    // Thermal load vector with per-element E, nu, alpha (size = tet.size()/4).
    std::vector<double> thermal_load_3d_per_element(const std::vector<double> &nodes,
                                                    const std::vector<int> &tet,
                                                    const std::vector<double> &temperature,
                                                    const std::vector<double> &E_elem,
                                                    const std::vector<double> &nu_elem,
                                                    const std::vector<double> &alpha_elem,
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

    // Thermal + inherent load vector with per-element E, nu, alpha.
    std::vector<double> thermal_load_3d_with_inherent_per_element(const std::vector<double> &nodes,
                                                                  const std::vector<int> &tet,
                                                                  const std::vector<double> &temperature,
                                                                  const std::vector<double> &eps_inherent,
                                                                  const std::vector<double> &E_elem,
                                                                  const std::vector<double> &nu_elem,
                                                                  const std::vector<double> &alpha_elem,
                                                                  double T_ref);

    // Assemble a single elastoplastic (J2, isotropic hardening) step at element centroids.
    // Uses total strain: eps = B * u, with thermal strain removed and plastic strain updated.
    // Returns stiffness (elastic tangent) and internal force for Newton iterations.
    ElastoplasticAssembly assemble_elastoplastic_3d_step(const std::vector<double> &nodes,
                                                         const std::vector<int> &tet,
                                                         const std::vector<double> &displacement,
                                                         const std::vector<double> &temperature,
                                                         const std::vector<double> &epsp_prev,
                                                         const std::vector<double> &epbar_prev,
                                                         const std::vector<double> &E_elem,
                                                         const std::vector<double> &nu_elem,
                                                         const std::vector<double> &alpha_elem,
                                                         double T_ref,
                                                         double sigma_y0,
                                                         double H_iso);

} // namespace thermo
