"""
Optimized heating simulation to match IGES target curvature.

Based on curvature comparison:
- IGES target: R = 11.48 m, requiring ~100 mm deflection
- Previous result: 0.044 mm deflection (2300× too small)

Optimization strategy:
1. Increase heat input significantly (slower speed or higher power)
2. Use multiple passes with cooling between passes
3. Optimize heating pattern for transverse bending
"""

import numpy as np
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def calculate_optimized_parameters():
    """
    Calculate heating parameters to achieve target deflection.
    
    Based on inherent strain theory:
    - Deflection scales with energy input per unit area
    - Need ~2300× increase in energy density
    - Can achieve through: slower speed, higher power, or multiple passes
    """
    
    print("="*60)
    print("CALCULATING OPTIMIZED HEATING PARAMETERS")
    print("="*60)
    
    # Current parameters (insufficient)
    P_current = 12000  # W (12 kW)
    v_current = 12  # mm/s
    line_energy_current = P_current / v_current  # J/mm
    
    # Target: achieve ~100 mm deflection
    # Current: 0.044 mm deflection
    scale_factor = 100.0 / 0.044  # ~2273
    
    print(f"\nCurrent Parameters:")
    print(f"  Power: {P_current/1000:.1f} kW")
    print(f"  Speed: {v_current:.1f} mm/s")
    print(f"  Line energy: {line_energy_current:.1f} J/mm")
    print(f"  Result: 0.044 mm deflection")
    
    print(f"\nTarget:")
    print(f"  Deflection: ~100 mm")
    print(f"  Required scale factor: {scale_factor:.0f}×")
    
    # Strategy 1: Reduce speed (most practical)
    # Limit speed reduction to 10× (0.12 mm/s is too slow)
    # Use multiple passes instead
    
    # Strategy 2: Multiple passes with moderate speed reduction
    v_optimized = 2.0  # mm/s (6× slower)
    n_passes = 4  # Multiple passes
    P_optimized = 15000  # W (15 kW - slightly higher power)
    
    line_energy_optimized = (P_optimized / v_optimized) * n_passes
    energy_ratio = line_energy_optimized / line_energy_current
    
    print(f"\nOptimized Strategy (Multi-pass):")
    print(f"  Power: {P_optimized/1000:.1f} kW")
    print(f"  Speed: {v_optimized:.1f} mm/s")
    print(f"  Number of passes: {n_passes}")
    print(f"  Line energy per pass: {P_optimized/v_optimized:.1f} J/mm")
    print(f"  Total line energy: {line_energy_optimized:.1f} J/mm")
    print(f"  Energy ratio: {energy_ratio:.1f}×")
    
    # Calculate Gaussian heat source parameters
    q0 = calculate_heat_flux(P_optimized)
    r0 = 9.0  # mm (same radius)
    
    print(f"\nHeat Source Parameters:")
    print(f"  Peak flux q0: {q0:.2f} W/mm²")
    print(f"  Radius r0: {r0:.1f} mm")
    
    # Cooling time between passes (allow thermal gradients to develop)
    cooling_time = 60.0  # seconds between passes
    
    print(f"  Cooling between passes: {cooling_time:.0f} s")
    
    return {
        'power': P_optimized,
        'speed': v_optimized,
        'n_passes': n_passes,
        'q0': q0,
        'r0': r0,
        'cooling_time': cooling_time,
        'line_energy': line_energy_optimized
    }


def calculate_heat_flux(power_watts, r0_mm=9.0, efficiency=0.5):
    """
    Calculate peak heat flux for Gaussian distribution.
    
    q(r) = q0 * exp(-r²/r0²)
    Total power = π * q0 * r0² * efficiency
    """
    # For a moving heat source with efficiency
    q0 = power_watts / (np.pi * r0_mm**2 * efficiency)
    return q0


