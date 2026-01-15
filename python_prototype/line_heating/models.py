"""Core data models for the line heating prototype."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Sequence, Tuple


Point = Tuple[float, float]


@dataclass
class Material:
    grade: str = "A36"
    E: float = 210_000.0  # MPa
    nu: float = 0.3
    alpha: float = 1.2e-5  # 1/K
    yield_strength: float = 250.0  # MPa
    steel_factor: float = 1.0


@dataclass
class Fixture:
    region: str  # e.g., "edge:west", "polygon:..."
    type: Literal["free", "simply", "clamped", "spring"] = "free"
    stiffness: Optional[float] = None  # for spring support in N/mm


@dataclass
class Plate:
    id: str
    length: float  # mm
    width: float  # mm
    thickness: float  # mm
    material: Material
    fixtures: List[Fixture] = field(default_factory=list)
    mesh_size: float = 20.0  # mm nominal element size for coarse proto


@dataclass
class Target:
    mode: Literal["radius", "curvature_map", "surface_mesh"] = "radius"
    radius: Optional[float] = None  # mm; positive for convex about +z
    curvature_map_uri: Optional[str] = None
    surface_mesh_uri: Optional[str] = None
    weight_curvature: float = 1.0
    weight_deflection: float = 0.0


@dataclass
class LineGeometry:
    id: str
    name: str
    type: Literal["straight", "polyline", "spline"] = "polyline"
    points: Sequence[Point] = field(default_factory=list)
    heated_side: Literal["+z", "-z"] = "+z"
    direction: Literal["start_to_end", "end_to_start"] = "start_to_end"
    nominal_width: float = 15.0  # mm footprint


@dataclass
class Quench:
    mode: Literal["air", "water"] = "air"
    lag_s: float = 0.0
    zones: List[str] = field(default_factory=list)


@dataclass
class PassProcess:
    power_W: float
    speed_mm_s: float
    footprint_width_mm: float
    repeats: int = 1
    quench: Quench = field(default_factory=Quench)
    steel_factor_G: float = 1.0


@dataclass
class HeatingPass:
    id: str
    line_id: str
    sequence_index: int
    process: PassProcess
    derived_line_energy_J_mm: Optional[float] = None
    derived_shrinkage_eps: Optional[float] = None
    effective_width_mm: Optional[float] = None


@dataclass
class SimulationSettings:
    model: Literal["shrinkage_band", "mindlin_q4"] = "shrinkage_band"
    band_profile: Literal["top_hat", "gaussian"] = "top_hat"
    sigma_mm: Optional[float] = None  # for gaussian
    rel_tol: float = 1e-6
    max_iter: int = 10_000
    boundary_condition: Literal["clamped", "simply", "free", "corners_simply", "corners_clamped"] = "clamped"  # support pattern
    cooling_decay_per_mm: float = 0.0  # exponential decay factor along line length; 0 disables


@dataclass
class Plan:
    meta_version: str
    plate: Plate
    target: Target
    lines: List[LineGeometry]
    passes: List[HeatingPass]
    calibration: Optional[dict] = None  # placeholder for C0, a, b, Q lookup
    simulation: SimulationSettings = field(default_factory=SimulationSettings)
