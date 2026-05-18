#!/usr/bin/env python3
"""
Enhanced Keel Plate Simulation
Target: R=11.48m curvature (2× stronger than practical version)

Strategy:
1. Increase energy: 1600 J/mm (1.65× practical)
2. Use 2 heating passes (cumulative effect)
3. Higher inherent strain: eps0=0.038
4. Keep coarse mesh (h=60mm) for reasonable runtime
"""

import json
import numpy as np
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Target parameters
Lx, Ly, H = 3000.0, 1000.0, 49.0  # mm
num_lines = 5
spacing = Ly / (num_lines + 1)
lines_y = [spacing * (i+1) for i in range(num_lines)]

# Enhanced heating parameters
target_energy = 1600  # J/mm (increased from 970)
velocity = 10.0  # mm/s
q0 = target_energy * velocity  # W/mm²
num_passes = 2  # Two passes for cumulative effect

# Thermal parameters
T_peak = 1200  # °C (high temperature)
r0 = 9.0  # mm (heat source radius)

# Enhanced inherent strain (scaled for higher energy + 2 passes)
# Base: eps0 ~ 0.025 for 970 J/mm single pass
# Scaling: eps0 ∝ E^0.35 * pass_factor
# Energy ratio: (1600/970)^0.35 = 1.167
# Pass factor: 1.4 for 2 passes (not quite 2× due to diminishing returns)
eps0_base = 0.025
energy_scale = (target_energy / 970) ** 0.35
pass_scale = 1.4  # empirical for 2 passes
eps0_enhanced = eps0_base * energy_scale * pass_scale
print(f"Enhanced eps0: {eps0_enhanced:.4f} (energy_scale={energy_scale:.3f}, pass_scale={pass_scale})")

# Mesh parameters (coarse for speed)
h_mesh = 60.0  # mm
h_refine = 30.0
refine_band = 120.0

# Time stepping
dt = 3.0  # s
t_total = 600.0  # s (heating duration)

# Generate heating lines
heat_lines = []
for y in lines_y:
    heat_lines.append({
        "x0": 0.0,
        "y0": y,
        "x1": Lx,
        "y1": y
    })

# Create configuration
config = {
    "_description": "Enhanced keel plate - 2 passes, 1600 J/mm, higher eps0",
    
    "geometry": {
        "Lx": Lx,
        "Ly": Ly,
        "thickness": H
    },
    
    "mesh": {
        "h": h_mesh,
        "h_refine": h_refine,
        "refine_band": refine_band,
        "mesh_algorithm": "Delaunay"
    },
    
    "material": {
        "young_modulus": 210000.0,
        "poisson_ratio": 0.3,
        "thermal_expansion": 1.2e-05,
        "density": 7850.0,
        "specific_heat": 500.0,
        "thermal_conductivity": 50.0
    },
    
    "heating": {
        "mode": "simultaneous",
        "q0": q0,
        "r0": r0,
        "T_peak": T_peak,
        "velocity": velocity,
        "heat_lines": heat_lines,
        "pass_repeats": num_passes,
        "pass_gap": 0.0
    },
    
    "inherent_strain": {
        "eps0": eps0_enhanced,
        "band_width": 40.0
    },
    
    "boundary": {
        "bc_type": "centerline_fixed"
    },
    
    "solver": {
        "dt": dt,
        "t_total": t_total,
        "T_amb": 20.0,
        "convection_coef": 25.0
    },
    
    "output": {
        "result_dir": str(REPO_ROOT / "results" / "keel_plate_enhanced")
    }
}

# Save configuration
output_dir = REPO_ROOT / "config"
output_dir.mkdir(parents=True, exist_ok=True)
config_file = output_dir / "keel_plate_enhanced.json"

with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print(f"\n✅ Created enhanced configuration: {config_file}")
print(f"\nKey parameters:")
print(f"  Energy:        {target_energy} J/mm ({target_energy/970:.2f}× practical)")
print(f"  Heat flux:     {q0:.1f} W/mm²")
print(f"  Velocity:      {velocity} mm/s")
print(f"  Passes:        {num_passes}")
print(f"  Lines:         {num_lines} at {spacing:.1f}mm spacing")
print(f"  Temperature:   {T_peak}°C")
print(f"  Inherent ε₀:   {eps0_enhanced:.4f} ({eps0_enhanced/0.025:.2f}× base)")
print(f"  Mesh size:     {h_mesh}mm")

# Run simulation
import subprocess
import sys
import os

result_dir = Path(config["output"]["result_dir"]).resolve()
result_dir.mkdir(parents=True, exist_ok=True)

log_file = result_dir / "run.log"
pid_file = result_dir / "simulation.pid"

# Convert heating lines to command format
heat_y_list = [line["y0"] for line in heat_lines]
heat_y_str = ",".join(map(str, heat_y_list))

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
    "--pass-gap", "0.0",
    "--heat-y-list", heat_y_str,
    "--bc", "centerline_fixed",
    "--use-inherent",
    "--eps0", str(eps0_enhanced),
    "--inh-sigma", "40.0",
    "--out", str(result_dir)
]

print(f"\n🚀 Starting enhanced simulation...")
print(f"   Log: {log_file}")
print(f"   Results: {result_dir}")

# Start simulation with nohup
with open(log_file, 'w') as log:
    proc = subprocess.Popen(
        cmd,
        stdout=log,
        stderr=subprocess.STDOUT,
        cwd=os.getcwd(),
        start_new_session=True
    )
    
    # Save PID
    with open(pid_file, 'w') as f:
        f.write(str(proc.pid))
    
    print(f"\n✅ Simulation started with PID: {proc.pid}")
    print(f"\nMonitor progress:")
    print(f"  tail -f {log_file}")
    print(f"  ps -p {proc.pid}")
    print(f"\nEstimated runtime: ~15-25 minutes (2 passes)")
