#!/usr/bin/env python3
"""
Calibrated Keel Plate Simulation - Target R=11.48m
Based on empirical calibration from practical (R=19.87m) and enhanced (R=3.32m)

Strategy: Interpolate between validated results
- Single pass, 1200 J/mm energy
- Calibrated eps0=0.023
"""

import json
import numpy as np
from pathlib import Path
import subprocess
import sys
import os

REPO_ROOT = Path(__file__).resolve().parents[2]

# Geometry
Lx, Ly, H = 3000.0, 1000.0, 49.0  # mm
num_lines = 5
spacing = Ly / (num_lines + 1)
lines_y = [spacing * (i+1) for i in range(num_lines)]

# Calibrated parameters (interpolated from practical and enhanced results)
target_energy = 1200  # J/mm
velocity = 10.0  # mm/s
q0 = target_energy * velocity
num_passes = 1
T_peak = 1200  # °C
r0 = 9.0  # mm
eps0_calibrated = 0.023

# Mesh
h_mesh = 60.0
h_refine = 30.0
refine_band = 120.0
dt = 3.0
t_total = 600.0

print(f"🎯 Calibrated Parameters for R=11.48m:")
print(f"   Energy: {target_energy} J/mm")
print(f"   eps0: {eps0_calibrated:.4f}")
print(f"   Passes: {num_passes}")

# Setup
result_dir = REPO_ROOT / "results" / "keel_plate_calibrated"
result_dir.mkdir(parents=True, exist_ok=True)
log_file = result_dir / "run.log"
pid_file = result_dir / "simulation.pid"

# Build command
heat_y_str = ",".join([f"{y:.2f}" for y in lines_y])

cmd = [
    sys.executable,
    str(REPO_ROOT / "thermo_fem" / "python" / "run_coupled_3d.py"),
    "--Lx", str(Lx),
    "--Ly", str(Ly),
    "--thickness", str(H),
    "--h", str(h_mesh),
    "--h-refine", str(h_refine),
    "--refine-band", str(refine_band),
    "--q0", str(q0),
    "--r0", str(r0),
    "--velocity", str(velocity),
    "--T-inf", "20.0",
    "--h-conv", "25.0",
    "--dt", str(dt),
    "--extra-time", "300",
    "--heat-mode", "simultaneous",
    "--pass-repeats", str(num_passes),
    "--heat-y-list", heat_y_str,
    "--bc", "centerline_fixed",
    "--use-inherent",
    "--eps0", str(eps0_calibrated),
    "--inh-sigma", "40.0",
    "--out", str(result_dir)
]

print(f"\n🚀 Starting calibrated simulation...")
print(f"   Log: {log_file}")

# Start
with open(log_file, 'w') as log:
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        cwd=str(REPO_ROOT),
        start_new_session=True
    )
    
    with open(pid_file, 'w') as f:
        f.write(str(proc.pid))
    
    print(f"✅ Started with PID: {proc.pid}")
    print(f"   Monitor: tail -f {log_file}")
    print(f"   Estimated: ~10-12 minutes")
