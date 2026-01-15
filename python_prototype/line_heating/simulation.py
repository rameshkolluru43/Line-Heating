"""Simulation helpers for the prototype.

`run_linear_shrinkage_plan` keeps the original lightweight aggregation.
`run_structured_plate_solver` builds a grid and returns zero fields as a
placeholder for a future FE kernel.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from .models import HeatingPass, Plan
from .shrinkage import Calibration, PlateContext, compute_shrinkage
from .solver import solve_plan_structured


def run_linear_shrinkage_plan(plan: Plan, calibration: Calibration | None = None) -> Dict[str, object]:
    """Compute shrinkage metrics for all passes and return aggregated summary.

    This function is intentionally lightweight; it prepares the data structures
    expected by a future FE solver.
    """
    cal = calibration or Calibration()
    plate_ctx = PlateContext(thickness_mm=plan.plate.thickness, steel_factor=plan.plate.material.steel_factor)

    pass_results: List[Dict[str, float]] = []
    total_energy = 0.0
    for p in sorted(plan.passes, key=lambda p: p.sequence_index):
        res = compute_shrinkage(p, plate_ctx, cal)
        p.derived_line_energy_J_mm = res["line_energy_J_per_mm"]
        p.derived_shrinkage_eps = res["shrinkage_eps"]
        p.effective_width_mm = res["effective_width_mm"]
        # line_energy_J_per_mm already includes repeats as heat input; do not multiply repeats again.
        total_energy += res["line_energy_J_per_mm"] * p.process.footprint_width_mm
        pass_results.append({"pass_id": p.id, **res})

    return {
        "pass_results": pass_results,
        "total_line_energy_J": total_energy,
        "note": "Shrinkage aggregation only; deformation not solved in this mode.",
    }


def run_structured_plate_solver(plan: Plan, calibration: Calibration | None = None) -> Dict[str, object]:
    """Wrapper around the structured-grid placeholder solver."""
    result = solve_plan_structured(plan, calibration)
    w = result.field.w
    stats = {
        "w_min": float(w.min()),
        "w_max": float(w.max()),
        "w_abs_max": float(np.abs(w).max()),
    }
    return {
        "pass_results": result.pass_results,
        "total_line_energy_J": result.total_line_energy_J,
        "grid": {
            "x": result.field.x,
            "y": result.field.y,
            "w": result.field.w,
            "kappa_x": result.field.kappa_x,
            "kappa_y": result.field.kappa_y,
            "kappa_xy": result.field.kappa_xy,
        },
        "note": result.note,
        "stats": stats,
    }
