#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "heat.hpp"
#include "mechanics.hpp"

namespace py = pybind11;
using namespace thermo;

PYBIND11_MODULE(thermo_bindings, m)
{
    m.doc() = "Thermo FEM core bindings";

    py::class_<HeatAssembly>(m, "HeatAssembly")
        .def_readonly("rows", &HeatAssembly::rows)
        .def_readonly("cols", &HeatAssembly::cols)
        .def_readonly("values", &HeatAssembly::values)
        .def_readonly("mass_lumped", &HeatAssembly::mass_lumped)
        .def_readonly("node_count", &HeatAssembly::node_count);

    py::class_<MechanicsAssembly>(m, "MechanicsAssembly")
        .def_readonly("rows", &MechanicsAssembly::rows)
        .def_readonly("cols", &MechanicsAssembly::cols)
        .def_readonly("values", &MechanicsAssembly::values)
        .def_readonly("dof_count", &MechanicsAssembly::dof_count);

    m.def("assemble_heat_2d", &assemble_heat_2d, py::arg("nodes"), py::arg("tri"),
          py::arg("k_cond"), py::arg("rho"), py::arg("cp"),
          "Assemble 2D linear triangle conduction matrix and lumped mass.");

    m.def("assemble_elasticity_3d", &assemble_elasticity_3d,
          py::arg("nodes"), py::arg("tet"), py::arg("E"), py::arg("nu"),
          "Assemble 3D linear tetrahedral elasticity stiffness matrix.");

    m.def("thermal_load_3d", &thermal_load_3d,
          py::arg("nodes"), py::arg("tet"), py::arg("temperature"),
          py::arg("E"), py::arg("nu"), py::arg("alpha"), py::arg("T_ref"),
          "Compute thermal load vector from thermal strain.");

    m.def("thermal_load_3d_with_inherent", &thermal_load_3d_with_inherent,
          py::arg("nodes"), py::arg("tet"), py::arg("temperature"), py::arg("eps_inherent"),
          py::arg("E"), py::arg("nu"), py::arg("alpha"), py::arg("T_ref"),
          "Compute load vector from isotropic thermal + inherent (eigen) strain.");
}
