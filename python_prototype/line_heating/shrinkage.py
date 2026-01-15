"""Shrinkage-band model utilities for line heating prototype."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from .models import HeatingPass


@dataclass
class Calibration:
    C0: float = 1e-3
    a: float = 0.7
    b: float = 0.5
    Q_air: float = 1.0
    Q_water: float = 1.3  # can be lag-dependent in future
    load_scale: float = 1e-6  # scales shrinkage->load mapping in FE (tunable)
    # Thermal->shrinkage mapping (when using a thermal field instead of energy law)
    thermal_cap_C: float = 700.0  # cap temperature for plastic contribution
    thermal_ref_C: float = 450.0  # below this, shrinkage is zero
    thermal_eps_ref: float = 2e-3  # reference shrinkage at cap
    thermal_exp: float = 1.0  # exponent for normalized temperature ramp
    # Numerical stabilization for Mindlin solves: fraction of max |diag(Kff)| added to diagonal
    reg_diag_scale: float = 1e-8

    def q_factor(self, mode: str) -> float:
        if mode == "water":
            return self.Q_water
        return self.Q_air


@dataclass
class PlateContext:
    thickness_mm: float
    steel_factor: float = 1.0


def compute_shrinkage(pass_: HeatingPass, plate: PlateContext, cal: Calibration) -> Dict[str, float]:
    """Compute line energy (J/mm) and shrinkage strain epsilon_s for a pass."""
    P = pass_.process.power_W
    v = pass_.process.speed_mm_s
    w = pass_.process.footprint_width_mm
    if v <= 0:
        raise ValueError("Travel speed must be positive")
    if w <= 0:
        raise ValueError("Footprint width must be positive")

    line_energy_base = P / v  # J/mm if power in J/s and speed in mm/s
    # Treat repeats as additional heat input along the same line; scale energy accordingly.
    line_energy = line_energy_base * max(1, pass_.process.repeats)
    q = cal.q_factor(pass_.process.quench.mode)
    G = pass_.process.steel_factor_G * plate.steel_factor
    t = plate.thickness_mm

    eps = cal.C0 * (line_energy ** cal.a) * (t ** (-cal.b)) * q * G
    return {
        "line_energy_J_per_mm": line_energy,
        "line_energy_base_J_per_mm": line_energy_base,
        "shrinkage_eps": eps,
        "effective_width_mm": w,
    }