def create_optimized_heating_plan(params):
    """Create heating plan with optimized parameters."""
    
    # Plate dimensions
    Lx = 3000.0  # mm
    Ly = 1000.0  # mm
    thickness = 49.0  # mm
    
    # Heating lines (same 5 lines as before)
    n_lines = 5
    y_positions = np.linspace(Ly/(n_lines+1), Ly*n_lines/(n_lines+1), n_lines)
    
    heat_lines = []
    for y in y_positions:
        heat_lines.append({
            'x0': 0.0,
            'y0': float(y),
            'x1': Lx,
            'y1': float(y)
        })
    
    plan = {
        'plate': {
            'length': Lx,
            'width': Ly,
            'thickness': thickness
        },
        'heating': {
            'power_W': params['power'],
            'speed_mm_s': params['speed'],
            'n_passes': params['n_passes'],
            'q0': params['q0'],
            'r0': params['r0'],
            'cooling_time_s': params['cooling_time'],
            'line_energy_J_mm': params['line_energy']
        },
        'lines': heat_lines
    }
    
    output_file = REPO_ROOT / "config" / "keel_plate_heating_optimized.json"
    with open(output_file, 'w') as f:
        json.dump(plan, f, indent=2)
    
    print(f"\n✅ Saved optimized heating plan: {output_file}")
    
    return output_file, heat_lines


def run_optimized_simulation(params, heat_lines):
    """Run FEM simulation with optimized parameters."""
    
    print("\n" + "="*60)
    print("RUNNING OPTIMIZED SIMULATION")
    print("="*60)
    
    # Setup paths
    repo_root = REPO_ROOT
    fem_script = repo_root / "thermo_fem" / "python" / "run_coupled_3d.py"
    output_dir = repo_root / "results" / "keel_plate_optimized"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Plate parameters
    Lx = 3000.0
    Ly = 1000.0
    thickness = 49.0
    
    # Mesh parameters (balanced: not too coarse, not too fine)
    h = 40.0  # mm (base mesh size)
    h_refine = 20.0  # mm (refined near heat lines)
    refine_band = 100.0  # mm (refinement zone width)
    
    # Time stepping
    dt = 1.5  # s (moderate time step)
    
    # Material properties (Steel A36)
    E = 210000.0  # MPa
    nu = 0.3
    alpha = 1.2e-5  # 1/K
    
    # Construct command for multi-pass heating
    cmd = [
        sys.executable,
        str(fem_script),
        f"--Lx={Lx}",
        f"--Ly={Ly}",
        f"--thickness={thickness}",
        f"--h={h}",
        f"--h-refine={h_refine}",
        f"--refine-band={refine_band}",
        f"--q0={params['q0']}",
        f"--r0={params['r0']}",
        f"--velocity={params['speed']}",
        f"--heat-mode=sequential",  # Multi-pass: sequential with cooling
        f"--pass-repeats={params['n_passes']}",
        f"--pass-gap={params['cooling_time']}",  # Cooling time between passes
        f"--dt={dt}",
        f"--E={E}",
        f"--nu={nu}",
        f"--alpha={alpha}",
        f"--out={output_dir}"
    ]
    
    # Add heating lines (use --heat-lines argument with semicolon-separated list)
    heat_lines_str = ";".join([
        f"{line['x0']},{line['y0']},{line['x1']},{line['y1']}"
        for line in heat_lines
    ])
    cmd.append(f"--heat-lines={heat_lines_str}")
    
    print(f"\nSimulation Configuration:")
    print(f"  Mesh size: h={h} mm, h_refine={h_refine} mm")
    print(f"  Time step: dt={dt} s")
    print(f"  Heat mode: sequential (multi-pass)")
    print(f"  Passes: {params['n_passes']} with {params['cooling_time']}s cooling")
    print(f"  Output: {output_dir}")
    
    print(f"\n⚠️  Estimated simulation time:")
    # Estimate: ~250 s per pass per line, 5 lines, 4 passes
    estimated_time = 250 * params['n_passes'] * len(heat_lines) / 60.0
    print(f"  Sequential heating: ~{estimated_time:.0f} minutes")
    print(f"  (This is a long simulation - consider running in background)")
    
    print(f"\nCommand:")
    print(f"  {' '.join(cmd)}")
    
    # Ask user confirmation
    print(f"\n{'='*60}")
    response = input("Start simulation now? (y/n) [n]: ").strip().lower()
    
    if response == 'y':
        print("\n🚀 Starting simulation...")
        print("(Press Ctrl+C to stop if needed)\n")
        
        # Run simulation
        result = subprocess.run(cmd, cwd=repo_root)
        
        if result.returncode == 0:
            print(f"\n✅ Simulation completed successfully!")
            print(f"📁 Results saved to: {output_dir}")
            return output_dir
        else:
            print(f"\n❌ Simulation failed with exit code {result.returncode}")
            return None
    else:
        # Save command for later execution
        cmd_file = output_dir / "run_command.sh"
        with open(cmd_file, 'w') as f:
            f.write("#!/bin/bash\n\n")
            f.write("# Optimized heating simulation\n")
            f.write("# Estimated runtime: ~{:.0f} minutes\n\n".format(estimated_time))
            f.write("cd " + str(repo_root) + "\n")
            f.write("source .venv_lineheating/bin/activate\n\n")
            f.write(" \\\n  ".join(cmd) + "\n")
        
        cmd_file.chmod(0o755)
        
        print(f"\n💾 Simulation command saved to: {cmd_file}")
        print(f"\nTo run later:")
        print(f"  {cmd_file}")
        print(f"\nOr in background with nohup:")
        print(f"  nohup {cmd_file} > {output_dir}/simulation.log 2>&1 &")
        
        return None


