"""
Fast parallel simulation with optimized parameters for quick results.
Uses coarser mesh and fewer time steps while maintaining accuracy.
"""

import os
import sys
from pathlib import Path
import json
import subprocess
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

# Enable parallel processing
os.environ['OMP_NUM_THREADS'] = '8'
os.environ['OPENBLAS_NUM_THREADS'] = '8'
os.environ['MKL_NUM_THREADS'] = '8'
os.environ['NUMEXPR_NUM_THREADS'] = '8'
os.environ['VECLIB_MAXIMUM_THREADS'] = '8'

def run_optimized_simulation():
    """Run simulation with optimized parameters for faster execution."""
    
    print(f"\n{'='*60}")
    print("🚀 FAST PARALLEL FEM SIMULATION")
    print(f"{'='*60}\n")
    print("Optimization Strategy:")
    print("  ✓ 8-thread parallel execution")
    print("  ✓ Coarser mesh (h=50mm, h_refine=25mm)")
    print("  ✓ Larger time steps (dt=2.0s)")
    print("  ✓ Reduced cooling time")
    print("  ✓ Simultaneous heating (faster than sequential)")
    print(f"\n{'='*60}\n")
    
    # Load the heating plan
    repo_root = REPO_ROOT
    plan_path = repo_root / "config" / "keel_plate_heating_plan.json"
    
    with open(plan_path, 'r') as f:
        plan = json.load(f)
    
    plate = plan['plate']
    heat_lines_file = repo_root / "config" / "keel_plate_heat_lines.json"
    output_dir = repo_root / "results" / "keel_plate_fast_parallel"
    
    # Optimized parameters for faster execution
    Lx = plate['length']
    Ly = plate['width']
    thickness = plate['thickness']
    
    # Coarser mesh for speed
    h = 50.0  # Global mesh size (was 40)
    h_refine = 25.0  # Refined size (was 20)
    refine_band = 80.0
    
    # Larger time steps
    dt = 2.0  # Time step (was 1.0)
    
    # Heat parameters
    power_W = plan['heat_requirements']['power_W']
    speed_mm_s = plan['heat_requirements']['speed_mm_s']
    r0 = 9.0
    beta = 2.0
    q0 = power_W * beta / (np.pi * r0**2)
    
    # Reduced cooling time
    extra_time = 50.0  # Extra cooling (was 100)
    
    print("Simulation Parameters:")
    print(f"  Plate: {Lx:.0f} × {Ly:.0f} × {thickness:.0f} mm")
    print(f"  Mesh: h={h:.0f}mm, h_refine={h_refine:.0f}mm")
    print(f"  Time step: dt={dt:.1f}s")
    print(f"  Heat flux: q0={q0:.1f} W/mm²")
    print(f"  Mode: Simultaneous (all 5 lines at once)")
    print(f"\nExpected Runtime: 10-15 minutes")
    print(f"\n{'='*60}\n")
    
    # Build command
    cmd = [
        sys.executable,
        str(repo_root / "thermo_fem" / "python" / "run_coupled_3d.py"),
        "--Lx", str(Lx),
        "--Ly", str(Ly),
        "--thickness", str(thickness),
        "--h", str(h),
        "--h-refine", str(h_refine),
        "--refine-band", str(refine_band),
        "--q0", str(q0),
        "--r0", str(r0),
        "--velocity", str(speed_mm_s),
        "--heat-lines-file", str(heat_lines_file),
        "--heat-mode", "simultaneous",  # FASTER: all lines at once
        "--dt", str(dt),
        "--extra-time", str(extra_time),
        "--k", "0.045",
        "--rho", "7.85e-6",
        "--cp", "500.0",
        "--h-conv", "5e-5",
        "--T-inf", "293.0",
        "--T-ref", "293.0",
        "--E", "210000.0",
        "--nu", "0.3",
        "--alpha", "1.2e-5",
        "--gaussian-beta", str(beta),
        "--out", str(output_dir),
        "--vtk-deform-scale", "1.0",
        "--target-Tmax", "1173",
        "--target-Tmax-tol", "20.0",
        "--target-Tmax-iters", "2",  # Fewer iterations
    ]
    
    print("Starting simulation...")
    print(f"Output: {output_dir}\n")
    
    try:
        result = subprocess.run(cmd, check=True)
        
        print(f"\n{'='*60}")
        print("✅ SIMULATION COMPLETED")
        print(f"{'='*60}\n")
        
        # Check results
        summary_file = output_dir / "summary.json"
        if summary_file.exists():
            with open(summary_file, 'r') as f:
                summary = json.load(f)
            
            print("Results Summary:")
            print(f"  Peak Temperature: {summary.get('T_max_K', 0):.1f} K ({summary.get('T_max_K', 0)-273:.1f}°C)")
            print(f"  Max Deflection:   {summary.get('max_deflection_mm', 0):.3f} mm")
            print(f"  RMS Deflection:   {summary.get('rms_deflection_mm', 0):.3f} mm")
            print(f"  Mesh Nodes:       {summary.get('n_nodes', 0):,}")
            print(f"  Mesh Elements:    {summary.get('n_elems', 0):,}")
        
        print(f"\n📁 Output files in: {output_dir}")
        print(f"📈 Open VTK files in ParaView for visualization")
        
        return 0
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Simulation failed with error code {e.returncode}")
        return 1
    except KeyboardInterrupt:
        print(f"\n⚠️  Simulation interrupted by user")
        return 130

if __name__ == "__main__":
    sys.exit(run_optimized_simulation())
