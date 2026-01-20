#include "mechanics.hpp"
#include <stdexcept>
#include <cmath>

namespace thermo
{

    namespace
    {
        // Compute volume and shape function gradients for linear tetrahedron
        inline void tet_geometry(const double *n0, const double *n1, const double *n2, const double *n3,
                                 double &volume, double grad_N[4][3])
        {
            // Jacobian: J = [p1-p0, p2-p0, p3-p0]
            double J[3][3];
            for (int i = 0; i < 3; ++i)
            {
                J[i][0] = n1[i] - n0[i];
                J[i][1] = n2[i] - n0[i];
                J[i][2] = n3[i] - n0[i];
            }

            // det(J)
            double det_J = J[0][0] * (J[1][1] * J[2][2] - J[1][2] * J[2][1]) -
                           J[0][1] * (J[1][0] * J[2][2] - J[1][2] * J[2][0]) +
                           J[0][2] * (J[1][0] * J[2][1] - J[1][1] * J[2][0]);

            volume = std::abs(det_J) / 6.0;

            if (volume < 1e-12)
            {
                throw std::runtime_error("Degenerate tetrahedron detected");
            }

            // Inverse Jacobian
            double J_inv[3][3];
            double inv_det = 1.0 / det_J;
            J_inv[0][0] = (J[1][1] * J[2][2] - J[1][2] * J[2][1]) * inv_det;
            J_inv[0][1] = (J[0][2] * J[2][1] - J[0][1] * J[2][2]) * inv_det;
            J_inv[0][2] = (J[0][1] * J[1][2] - J[0][2] * J[1][1]) * inv_det;
            J_inv[1][0] = (J[1][2] * J[2][0] - J[1][0] * J[2][2]) * inv_det;
            J_inv[1][1] = (J[0][0] * J[2][2] - J[0][2] * J[2][0]) * inv_det;
            J_inv[1][2] = (J[0][2] * J[1][0] - J[0][0] * J[1][2]) * inv_det;
            J_inv[2][0] = (J[1][0] * J[2][1] - J[1][1] * J[2][0]) * inv_det;
            J_inv[2][1] = (J[0][1] * J[2][0] - J[0][0] * J[2][1]) * inv_det;
            J_inv[2][2] = (J[0][0] * J[1][1] - J[0][1] * J[1][0]) * inv_det;

            // Shape function gradients in reference coords: dN/dξ
            // N0 = 1 - ξ - η - ζ  =>  ∇N0 = [-1, -1, -1]
            // N1 = ξ               =>  ∇N1 = [1, 0, 0]
            // N2 = η               =>  ∇N2 = [0, 1, 0]
            // N3 = ζ               =>  ∇N3 = [0, 0, 1]
            double dN_ref[4][3] = {
                {-1.0, -1.0, -1.0},
                {1.0, 0.0, 0.0},
                {0.0, 1.0, 0.0},
                {0.0, 0.0, 1.0}};

            // grad_N = dN/dξ @ J_inv
            for (int i = 0; i < 4; ++i)
            {
                for (int j = 0; j < 3; ++j)
                {
                    grad_N[i][j] = 0.0;
                    for (int k = 0; k < 3; ++k)
                    {
                        grad_N[i][j] += dN_ref[i][k] * J_inv[k][j];
                    }
                }
            }
        }

        // B-matrix for linear elasticity: strain = B * u_elem (6x12 for tet4)
        inline void compute_B_matrix(const double grad_N[4][3], double B[6][12])
        {
            // Initialize to zero
            for (int i = 0; i < 6; ++i)
                for (int j = 0; j < 12; ++j)
                    B[i][j] = 0.0;

            // Strain-displacement relationship:
            // ε = [εxx, εyy, εzz, γxy, γyz, γxz]^T = B * u
            // For each node i (DOFs: ux_i, uy_i, uz_i at positions 3i, 3i+1, 3i+2):
            for (int node = 0; node < 4; ++node)
            {
                int col_x = 3 * node;
                int col_y = 3 * node + 1;
                int col_z = 3 * node + 2;

                double dNx = grad_N[node][0];
                double dNy = grad_N[node][1];
                double dNz = grad_N[node][2];

                // εxx = ∂ux/∂x
                B[0][col_x] = dNx;
                // εyy = ∂uy/∂y
                B[1][col_y] = dNy;
                // εzz = ∂uz/∂z
                B[2][col_z] = dNz;
                // γxy = ∂ux/∂y + ∂uy/∂x
                B[3][col_x] = dNy;
                B[3][col_y] = dNx;
                // γyz = ∂uy/∂z + ∂uz/∂y
                B[4][col_y] = dNz;
                B[4][col_z] = dNy;
                // γxz = ∂ux/∂z + ∂uz/∂x
                B[5][col_x] = dNz;
                B[5][col_z] = dNx;
            }
        }