def create_background_script(params, heat_lines):
    """Create a script to run simulation in background."""
    
    repo_root = REPO_ROOT
    output_dir = repo_root / "results" / "keel_plate_optimized"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    script_file = output_dir / "run_optimized_background.sh"
    
    with open(script_file, 'w') as f:
        f.write("#!/bin/bash\n")
        f.write("# Optimized multi-pass heating simulation\n")
        f.write("# Background execution with nohup\n\n")
        f.write(f"cd {repo_root}\n")
        f.write("source .venv_lineheating/bin/activate\n\n")
        f.write("export OMP_NUM_THREADS=8\n")
        f.write("export OPENBLAS_NUM_THREADS=8\n\n")
        
        fem_script = repo_root / "thermo_fem" / "python" / "run_coupled_3d.py"
        
        f.write(f"python {fem_script} \\\n")
        f.write(f"  --Lx=3000.0 \\\n")
        f.write(f"  --Ly=1000.0 \\\n")
        f.write(f"  --thickness=49.0 \\\n")
        f.write(f"  --h=40.0 \\\n")
        f.write(f"  --h-refine=20.0 \\\n")
        f.write(f"  --refine-band=100.0 \\\n")
        f.write(f"  --q0={params['q0']} \\\n")
        f.write(f"  --r0={params['r0']} \\\n")
        f.write(f"  --velocity={params['speed']} \\\n")
        f.write(f"  --heat-mode=sequential \\\n")
        f.write(f"  --pass-repeats={params['n_passes']} \\\n")
        f.write(f"  --pass-gap={params['cooling_time']} \\\n")
        f.write(f"  --dt=1.5 \\\n")
        f.write(f"  --E=210000.0 \\\n")
        f.write(f"  --nu=0.3 \\\n")
        f.write(f"  --alpha=1.2e-5 \\\n")
        f.write(f"  --out={output_dir} \\\n")
        
        # Add heating lines as semicolon-separated list
        heat_lines_str = ";".join([
            f"{line['x0']},{line['y0']},{line['x1']},{line['y1']}"
            for line in heat_lines
        ])
        f.write(f'  --heat-lines="{heat_lines_str}"\n')
    
    script_file.chmod(0o755)
    
    print(f"\n✅ Created background execution script: {script_file}")
    
    return script_file


def main():
    """Main optimization workflow."""
    
    print("\n" + "="*60)
    print("OPTIMIZED HEATING PLAN FOR IGES TARGET CURVATURE")
    print("="*60)
    print("\nGoal: Achieve R = 11.48 m (deflection ~100 mm)")
    print("Previous result: 0.044 mm (2300× too small)\n")
    
    # Calculate optimized parameters
    params = calculate_optimized_parameters()
    
    # Create heating plan
    plan_file, heat_lines = create_optimized_heating_plan(params)
    
    # Create background script
    script_file = create_background_script(params, heat_lines)
    
    print(f"\n" + "="*60)
    print("📋 NEXT STEPS")
    print("="*60)
    
    print(f"\n1. Review the optimized parameters above")
    print(f"\n2. Run simulation interactively:")
    print(f"   python scripts/cases/run_keel_optimized.py --run")
    
    print(f"\n3. Or run in background (recommended for long simulations):")
    print(f"   nohup {script_file} > results/keel_plate_optimized/simulation.log 2>&1 &")
    print(f"   echo $! > results/keel_plate_optimized/simulation.pid")
    
    print(f"\n4. Monitor progress:")
    print(f"   tail -f results/keel_plate_optimized/simulation.log")
    
    print(f"\n5. After completion, compare curvature:")
    print(f"   python scripts/cases/compare_curvature.py --results-dir results/keel_plate_optimized")
    
    print(f"\n" + "="*60)
    
    # Check if user wants to run now
    if "--run" in sys.argv:
        run_optimized_simulation(params, heat_lines)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
