#pragma once

#include <cstddef>
#include <vector>

namespace thermo
{

    struct HeatAssembly
    {
        std::vector<int> rows;
        std::vector<int> cols;
        std::vector<double> values;
        std::vector<double> mass_lumped;
        std::size_t node_count{};
    };

    // Assemble 2D linear triangle conduction matrix and lumped mass.
    // nodes: flat array [x0, y0, x1, y1, ...], tri connectivity: [n0, n1, n2, ...]
    HeatAssembly assemble_heat_2d(const std::vector<double> &nodes,
                                  const std::vector<int> &tri,
                                  double k_cond,
                                  double rho,
                                  double cp);

} // namespace thermo