        // 3D isotropic elasticity matrix (Voigt notation)
        inline void compute_D_matrix(double E, double nu, double D[6][6])
        {
            double lambda = E * nu / ((1.0 + nu) * (1.0 - 2.0 * nu));
            double mu = E / (2.0 * (1.0 + nu));

            for (int i = 0; i < 6; ++i)
                for (int j = 0; j < 6; ++j)
                    D[i][j] = 0.0;

            // Normal strains
            D[0][0] = D[1][1] = D[2][2] = lambda + 2.0 * mu;
            D[0][1] = D[0][2] = D[1][0] = D[1][2] = D[2][0] = D[2][1] = lambda;
            // Shear strains
            D[3][3] = D[4][4] = D[5][5] = mu;
        }

        inline double voigt_dev_norm2(const double s[6])
        {
            return s[0] * s[0] + s[1] * s[1] + s[2] * s[2] +
                   2.0 * (s[3] * s[3] + s[4] * s[4] + s[5] * s[5]);
        }

        inline void voigt_deviatoric(const double sigma[6], double s[6], double &p_mean)
        {
            p_mean = (sigma[0] + sigma[1] + sigma[2]) / 3.0;
            s[0] = sigma[0] - p_mean;
            s[1] = sigma[1] - p_mean;
            s[2] = sigma[2] - p_mean;
            s[3] = sigma[3];
            s[4] = sigma[4];
            s[5] = sigma[5];
        }

    } // namespace

    MechanicsAssembly assemble_elasticity_3d(const std::vector<double> &nodes,
                                             const std::vector<int> &tet,
                                             double E,
                                             double nu)
    {
        if (nodes.size() % 3 != 0)
        {
            throw std::invalid_argument("nodes size must be multiples of 3 (x,y,z triplets)");
        }
        const std::size_t n_nodes = nodes.size() / 3;
        const std::size_t n_dof = 3 * n_nodes;

        if (tet.size() % 4 != 0)
        {
            throw std::invalid_argument("tet connectivity must be multiples of 4");
        }
        const std::size_t n_elem = tet.size() / 4;

        MechanicsAssembly asmbl;
        asmbl.dof_count = n_dof;
        asmbl.rows.reserve(n_elem * 144); // 12x12 = 144 entries per tet
        asmbl.cols.reserve(n_elem * 144);
        asmbl.values.reserve(n_elem * 144);

        // Elasticity matrix
        double D[6][6];
        compute_D_matrix(E, nu, D);

        for (std::size_t e = 0; e < n_elem; ++e)
        {
            const int n0 = tet[4 * e + 0];
            const int n1 = tet[4 * e + 1];
            const int n2 = tet[4 * e + 2];
            const int n3 = tet[4 * e + 3];

            if (n0 < 0 || n1 < 0 || n2 < 0 || n3 < 0 ||
                static_cast<std::size_t>(n0) >= n_nodes ||
                static_cast<std::size_t>(n1) >= n_nodes ||
                static_cast<std::size_t>(n2) >= n_nodes ||
                static_cast<std::size_t>(n3) >= n_nodes)
            {
                throw std::out_of_range("tet node index out of range");
            }

            const double *p0 = &nodes[3 * n0];
            const double *p1 = &nodes[3 * n1];
            const double *p2 = &nodes[3 * n2];
            const double *p3 = &nodes[3 * n3];

            double volume = 0.0;
            double grad_N[4][3];
            tet_geometry(p0, p1, p2, p3, volume, grad_N);

            // B matrix (6x12)
            double B[6][12];
            compute_B_matrix(grad_N, B);

            // Element stiffness: K_elem = V * B^T * D * B
            double DB[6][12]; // D * B
            for (int i = 0; i < 6; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    DB[i][j] = 0.0;
                    for (int k = 0; k < 6; ++k)
                    {
                        DB[i][j] += D[i][k] * B[k][j];
                    }
                }
            }

            double K_elem[12][12]; // B^T * D * B
            for (int i = 0; i < 12; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    K_elem[i][j] = 0.0;
                    for (int k = 0; k < 6; ++k)
                    {
                        K_elem[i][j] += B[k][i] * DB[k][j];
                    }
                    K_elem[i][j] *= volume;
                }
            }

