"""JSON-friendly helpers for Plan import/export."""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List

from .models import (
    Fixture,
    HeatingPass,
    LineGeometry,
    Material,
    PassProcess,
    Plate,
    Plan,
    Quench,
    SimulationSettings,
    Target,
)


def plan_to_dict(plan: Plan) -> Dict[str, Any]:
    """Convert a Plan to a plain dict suitable for JSON serialization."""
    return asdict(plan)


def save_plan_json(plan: Plan, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(plan_to_dict(plan), f, indent=2)


def _fixtures_from_dict(items: List[Dict[str, Any]]) -> List[Fixture]:
    return [Fixture(**item) for item in items]


def _material_from_dict(data: Dict[str, Any]) -> Material:
    return Material(**data)


def _plate_from_dict(data: Dict[str, Any]) -> Plate:
    material = _material_from_dict(data["material"])
    fixtures = _fixtures_from_dict(data.get("fixtures", []))
    return Plate(
        id=data["id"],
        length=data["length"],
        width=data["width"],
        thickness=data["thickness"],
        material=material,
        fixtures=fixtures,
        mesh_size=data.get("mesh_size", 20.0),
    )


def _target_from_dict(data: Dict[str, Any]) -> Target:
    return Target(**data)


def _line_from_dict(data: Dict[str, Any]) -> LineGeometry:
    return LineGeometry(**data)


def _quench_from_dict(data: Dict[str, Any]) -> Quench:
    return Quench(**data)


def _process_from_dict(data: Dict[str, Any]) -> PassProcess:
    q = _quench_from_dict(data.get("quench", {}))
    return PassProcess(
        power_W=data["power_W"],
        speed_mm_s=data["speed_mm_s"],
        footprint_width_mm=data["footprint_width_mm"],
        repeats=data.get("repeats", 1),
        quench=q,
        steel_factor_G=data.get("steel_factor_G", 1.0),
    )


def _pass_from_dict(data: Dict[str, Any]) -> HeatingPass:
    proc = _process_from_dict(data["process"])
    return HeatingPass(
        id=data["id"],
        line_id=data["line_id"],
        sequence_index=data["sequence_index"],
        process=proc,
    )


def _simulation_settings_from_dict(data: Dict[str, Any]) -> SimulationSettings:
    return SimulationSettings(
        model=data.get("model", "shrinkage_band"),
        band_profile=data.get("band_profile", "top_hat"),
        sigma_mm=data.get("sigma_mm"),
        rel_tol=data.get("rel_tol", 1e-6),
        max_iter=data.get("max_iter", 10_000),
        boundary_condition=data.get("boundary_condition", "clamped"),
    )


def plan_from_dict(data: Dict[str, Any]) -> Plan:
    plate = _plate_from_dict(data["plate"])
    target = _target_from_dict(data["target"])
    lines = [_line_from_dict(item) for item in data.get("lines", [])]
    passes = [_pass_from_dict(item) for item in data.get("passes", [])]
    simulation = _simulation_settings_from_dict(data.get("simulation", {}))
    return Plan(
        meta_version=data.get("meta_version", "0.1.0"),
        plate=plate,
        target=target,
        lines=lines,
        passes=passes,
        calibration=data.get("calibration"),
        simulation=simulation,
    )


def load_plan_json(path: str) -> Plan:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return plan_from_dict(data)
