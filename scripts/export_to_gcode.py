#!/usr/bin/env python3
"""Export a line-heating plan to G-code."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def to_feedrate_mm_min(v_mm_s: float) -> float:
    return float(v_mm_s) * 60.0


def export_gcode(plan: dict, dwell_s: float) -> str:
    lines = []
    lines.append("(Plate line heating program)")
    lines.append("G90 G21")
    lines.append("M03")

    for i, line in enumerate(plan["lines"], start=1):
        y = float(line["y_mm"])
        x0 = float(line["x_start_mm"])
        x1 = float(line["x_end_mm"])
        v = float(line["velocity_mm_s"])
        feed = to_feedrate_mm_min(v)
        passes = int(line.get("passes", 1))

        for p in range(passes):
            lines.append(f"(Line {i}, pass {p + 1}/{passes})")
            lines.append(f"G01 X{x0:.3f} Y{y:.3f} F{feed:.1f}")
            lines.append(f"G01 X{x1:.3f} Y{y:.3f} F{feed:.1f}")
            if dwell_s > 0 and p < passes - 1:
                lines.append(f"G04 P{dwell_s:.1f}")

    lines.append("M05")
    lines.append("M30")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="Path to planner output JSON.")
    parser.add_argument("--output", required=True, help="Path to output G-code file.")
    parser.add_argument("--dwell", type=float, default=0.0, help="Dwell time between passes (s).")
    args = parser.parse_args()

    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    gcode = export_gcode(plan, args.dwell)

    out_path = Path(args.output)
    out_path.write_text(gcode, encoding="utf-8")


if __name__ == "__main__":
    main()
