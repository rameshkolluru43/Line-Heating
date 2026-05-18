"""
Run the full 3D thermo-mechanical FEM simulation for the keel plate heating plan.

This script:
1. Loads the heating plan from config/keel_plate_heating_plan.json
2. Converts it to the format needed by thermo_fem/python/run_coupled_3d.py
3. Runs the full FEM simulation
4. Analyzes the deflection results
"""

from pathlib import Path
import json
import subprocess
import sys
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_heating_plan(plan_path: Path) -> dict:
    """Load the heating plan JSON."""
    with open(plan_path, 'r') as f:
        plan = json.load(f)
    return plan


def convert_plan_to_heat_lines(plan: dict) -> list[dict]:
    """Convert heating plan to heat_lines format for run_coupled_3d.py."""
    heat_lines = []
    for line in plan['lines']:
        points = line['points']
        heat_lines.append({
            'x0': points[0][0],
            'y0': points[0][1],
            'x1': points[1][0],
            'y1': points[1][1]
        })
    return heat_lines


def create_heat_lines_file(heat_lines: list[dict], output_path: Path):
    """Write heat lines to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump({'lines': heat_lines}, f, indent=2)
    print(f"✅ Heat lines file created: {output_path}")


def run_fem_simulation(
    plate: dict,
    heat_lines_file: Path,
    heat_requirements: dict,
    output_dir: Path,
    sequential: bool = True,
):
    """Run the 3D coupled FEM simulation."""
    
    # Extract parameters
    Lx = plate['length']
    Ly = plate['width']
    thickness = plate['thickness']
    
    # Process parameters from heat requirements
    power_W = heat_requirements['power_W']
    speed_mm_s = heat_requirements['speed_mm_s']
    footprint_mm = heat_requirements['footprint_mm']
    
    # Calculate q0 (power density) in W/mm^2
    # Total power distributed over circular area: π * r0^2
    r0 = footprint_mm / 2.0  # Gaussian radius
    # For Gaussian with peak q0: Total power = q0 * π * r0^2 / β (for β=2)
    # Rearranging: q0 = Total_Power * β / (π * r0^2)
    beta = 2.0
    q0 = power_W * beta / (np.pi * r0**2)
    
    print(f"\n{'='*60}")
    print("🔧 SIMULATION PARAMETERS")
    print(f"{'='*60}\n")
    print(f"Plate Dimensions:")
    print(f"  Length (Lx):     {Lx:.1f} mm")
    print(f"  Width (Ly):      {Ly:.1f} mm")
    print(f"  Thickness:       {thickness:.1f} mm")
    print(f"\nHeating Parameters:")
    print(f"  Torch Power:     {power_W/1000:.1f} kW")
    print(f"  Travel Speed:    {speed_mm_s:.1f} mm/s")
    print(f"  Gaussian r0:     {r0:.1f} mm")
    print(f"  Peak Flux q0:    {q0:.2f} W/mm²")
    print(f"  Heating Mode:    {'Sequential' if sequential else 'Simultaneous'}")
    
    # Mesh parameters - coarser for large plate
    h = 40.0  # Global mesh size
    h_refine = 20.0  # Refined mesh near heating lines
    refine_band = 80.0  # Refinement band width
    
    # Time stepping
    dt = 1.0  # Time step (s)
    scan_time = Lx / speed_mm_s
    extra_time = 100.0  # Extra cooling time after scan
    
    print(f"\nMesh Parameters:")
    print(f"  Global size h:   {h:.1f} mm")
    print(f"  Refined h:       {h_refine:.1f} mm")
    print(f"  Refine band:     {refine_band:.1f} mm")
    print(f"\nTime Parameters:")
    print(f"  Time step dt:    {dt:.1f} s")
    print(f"  Scan time:       {scan_time:.1f} s ({scan_time/60:.1f} min)")
    print(f"  Extra cooling:   {extra_time:.1f} s ({extra_time/60:.1f} min)")
    print(f"  Total time:      {scan_time + extra_time:.1f} s ({(scan_time + extra_time)/60:.1f} min)")
    
    # Material properties (steel A36)
    k = 0.045  # W/(mm·K)
    rho = 7.85e-6  # kg/mm³
    cp = 500.0  # J/(kg·K)
    E = 210000.0  # MPa
    nu = 0.3
    alpha = 1.2e-5  # 1/K
    h_conv = 5e-5  # W/(mm²·K)
    T_inf = 293.0  # K (20°C)
    T_ref = 293.0  # K
    
    # Build command
    cmd = [
        sys.executable,
        str(REPO_ROOT / "thermo_fem" / "python" / "run_coupled_3d.py"),
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
        "--heat-mode", "sequential" if sequential else "simultaneous",
        "--dt", str(dt),
        "--extra-time", str(extra_time),
        "--k", str(k),
        "--rho", str(rho),
        "--cp", str(cp),
        "--h-conv", str(h_conv),
        "--T-inf", str(T_inf),
        "--T-ref", str(T_ref),
        "--E", str(E),
        "--nu", str(nu),
        "--alpha", str(alpha),
        "--gaussian-beta", str(beta),
        "--out", str(output_dir),
        "--vtk-deform-scale", "1.0",  # No scaling for realistic deflection
    ]
    
    # Add target temperature tuning if desired
    target_temp = 900 + 273  # 900°C in Kelvin
    cmd.extend([
        "--target-Tmax", str(target_temp),
        "--target-Tmax-tol", "20.0",
        "--target-Tmax-iters", "3",
    ])
    
    # Add water quench simulation
    if sequential:
        cmd.extend([
            "--quench",
            "--quench-h-conv", "5e-3",  # Strong water quench
            "--pass-gap", "120.0",  # 120s between passes
        ])
    
    print(f"\n{'='*60}")
    print("🚀 RUNNING FEM SIMULATION")
    print(f"{'='*60}\n")
    print(f"Command: {' '.join(cmd[:10])}...")
    print(f"Output directory: {output_dir}")
    print(f"\nThis may take several minutes...\n")
    
    # Run the simulation
    try:
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        print(f"\n{'='*60}")
        print("✅ SIMULATION COMPLETED SUCCESSFULLY")
        print(f"{'='*60}\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n{'='*60}")
        print("❌ SIMULATION FAILED")
        print(f"{'='*60}\n")
        print(f"Error: {e}")
        return False


def analyze_results(output_dir: Path):
    """Analyze the simulation results."""
    
    print(f"\n{'='*60}")
    print("📊 ANALYZING RESULTS")
    print(f"{'='*60}\n")
    
    # Check for summary.json
    summary_file = output_dir / "summary.json"
    if summary_file.exists():
        with open(summary_file, 'r') as f:
            summary = json.load(f)
        
        print("Simulation Summary:")
        print(f"  Peak Temperature: {summary.get('T_max_K', 'N/A'):.1f} K ({summary.get('T_max_K', 0) - 273:.1f}°C)")
        print(f"  Max Deflection:   {summary.get('max_deflection_mm', 'N/A'):.3f} mm")
        print(f"  Min Deflection:   {summary.get('min_deflection_mm', 'N/A'):.3f} mm")
        print(f"  RMS Deflection:   {summary.get('rms_deflection_mm', 'N/A'):.3f} mm")
    else:
        print("⚠️  No summary.json found")
    
    # Check for deflection data
    deflection_file = output_dir / "deflection_solution.npy"
    if deflection_file.exists():
        w = np.load(deflection_file)
        print(f"\nDeflection Statistics:")
        print(f"  Maximum: {np.max(np.abs(w)):.3f} mm")
        print(f"  Minimum: {np.min(w):.3f} mm")
        print(f"  Mean:    {np.mean(w):.3f} mm")
        print(f"  Std Dev: {np.std(w):.3f} mm")
    else:
        print("⚠️  No deflection_solution.npy found")
    
    # List output files
    print(f"\n📁 Output Files:")
    vtk_files = list(output_dir.glob("*.vtk"))
    png_files = list(output_dir.glob("*.png"))
    json_files = list(output_dir.glob("*.json"))
    
    if vtk_files:
        print(f"  VTK files: {len(vtk_files)}")
        for f in vtk_files[:3]:  # Show first 3
            print(f"    - {f.name}")
        if len(vtk_files) > 3:
            print(f"    ... and {len(vtk_files) - 3} more")
    
    if png_files:
        print(f"  PNG plots: {len(png_files)}")
        for f in png_files[:3]:
            print(f"    - {f.name}")
        if len(png_files) > 3:
            print(f"    ... and {len(png_files) - 3} more")
    
    if json_files:
        print(f"  JSON files: {len(json_files)}")
        for f in json_files:
            print(f"    - {f.name}")
    
    print(f"\n{'='*60}")
    print("📈 VISUALIZATION")
    print(f"{'='*60}\n")
    print("To visualize results in ParaView:")
    print(f"  1. Open ParaView")
    print(f"  2. Load: {output_dir / 'undeformed.vtk'}")
    print(f"  3. Load: {output_dir / 'deformed.vtk'}")
    print(f"  4. View temperature and deflection fields")
    print(f"\nPlots are also available as PNG files in: {output_dir}")


def main():
    """Main execution function."""
    
    print(f"\n{'='*60}")
    print("🔥 KEEL PLATE LINE HEATING FEM SIMULATION")
    print(f"{'='*60}\n")
    
    # Paths
    repo_root = REPO_ROOT
    plan_path = repo_root / "config" / "keel_plate_heating_plan.json"
    heat_lines_path = repo_root / "config" / "keel_plate_heat_lines.json"
    output_dir = repo_root / "results" / "keel_plate_simulation"
    
    # Check if plan exists
    if not plan_path.exists():
        print(f"❌ Heating plan not found: {plan_path}")
        print("Run scripts/cases/analyze_keel_plate.py first to generate the plan.")
        return 1
    
    # Load plan
    print(f"📖 Loading heating plan from: {plan_path}")
    plan = load_heating_plan(plan_path)
    
    # Convert to heat lines format
    print(f"🔄 Converting plan to heat lines format...")
    heat_lines = convert_plan_to_heat_lines(plan)
    print(f"   Found {len(heat_lines)} heating lines")
    
    # Create heat lines file
    create_heat_lines_file(heat_lines, heat_lines_path)
    
    # Run simulation
    success = run_fem_simulation(
        plate=plan['plate'],
        heat_lines_file=heat_lines_path,
        heat_requirements=plan['heat_requirements'],
        output_dir=output_dir,
        sequential=True  # Sequential heating (one line at a time)
    )
    
    if not success:
        print("\n❌ Simulation failed. Check error messages above.")
        return 1
    
    # Analyze results
    analyze_results(output_dir)
    
    print(f"\n{'='*60}")
    print("✅ ALL DONE!")
    print(f"{'='*60}\n")
    print(f"Results saved to: {output_dir}")
    print(f"\nNext steps:")
    print(f"  - Review plots in {output_dir}")
    print(f"  - Open VTK files in ParaView for 3D visualization")
    print(f"  - Check summary.json for quantitative metrics")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