            // Assemble into global matrix
            const int dof_map[12] = {
                3 * n0, 3 * n0 + 1, 3 * n0 + 2,
                3 * n1, 3 * n1 + 1, 3 * n1 + 2,
                3 * n2, 3 * n2 + 1, 3 * n2 + 2,
                3 * n3, 3 * n3 + 1, 3 * n3 + 2};

            for (int i = 0; i < 12; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    asmbl.rows.push_back(dof_map[i]);
                    asmbl.cols.push_back(dof_map[j]);
                    asmbl.values.push_back(K_elem[i][j]);
                }
            }
        }

        return asmbl;
    }

    MechanicsAssembly assemble_elasticity_3d_per_element(const std::vector<double> &nodes,
                                                         const std::vector<int> &tet,
                                                         const std::vector<double> &E_elem,
                                                         const std::vector<double> &nu_elem)
    {
        if (nodes.size() % 3 != 0)
        {
            throw std::invalid_argument("nodes size must be multiples of 3 (x,y,z triplets)");
        }
        const std::size_t n_nodes = nodes.size() / 3;
        const std::size_t n_dof = 3 * n_nodes;

        if (tet.size() % 4 != 0)
        {
            throw std::invalid_argument("tet connectivity must be multiples of 4");
        }
        const std::size_t n_elem = tet.size() / 4;
        if (E_elem.size() != n_elem || nu_elem.size() != n_elem)
        {
            throw std::invalid_argument("E_elem/nu_elem size mismatch");
        }

        MechanicsAssembly asmbl;
        asmbl.dof_count = n_dof;
        asmbl.rows.reserve(n_elem * 144);
        asmbl.cols.reserve(n_elem * 144);
        asmbl.values.reserve(n_elem * 144);

        for (std::size_t e = 0; e < n_elem; ++e)
        {
            const double E = E_elem[e];
            const double nu = nu_elem[e];

            double D[6][6];
            compute_D_matrix(E, nu, D);

            const int n0 = tet[4 * e + 0];
            const int n1 = tet[4 * e + 1];
            const int n2 = tet[4 * e + 2];
            const int n3 = tet[4 * e + 3];

            if (n0 < 0 || n1 < 0 || n2 < 0 || n3 < 0 ||
                static_cast<std::size_t>(n0) >= n_nodes ||
                static_cast<std::size_t>(n1) >= n_nodes ||
                static_cast<std::size_t>(n2) >= n_nodes ||
                static_cast<std::size_t>(n3) >= n_nodes)
            {
                throw std::out_of_range("tet node index out of range");
            }

            const double *p0 = &nodes[3 * n0];
            const double *p1 = &nodes[3 * n1];
            const double *p2 = &nodes[3 * n2];
            const double *p3 = &nodes[3 * n3];

            double volume = 0.0;
            double grad_N[4][3];
            tet_geometry(p0, p1, p2, p3, volume, grad_N);

            double B[6][12];
            compute_B_matrix(grad_N, B);

            double DB[6][12];
            for (int i = 0; i < 6; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    DB[i][j] = 0.0;
                    for (int k = 0; k < 6; ++k)
                    {
                        DB[i][j] += D[i][k] * B[k][j];
                    }
                }
            }

            double K_elem[12][12];
            for (int i = 0; i < 12; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    K_elem[i][j] = 0.0;
                    for (int k = 0; k < 6; ++k)
                    {
                        K_elem[i][j] += B[k][i] * DB[k][j];
                    }
                    K_elem[i][j] *= volume;
                }
            }

            const int dof_map[12] = {
                3 * n0, 3 * n0 + 1, 3 * n0 + 2,
                3 * n1, 3 * n1 + 1, 3 * n1 + 2,
                3 * n2, 3 * n2 + 1, 3 * n2 + 2,
                3 * n3, 3 * n3 + 1, 3 * n3 + 2};

            for (int i = 0; i < 12; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    asmbl.rows.push_back(dof_map[i]);
                    asmbl.cols.push_back(dof_map[j]);
                    asmbl.values.push_back(K_elem[i][j]);
                }
            }
        }

        return asmbl;
    }

    std::vector<double> thermal_load_3d(const std::vector<double> &nodes,
                                        const std::vector<int> &tet,
                                        const std::vector<double> &temperature,
                                        double E,
                                        double nu,
                                        double alpha,
                                        double T_ref)
    {
        const std::size_t n_nodes = nodes.size() / 3;
        const std::size_t n_dof = 3 * n_nodes;

        if (temperature.size() != n_nodes)
        {
            throw std::invalid_argument("temperature array size mismatch");
        }

        std::vector<double> F_th(n_dof, 0.0);

        // Thermal strain vector: ε_th = α(T - T_ref) * [1, 1, 1, 0, 0, 0]^T
        // Thermal stress: σ_th = D * ε_th
        // Nodal forces: F = ∫ B^T * σ_th dV

        double D[6][6];
        compute_D_matrix(E, nu, D);

        const std::size_t n_elem = tet.size() / 4;
        for (std::size_t e = 0; e < n_elem; ++e)
        {
            const int n0 = tet[4 * e + 0];
            const int n1 = tet[4 * e + 1];
            const int n2 = tet[4 * e + 2];
            const int n3 = tet[4 * e + 3];

            const double *p0 = &nodes[3 * n0];
            const double *p1 = &nodes[3 * n1];
            const double *p2 = &nodes[3 * n2];
            const double *p3 = &nodes[3 * n3];

            double volume = 0.0;
            double grad_N[4][3];
            tet_geometry(p0, p1, p2, p3, volume, grad_N);

            double B[6][12];
            compute_B_matrix(grad_N, B);

            // Average element temperature
            double T_elem = 0.25 * (temperature[n0] + temperature[n1] +
                                    temperature[n2] + temperature[n3]);
            double dT = T_elem - T_ref;

            // Thermal strain: ε_th = α * dT * [1, 1, 1, 0, 0, 0]^T
            double eps_th[6] = {alpha * dT, alpha * dT, alpha * dT, 0.0, 0.0, 0.0};

            // Thermal stress: σ_th = D * ε_th
            double sigma_th[6];
            for (int i = 0; i < 6; ++i)
            {
                sigma_th[i] = 0.0;
                for (int j = 0; j < 6; ++j)
                {
                    sigma_th[i] += D[i][j] * eps_th[j];
                }
            }

            // Element force: f_elem = V * B^T * σ_th
            double f_elem[12];
            for (int i = 0; i < 12; ++i)
            {
                f_elem[i] = 0.0;
                for (int j = 0; j < 6; ++j)
                {
                    f_elem[i] += B[j][i] * sigma_th[j];
                }
                f_elem[i] *= volume;
            }

            // Assemble into global force vector
            const int dof_map[12] = {
                3 * n0, 3 * n0 + 1, 3 * n0 + 2,
                3 * n1, 3 * n1 + 1, 3 * n1 + 2,
                3 * n2, 3 * n2 + 1, 3 * n2 + 2,
                3 * n3, 3 * n3 + 1, 3 * n3 + 2};

            for (int i = 0; i < 12; ++i)
            {
                F_th[dof_map[i]] += f_elem[i];
            }
        }

        return F_th;
    }

    std::vector<double> thermal_load_3d_per_element(const std::vector<double> &nodes,
                                                    const std::vector<int> &tet,
                                                    const std::vector<double> &temperature,
                                                    const std::vector<double> &E_elem,
                                                    const std::vector<double> &nu_elem,
                                                    const std::vector<double> &alpha_elem,
                                                    double T_ref)
    {
        const std::size_t n_nodes = nodes.size() / 3;
        const std::size_t n_dof = 3 * n_nodes;

        if (temperature.size() != n_nodes)
        {
            throw std::invalid_argument("temperature array size mismatch");
        }
        if (tet.size() % 4 != 0)
        {
            throw std::invalid_argument("tet connectivity must be multiples of 4");
        }
        const std::size_t n_elem = tet.size() / 4;
        if (E_elem.size() != n_elem || nu_elem.size() != n_elem || alpha_elem.size() != n_elem)
        {
            throw std::invalid_argument("E/nu/alpha per-element size mismatch");
        }

        std::vector<double> F_th(n_dof, 0.0);

        for (std::size_t e = 0; e < n_elem; ++e)
        {
            const double E = E_elem[e];
            const double nu = nu_elem[e];
            const double alpha = alpha_elem[e];

            double D[6][6];
            compute_D_matrix(E, nu, D);

            const int n0 = tet[4 * e + 0];
            const int n1 = tet[4 * e + 1];
            const int n2 = tet[4 * e + 2];
            const int n3 = tet[4 * e + 3];

            const double *p0 = &nodes[3 * n0];
            const double *p1 = &nodes[3 * n1];
            const double *p2 = &nodes[3 * n2];
            const double *p3 = &nodes[3 * n3];

            double volume = 0.0;
            double grad_N[4][3];
            tet_geometry(p0, p1, p2, p3, volume, grad_N);

            double B[6][12];
            compute_B_matrix(grad_N, B);

            double T_elem = 0.25 * (temperature[n0] + temperature[n1] +
                                    temperature[n2] + temperature[n3]);
            double dT = T_elem - T_ref;

            double eps_th[6] = {alpha * dT, alpha * dT, alpha * dT, 0.0, 0.0, 0.0};

            double sigma_th[6];
            for (int i = 0; i < 6; ++i)
            {
                sigma_th[i] = 0.0;
                for (int j = 0; j < 6; ++j)
                {
                    sigma_th[i] += D[i][j] * eps_th[j];
                }
            }

            double f_elem[12];
            for (int i = 0; i < 12; ++i)
            {
                f_elem[i] = 0.0;
                for (int j = 0; j < 6; ++j)
                {
                    f_elem[i] += B[j][i] * sigma_th[j];
                }
                f_elem[i] *= volume;
            }

            const int dof_map[12] = {
                3 * n0, 3 * n0 + 1, 3 * n0 + 2,
                3 * n1, 3 * n1 + 1, 3 * n1 + 2,
                3 * n2, 3 * n2 + 1, 3 * n2 + 2,
                3 * n3, 3 * n3 + 1, 3 * n3 + 2};

            for (int i = 0; i < 12; ++i)
            {
                F_th[dof_map[i]] += f_elem[i];
            }
        }

        return F_th;
    }

    std::vector<double> thermal_load_3d_with_inherent(const std::vector<double> &nodes,
                                                      const std::vector<int> &tet,
                                                      const std::vector<double> &temperature,
                                                      const std::vector<double> &eps_inherent,
                                                      double E,
                                                      double nu,
                                                      double alpha,
                                                      double T_ref)
    {
        const std::size_t n_nodes = nodes.size() / 3;
        const std::size_t n_dof = 3 * n_nodes;

        if (temperature.size() != n_nodes)
        {
            throw std::invalid_argument("temperature array size mismatch");
        }
        if (eps_inherent.size() != n_nodes)
        {
            throw std::invalid_argument("eps_inherent array size mismatch");
        }

        std::vector<double> F_th(n_dof, 0.0);

        double D[6][6];
        compute_D_matrix(E, nu, D);

        const std::size_t n_elem = tet.size() / 4;
        for (std::size_t e = 0; e < n_elem; ++e)
        {
            const int n0 = tet[4 * e + 0];
            const int n1 = tet[4 * e + 1];
            const int n2 = tet[4 * e + 2];
            const int n3 = tet[4 * e + 3];

            const double *p0 = &nodes[3 * n0];
            const double *p1 = &nodes[3 * n1];
            const double *p2 = &nodes[3 * n2];
            const double *p3 = &nodes[3 * n3];

            double volume = 0.0;
            double grad_N[4][3];
            tet_geometry(p0, p1, p2, p3, volume, grad_N);

            double B[6][12];
            compute_B_matrix(grad_N, B);

            // Element-averaged fields
            const double T_elem = 0.25 * (temperature[n0] + temperature[n1] + temperature[n2] + temperature[n3]);
            const double eps_inh_elem = 0.25 * (eps_inherent[n0] + eps_inherent[n1] + eps_inherent[n2] + eps_inherent[n3]);

            const double dT = T_elem - T_ref;
            const double eps_iso = alpha * dT + eps_inh_elem;

            // Isotropic eigenstrain: [eps, eps, eps, 0, 0, 0]
            double eps_th[6] = {eps_iso, eps_iso, eps_iso, 0.0, 0.0, 0.0};

            double sigma_th[6];
            for (int i = 0; i < 6; ++i)
            {
                sigma_th[i] = 0.0;
                for (int j = 0; j < 6; ++j)
                {
                    sigma_th[i] += D[i][j] * eps_th[j];
                }
            }

            double f_elem[12];
            for (int i = 0; i < 12; ++i)
            {
                f_elem[i] = 0.0;
                for (int j = 0; j < 6; ++j)
                {
                    f_elem[i] += B[j][i] * sigma_th[j];
                }
                f_elem[i] *= volume;
            }

            const int dof_map[12] = {
                3 * n0, 3 * n0 + 1, 3 * n0 + 2,
                3 * n1, 3 * n1 + 1, 3 * n1 + 2,
                3 * n2, 3 * n2 + 1, 3 * n2 + 2,
                3 * n3, 3 * n3 + 1, 3 * n3 + 2};

            for (int i = 0; i < 12; ++i)
            {
                F_th[dof_map[i]] += f_elem[i];
            }
        }

        return F_th;
    }

    std::vector<double> thermal_load_3d_with_inherent_per_element(const std::vector<double> &nodes,
                                                                  const std::vector<int> &tet,
                                                                  const std::vector<double> &temperature,
                                                                  const std::vector<double> &eps_inherent,
                                                                  const std::vector<double> &E_elem,
                                                                  const std::vector<double> &nu_elem,
                                                                  const std::vector<double> &alpha_elem,
                                                                  double T_ref)
    {
        const std::size_t n_nodes = nodes.size() / 3;
        const std::size_t n_dof = 3 * n_nodes;

        if (temperature.size() != n_nodes)
        {
            throw std::invalid_argument("temperature array size mismatch");
        }
        if (eps_inherent.size() != n_nodes)
        {
            throw std::invalid_argument("eps_inherent array size mismatch");
        }
        if (tet.size() % 4 != 0)
        {
            throw std::invalid_argument("tet connectivity must be multiples of 4");
        }
        const std::size_t n_elem = tet.size() / 4;
        if (E_elem.size() != n_elem || nu_elem.size() != n_elem || alpha_elem.size() != n_elem)
        {
            throw std::invalid_argument("E/nu/alpha per-element size mismatch");
        }

        std::vector<double> F_th(n_dof, 0.0);

        for (std::size_t e = 0; e < n_elem; ++e)
        {
            const double E = E_elem[e];
            const double nu = nu_elem[e];
            const double alpha = alpha_elem[e];

            double D[6][6];
            compute_D_matrix(E, nu, D);

            const int n0 = tet[4 * e + 0];
            const int n1 = tet[4 * e + 1];
            const int n2 = tet[4 * e + 2];
            const int n3 = tet[4 * e + 3];

            const double *p0 = &nodes[3 * n0];
            const double *p1 = &nodes[3 * n1];
            const double *p2 = &nodes[3 * n2];
            const double *p3 = &nodes[3 * n3];

            double volume = 0.0;
            double grad_N[4][3];
            tet_geometry(p0, p1, p2, p3, volume, grad_N);

            double B[6][12];
            compute_B_matrix(grad_N, B);

            const double T_elem = 0.25 * (temperature[n0] + temperature[n1] + temperature[n2] + temperature[n3]);
            const double eps_inh_elem = 0.25 * (eps_inherent[n0] + eps_inherent[n1] + eps_inherent[n2] + eps_inherent[n3]);

            const double dT = T_elem - T_ref;
            const double eps_iso = alpha * dT + eps_inh_elem;

            double eps_th[6] = {eps_iso, eps_iso, eps_iso, 0.0, 0.0, 0.0};

            double sigma_th[6];
            for (int i = 0; i < 6; ++i)
            {
                sigma_th[i] = 0.0;
                for (int j = 0; j < 6; ++j)
                {
                    sigma_th[i] += D[i][j] * eps_th[j];
                }
            }

            double f_elem[12];
            for (int i = 0; i < 12; ++i)
            {
                f_elem[i] = 0.0;
                for (int j = 0; j < 6; ++j)
                {
                    f_elem[i] += B[j][i] * sigma_th[j];
                }
                f_elem[i] *= volume;
            }

            const int dof_map[12] = {
                3 * n0, 3 * n0 + 1, 3 * n0 + 2,
                3 * n1, 3 * n1 + 1, 3 * n1 + 2,
                3 * n2, 3 * n2 + 1, 3 * n2 + 2,
                3 * n3, 3 * n3 + 1, 3 * n3 + 2};

            for (int i = 0; i < 12; ++i)
            {
                F_th[dof_map[i]] += f_elem[i];
            }
        }

        return F_th;
    }

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
                                                         double H_iso)
    {
        if (nodes.size() % 3 != 0)
        {
            throw std::invalid_argument("nodes size must be multiples of 3 (x,y,z triplets)");
        }
        const std::size_t n_nodes = nodes.size() / 3;
        const std::size_t n_dof = 3 * n_nodes;

        if (tet.size() % 4 != 0)
        {
            throw std::invalid_argument("tet connectivity must be multiples of 4");
        }
        const std::size_t n_elem = tet.size() / 4;

        if (temperature.size() != n_nodes)
        {
            throw std::invalid_argument("temperature array size mismatch");
        }
        if (displacement.size() != n_dof)
        {
            throw std::invalid_argument("displacement array size mismatch");
        }
        if (E_elem.size() != n_elem || nu_elem.size() != n_elem || alpha_elem.size() != n_elem)
        {
            throw std::invalid_argument("E/nu/alpha per-element size mismatch");
        }

        std::vector<double> epsp_out(6 * n_elem, 0.0);
        std::vector<double> epbar_out(n_elem, 0.0);
        if (!epsp_prev.empty())
        {
            if (epsp_prev.size() != 6 * n_elem)
            {
                throw std::invalid_argument("epsp_prev size mismatch");
            }
            epsp_out = epsp_prev;
        }
        if (!epbar_prev.empty())
        {
            if (epbar_prev.size() != n_elem)
            {
                throw std::invalid_argument("epbar_prev size mismatch");
            }
            epbar_out = epbar_prev;
        }

        MechanicsAssembly Kasm;
        Kasm.dof_count = n_dof;
        Kasm.rows.reserve(n_elem * 144);
        Kasm.cols.reserve(n_elem * 144);
        Kasm.values.reserve(n_elem * 144);

        std::vector<double> F_int(n_dof, 0.0);

        for (std::size_t e = 0; e < n_elem; ++e)
        {
            const double E = E_elem[e];
            const double nu = nu_elem[e];
            const double alpha = alpha_elem[e];

            double D[6][6];
            compute_D_matrix(E, nu, D);
            const double G = E / (2.0 * (1.0 + nu));

            const int n0 = tet[4 * e + 0];
            const int n1 = tet[4 * e + 1];
            const int n2 = tet[4 * e + 2];
            const int n3 = tet[4 * e + 3];

            if (n0 < 0 || n1 < 0 || n2 < 0 || n3 < 0 ||
                static_cast<std::size_t>(n0) >= n_nodes ||
                static_cast<std::size_t>(n1) >= n_nodes ||
                static_cast<std::size_t>(n2) >= n_nodes ||
                static_cast<std::size_t>(n3) >= n_nodes)
            {
                throw std::out_of_range("tet node index out of range");
            }

            const double *p0 = &nodes[3 * n0];
            const double *p1 = &nodes[3 * n1];
            const double *p2 = &nodes[3 * n2];
            const double *p3 = &nodes[3 * n3];

            double volume = 0.0;
            double grad_N[4][3];
            tet_geometry(p0, p1, p2, p3, volume, grad_N);

            double B[6][12];
            compute_B_matrix(grad_N, B);

            const int dof_map[12] = {
                3 * n0, 3 * n0 + 1, 3 * n0 + 2,
                3 * n1, 3 * n1 + 1, 3 * n1 + 2,
                3 * n2, 3 * n2 + 1, 3 * n2 + 2,
                3 * n3, 3 * n3 + 1, 3 * n3 + 2};

            double u_elem[12];
            for (int i = 0; i < 12; ++i)
            {
                u_elem[i] = displacement[dof_map[i]];
            }

            double eps_total[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
            for (int i = 0; i < 6; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    eps_total[i] += B[i][j] * u_elem[j];
                }
            }

            const double T_elem = 0.25 * (temperature[n0] + temperature[n1] + temperature[n2] + temperature[n3]);
            const double dT = T_elem - T_ref;
            double eps_th[6] = {alpha * dT, alpha * dT, alpha * dT, 0.0, 0.0, 0.0};

            double epsp_old[6];
            for (int i = 0; i < 6; ++i)
            {
                epsp_old[i] = epsp_out[6 * e + i];
            }

            double eps_e_tr[6];
            for (int i = 0; i < 6; ++i)
            {
                eps_e_tr[i] = eps_total[i] - eps_th[i] - epsp_old[i];
            }

            double sigma_tr[6] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
            for (int i = 0; i < 6; ++i)
            {
                for (int j = 0; j < 6; ++j)
                {
                    sigma_tr[i] += D[i][j] * eps_e_tr[j];
                }
            }

            double s_tr[6];
            double p_mean = 0.0;
            voigt_deviatoric(sigma_tr, s_tr, p_mean);

            const double s_norm2 = voigt_dev_norm2(s_tr);
            const double s_eq = std::sqrt(1.5 * s_norm2);
            const double sig_y = sigma_y0 + H_iso * epbar_out[e];

            double sigma[6];
            double D_tan[6][6];
            if (s_eq <= sig_y || s_eq < 1e-12)
            {
                for (int i = 0; i < 6; ++i)
                {
                    sigma[i] = sigma_tr[i];
                }
                for (int i = 0; i < 6; ++i)
                {
                    for (int j = 0; j < 6; ++j)
                    {
                        D_tan[i][j] = D[i][j];
                    }
                }
            }
            else
            {
                const double delta_lambda = (s_eq - sig_y) / (3.0 * G + H_iso);
                const double scale = 1.0 - (3.0 * G * delta_lambda) / s_eq;
                for (int i = 0; i < 6; ++i)
                {
                    sigma[i] = scale * s_tr[i];
                }
                sigma[0] += p_mean;
                sigma[1] += p_mean;
                sigma[2] += p_mean;

                for (int i = 0; i < 6; ++i)
                {
                    const double depsp = delta_lambda * 1.5 * s_tr[i] / s_eq;
                    epsp_out[6 * e + i] = epsp_old[i] + depsp;
                }
                epbar_out[e] += delta_lambda;

                // Consistent tangent: C_ep = C - (2G)^2/(3G+H) * (n ⊗ n)
                double n_dir[6];
                const double inv_s_eq = 1.0 / s_eq;
                for (int i = 0; i < 6; ++i)
                {
                    n_dir[i] = 1.5 * s_tr[i] * inv_s_eq;
                }

                const double coeff = (2.0 * G) * (2.0 * G) / (3.0 * G + H_iso);
                for (int i = 0; i < 6; ++i)
                {
                    for (int j = 0; j < 6; ++j)
                    {
                        D_tan[i][j] = D[i][j] - coeff * n_dir[i] * n_dir[j];
                    }
                }
            }

            double f_elem[12];
            for (int i = 0; i < 12; ++i)
            {
                f_elem[i] = 0.0;
                for (int j = 0; j < 6; ++j)
                {
                    f_elem[i] += B[j][i] * sigma[j];
                }
                f_elem[i] *= volume;
            }
            for (int i = 0; i < 12; ++i)
            {
                F_int[dof_map[i]] += f_elem[i];
            }

            double DB[6][12];
            for (int i = 0; i < 6; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    DB[i][j] = 0.0;
                    for (int k = 0; k < 6; ++k)
                    {
                        DB[i][j] += D_tan[i][k] * B[k][j];
                    }
                }
            }

            double K_elem[12][12];
            for (int i = 0; i < 12; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    K_elem[i][j] = 0.0;
                    for (int k = 0; k < 6; ++k)
                    {
                        K_elem[i][j] += B[k][i] * DB[k][j];
                    }
                    K_elem[i][j] *= volume;
                }
            }

            for (int i = 0; i < 12; ++i)
            {
                for (int j = 0; j < 12; ++j)
                {
                    Kasm.rows.push_back(dof_map[i]);
                    Kasm.cols.push_back(dof_map[j]);
                    Kasm.values.push_back(K_elem[i][j]);
                }
            }
        }

        ElastoplasticAssembly out;
        out.stiffness = Kasm;
        out.internal_force = F_int;
        out.epsp = epsp_out;
        out.epbar = epbar_out;
        return out;
    }

} // namespace thermo
