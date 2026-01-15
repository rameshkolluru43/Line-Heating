#include "heat.hpp"

#include <stdexcept>

namespace thermo
{

    namespace
    {

        // Compute area and b,c coefficients for linear triangle
        inline void tri_geom(const double *n0, const double *n1, const double *n2,
                             double &area, double b[3], double c[3])
        {
            b[0] = n1[1] - n2[1];
            b[1] = n2[1] - n0[1];
            b[2] = n0[1] - n1[1];

            c[0] = n2[0] - n1[0];
            c[1] = n0[0] - n2[0];
            c[2] = n1[0] - n0[0];

            area = 0.5 * (n0[0] * (n1[1] - n2[1]) + n1[0] * (n2[1] - n0[1]) + n2[0] * (n0[1] - n1[1]));
        }

    } // namespace

    HeatAssembly assemble_heat_2d(const std::vector<double> &nodes,
                                  const std::vector<int> &tri,
                                  double k_cond,
                                  double rho,
                                  double cp)
    {
        if (nodes.size() % 2 != 0)
        {
            throw std::invalid_argument("nodes size must be even (x,y pairs)");
        }
        const std::size_t n_nodes = nodes.size() / 2;
        if (tri.size() % 3 != 0)
        {
            throw std::invalid_argument("tri connectivity must be multiples of 3");
        }

        HeatAssembly asmbl;
        asmbl.node_count = n_nodes;
        asmbl.mass_lumped.assign(n_nodes, 0.0);

        const std::size_t n_elem = tri.size() / 3;
        asmbl.rows.reserve(n_elem * 9);
        asmbl.cols.reserve(n_elem * 9);
        asmbl.values.reserve(n_elem * 9);

        for (std::size_t e = 0; e < n_elem; ++e)
        {
            const int n0 = tri[3 * e + 0];
            const int n1 = tri[3 * e + 1];
            const int n2 = tri[3 * e + 2];
            if (n0 < 0 || n1 < 0 || n2 < 0 || static_cast<std::size_t>(n0) >= n_nodes || static_cast<std::size_t>(n1) >= n_nodes || static_cast<std::size_t>(n2) >= n_nodes)
            {
                throw std::out_of_range("triangle node index out of range");
            }

            const double *p0 = &nodes[2 * n0];
            const double *p1 = &nodes[2 * n1];
            const double *p2 = &nodes[2 * n2];
            double area = 0.0;
            double b[3];
            double c[3];
            tri_geom(p0, p1, p2, area, b, c);
            if (area <= 0)
            {
                throw std::runtime_error("non-positive triangle area detected");
            }

            // Element conductivity matrix Ke = k * (b_i b_j + c_i c_j) / (4A)
            const double factor = k_cond / (4.0 * area);
            double ke[3][3];
            for (int i = 0; i < 3; ++i)
            {
                for (int j = 0; j < 3; ++j)
                {
                    ke[i][j] = factor * (b[i] * b[j] + c[i] * c[j]);
                }
            }

            // Lumped mass: rho * cp * area / 3 per node
            const double m_lump = rho * cp * area / 3.0;
            asmbl.mass_lumped[n0] += m_lump;
            asmbl.mass_lumped[n1] += m_lump;
            asmbl.mass_lumped[n2] += m_lump;

            const int nodes_local[3] = {n0, n1, n2};
            for (int i = 0; i < 3; ++i)
            {
                for (int j = 0; j < 3; ++j)
                {
                    asmbl.rows.push_back(nodes_local[i]);
                    asmbl.cols.push_back(nodes_local[j]);
                    asmbl.values.push_back(ke[i][j]);
                }
            }
        }

        return asmbl;
    }

} // namespace thermo
