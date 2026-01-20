"""Inverse problem (surrogate): estimate heat inputs for target deflection.

This uses the trained ELM model to solve for inputs that match a target
scalar deflection (max |w|). It is a lightweight inverse solver, not a
full field inversion.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy.optimize import differential_evolution

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_model(model_path: Path) -> dict:
    model = np.load(model_path, allow_pickle=True)
    return {
        "W": model["W"],
        "b": model["b"],
        "beta": model["beta"],
        "mean": model["mean"],
        "std": model["std"],
        "activation": str(model["activation"]),
    }


def _predict(model: dict, X: np.ndarray) -> np.ndarray:
    W = model["W"]
    b = model["b"]
    beta = model["beta"]
    mean = model["mean"]
    std = model["std"]
    act = model["activation"]
    Xs = (X - mean) / std
    Z = Xs @ W.T + b
    if act == "sigmoid":
        H = 1.0 / (1.0 + np.exp(-Z))
    elif act == "tanh":
        H = np.tanh(Z)
    elif act == "relu":
        H = np.maximum(0.0, Z)
    else:
        raise ValueError(f"Unknown activation: {act}")
    return H @ beta


def _default_line_pattern(Ly: float, passes: int) -> list[float]:
    if passes <= 1:
        return [Ly * 0.5]
    gap = Ly / (passes + 1)
    return [gap * (i + 1) for i in range(passes)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Inverse solver using ELM surrogate")
    parser.add_argument("--target-deflection-mm", type=float, required=True)
    parser.add_argument("--model", type=str, default="framework/ml/models/issa_elm_model.npz")
    parser.add_argument("--thickness-mm", type=float, default=12.0)
    parser.add_argument("--passes", type=int, default=1)
    parser.add_argument("--speed-range", type=float, nargs=2, default=[5.0, 20.0])
    parser.add_argument("--energy-range", type=float, nargs=2, default=[0.0, 1200.0])
    parser.add_argument("--Ly", type=float, default=1000.0)
    args = parser.parse_args()

    model = _load_model(Path(args.model))

    target = float(args.target_deflection_mm)
    thickness = float(args.thickness_mm)
    passes = int(args.passes)

    def objective(x: np.ndarray) -> float:
        speed, energy = x
        X = np.array([[speed, energy, thickness, passes]], dtype=float)
        y = float(_predict(model, X))
        return (y - target) ** 2

    bounds = [tuple(args.speed_range), tuple(args.energy_range)]
    result = differential_evolution(objective, bounds=bounds, seed=42, polish=True)

    speed, energy = result.x
    pred = float(_predict(model, np.array([[speed, energy, thickness, passes]])))

    line_pattern = _default_line_pattern(args.Ly, passes)

    out = {
        "target_deflection_mm": target,
        "predicted_deflection_mm": pred,
        "speed_mm_s": float(speed),
        "energy_J_per_mm": float(energy),
        "passes": passes,
        "heat_y_list_mm": line_pattern,
        "notes": [
            "This inverse uses a scalar surrogate (max |w|).",
            "Energy input is not well-identified unless trained with energy variation.",
        ],
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
