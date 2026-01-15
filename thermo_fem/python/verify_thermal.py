"""Quick thermal solver sanity checks.

Runs a few small cases to catch obvious regressions:
- With no heat input and ambient==T_ref, temperature should remain ~constant.
- With a moving heat flux, peak temperature should rise above T_ref.
- With temperature-dependent k/cp and radiation enabled, solver should remain stable.

Notes:
- Uses functions from run_coupled_3d.py; build thermo_bindings first.
- In this workspace, use python3.11.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from run_coupled_3d import build_plate_mesh_3d, solve_thermal_3d


def _assert_close(name: str, value: float, target: float, tol: float) -> None:
    err = abs(float(value) - float(target))
    if err > tol:
        raise AssertionError(f"{name}: |{value} - {target}| = {err} > {tol}")


def test_no_heat_stays_constant(tmp: Path) -> None:
    nodes, tet, _top_nodes, _bottom_nodes, top_tri, bottom_tri = build_plate_mesh_3d(
        Lx=200.0,
        Ly=140.0,
        thickness=10.0,
        h=60.0,
        h_refine=30.0,
        refine_band=35.0,
        out_dir=tmp,
    )

    T_ref = 293.15
    T = solve_thermal_3d(
        nodes=nodes,
        tet=tet,
        top_tri=top_tri,
        bottom_tri=bottom_tri,
        Lx=200.0,
        Ly=140.0,
        dt=1.0,
        steps=5,
        conductivity=0.03,
        density=7.85e-6,
        heat_capacity=500.0,
        q0=0.0,
        r0=10.0,
        velocity=10.0,
        h_conv=60.0,
        ambient_temperature=T_ref,
        reference_temperature=T_ref,
    )

    _assert_close("T_min", float(np.min(T)), T_ref, tol=1e-6)
    _assert_close("T_max", float(np.max(T)), T_ref, tol=1e-6)


def test_heat_increases_temperature(tmp: Path) -> None:
    nodes, tet, _top_nodes, _bottom_nodes, top_tri, bottom_tri = build_plate_mesh_3d(
        Lx=200.0,
        Ly=140.0,
        thickness=10.0,
        h=60.0,
        h_refine=25.0,
        refine_band=35.0,
        out_dir=tmp,
    )

    T_ref = 293.15
    T = solve_thermal_3d(
        nodes=nodes,
        tet=tet,
        top_tri=top_tri,
        bottom_tri=bottom_tri,
        Lx=200.0,
        Ly=140.0,
        dt=1.0,
        steps=8,
        conductivity=0.03,
        density=7.85e-6,
        heat_capacity=500.0,
        # Use a deliberately strong/wide heat input to make this a robust
        # regression check (centroid-based flux integration can under-resolve
        # narrow beams on coarse surface meshes).
        q0=500.0,
        r0=25.0,
        velocity=10.0,
        h_conv=60.0,
        ambient_temperature=T_ref,
        reference_temperature=T_ref,
    )

    if not (float(np.max(T)) > T_ref + 5.0):
        raise AssertionError(f"Expected heating to increase T_max above T_ref; got T_max={float(np.max(T))}")


def test_temp_dependent_and_radiation_stable(tmp: Path) -> None:
    nodes, tet, _top_nodes, _bottom_nodes, top_tri, bottom_tri = build_plate_mesh_3d(
        Lx=200.0,
        Ly=140.0,
        thickness=10.0,
        h=60.0,
        h_refine=25.0,
        refine_band=35.0,
        out_dir=tmp,
    )

    T_ref = 293.15
    T = solve_thermal_3d(
        nodes=nodes,
        tet=tet,
        top_tri=top_tri,
        bottom_tri=bottom_tri,
        Lx=200.0,
        Ly=140.0,
        dt=1.0,
        steps=8,
        conductivity=0.03,
        density=7.85e-6,
        heat_capacity=500.0,
        q0=500.0,
        r0=25.0,
        velocity=10.0,
        h_conv=60.0,
        ambient_temperature=T_ref,
        reference_temperature=T_ref,
        k_slope=1e-4,
        cp_slope=2e-4,
        radiation_emissivity=0.6,
        picard_iters=2,
    )

    if not np.all(np.isfinite(T)):
        raise AssertionError("Temperature array contains NaN/Inf")


def main() -> None:
    tmp = Path(__file__).parent / "outputs_verify_thermal"
    tmp.mkdir(parents=True, exist_ok=True)

    test_no_heat_stays_constant(tmp / "no_heat")
    print("PASS: no-heat constant-temperature")

    test_heat_increases_temperature(tmp / "heat")
    print("PASS: heating raises peak temperature")

    test_temp_dependent_and_radiation_stable(tmp / "tempdep_rad")
    print("PASS: temp-dependent + radiation stable")

    print("All thermal checks passed.")


if __name__ == "__main__":
    main()
