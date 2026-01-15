"""Minimal demo: impose inherent-strain bands and solve plate bending (biharmonic).

This uses a reduced-order surrogate: the four inherent components (Tx, Ty, Bx, By)
are collapsed into an equivalent transverse load via plate bending rigidity. It
reuses the biharmonic solver from line_heating.solver for speed.
"""
from __future__ import annotations

from line_heating.inherent import InherentStrainParams, solve_inherent_mindlin
from line_heating.models import LineGeometry, Material, Plate
from line_heating.plotting import plot_deflection_field


def main():
    # Plate and material
    material = Material(E=210e3, nu=0.3, alpha=1.2e-5)
    plate = Plate(id="demo", length=1200.0, width=800.0, thickness=12.0, material=material, mesh_size=20.0)

    # Define two heating lines (longitudinal, transverse) for illustration
    lines = [
        LineGeometry(id="L1", name="longitudinal", points=[(200.0, 100.0), (1000.0, 100.0)], heated_side="+z"),
        LineGeometry(id="L2", name="transverse", points=[(400.0, 600.0), (400.0, 200.0)], heated_side="+z"),
    ]

    # Assign inherent parameters per line (illustrative values)
    params = [
        InherentStrainParams(Tx=-2e-3, Ty=-5e-4, Bx=3e-4, By=1e-4, width_mm=80.0),
        InherentStrainParams(Tx=-1e-3, Ty=-1e-3, Bx=2e-4, By=2e-4, width_mm=60.0),
    ]

    fe_res = solve_inherent_mindlin(
        plate=plate,
        lines=lines,
        params_per_line=params,
        mesh_size_mm=20.0,
        boundary_condition="simply",
        profile="top_hat",
    )

    print(f"Deflection stats: min={fe_res.w.min():.3f} mm, max={fe_res.w.max():.3f} mm")

    # Quick plot
    plot_deflection_field(fe_res.x, fe_res.y, fe_res.w, title="Inherent-strain Mindlin demo")


if __name__ == "__main__":
    main()
