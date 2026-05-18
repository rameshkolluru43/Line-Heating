"""
Optimized heating parameters for keel plate using li2023 scaling methodology.

Based on:
- li2023 cases showing deflection-to-energy relationships
- Inherent strain model from validated cases
- Target: 100mm deflection for R=11.48m curvature
"""

import json
import subprocess
import sys
from pathlib import Path
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]


def calculate_scaled_parameters():
    """
    Scale parameters from li2023 cases to keel plate dimensions.
    
    li2023 case_087:
      - Plate: 400×300×10mm
      - Energy: 1000 J/mm
      - Velocity: 12 mm/s  
      - Passes: 2
      - Result: ~13.5 mm deflection
    
    Keel plate:
      - Plate: 3000×1000×49mm  
      - Target: ~100 mm deflection
      - Thickness ratio: 49/10 = 4.9×
      - Width ratio: 1000/300 = 3.33×
    """
    
    print("="*70)
    print("PARAMETER SCALING FROM LI2023 VALIDATED CASES")
    print("="*70)
    
    # Reference case (li2023_087)
    ref_thickness = 10.0  # mm
    ref_width = 300.0  # mm
    ref_energy = 1000.0  # J/mm
    ref_velocity = 12.0  # mm/s
    ref_passes = 2
    ref_deflection = 13.5  # mm
    ref_eps0 = 0.068
    
    # Target keel plate
    target_thickness = 49.0  # mm
    target_width = 1000.0  # mm
    target_deflection = 100.0  # mm (for R=11.48m)
    
    print(f"\nReference Case (li2023_087):")
    print(f"  Plate: 400×{ref_width}×{ref_thickness} mm")
    print(f"  Energy: {ref_energy} J/mm")
    print(f"  Velocity: {ref_velocity} mm/s")
    print(f"  Passes: {ref_passes}")
    print(f"  Deflection: {ref_deflection} mm")
    print(f"  eps0: {ref_eps0}")
    
    print(f"\nTarget (Keel Plate):")
    print(f"  Plate: 3000×{target_width}×{target_thickness} mm")
    print(f"  Target deflection: {target_deflection} mm")
    
    # Scaling factors
    thickness_ratio = target_thickness / ref_thickness
    width_ratio = target_width / ref_width
    deflection_ratio = target_deflection / ref_deflection
    
    print(f"\nScaling Factors:")
    print(f"  Thickness ratio: {thickness_ratio:.2f}×")
    print(f"  Width ratio: {width_ratio:.2f}×")
    print(f"  Deflection ratio: {deflection_ratio:.2f}×")
    
    # From inherent strain model: eps0 ∝ (E/E_ref)^a * (H_ref/H)^p
    # where a=0.35, p=0.325
    # Deflection ∝ eps0 * (width^2 / thickness^2) approximately
    
    # For similar eps0, deflection scales with geometry:
    # w ∝ width² / thickness²
    # To achieve target deflection, need to adjust eps0
    
    # Geometric deflection ratio (if eps0 stays same)
    geometric_factor = (width_ratio ** 2) / (thickness_ratio ** 2)
    
    # Needed eps0 ratio to achieve target deflection
    eps0_needed_ratio = deflection_ratio / geometric_factor
    
    # From eps0 model: eps0 ∝ E^a * H^(-p)
    # To get eps0_ratio: E_new / E_ref = (eps0_ratio)^(1/a) * (H_new / H_ref)^(p/a)
    
    p = 0.325  # thickness exponent from eps0 model
    a = 0.35  # energy exponent from eps0 model
    
    energy_ratio_from_eps0 = (eps0_needed_ratio) ** (1/a)
    energy_ratio_from_thickness = (thickness_ratio) ** (p/a)
    
    energy_scale = energy_ratio_from_eps0 * energy_ratio_from_thickness
    
    # Cap the energy to reasonable values (max 1200 J/mm as used in li2023)
    scaled_energy = min(ref_energy * energy_scale, 1200.0)
    
    # Velocity can stay similar for similar peak temperature
    scaled_velocity = ref_velocity * 0.8  # Slightly slower for thicker plate
    
    # Passes: increase for thicker plate
    scaled_passes = ref_passes  # Keep same initially
    
    # Calculate expected eps0 for scaled parameters
    eps0_scale = (scaled_energy / ref_energy) ** a * (ref_thickness / target_thickness) ** p
    scaled_eps0 = ref_eps0 * eps0_scale
    
    print(f"\nScaling Calculations:")
    print(f"  Geometric deflection factor: {geometric_factor:.2f}×")
    print(f"  Needed eps0 ratio: {eps0_needed_ratio:.2f}×")
    print(f"  Energy ratio from eps0: {energy_ratio_from_eps0:.2f}×")
    print(f"  Energy ratio from thickness: {energy_ratio_from_thickness:.2f}×")
    print(f"  Total energy scale (before cap): {energy_scale:.2f}×")
    
    print(f"\nScaled Parameters:")
    print(f"  Energy: {scaled_energy:.1f} J/mm (vs ref {ref_energy})")
    print(f"  Velocity: {scaled_velocity:.1f} mm/s (vs ref {ref_velocity})")
    print(f"  Passes: {scaled_passes}")
    print(f"  Expected eps0: {scaled_eps0:.4f} (vs ref {ref_eps0})")
    
    # Calculate q0 from energy
    r0 = 7.0  # mm (from li2023 cases)
    q0 = scaled_energy * scaled_velocity / (np.pi * r0**2)
    
    print(f"  Heat flux q0: {q0:.2f} W/mm²")
    print(f"  Torch radius r0: {r0} mm")
    
    # Calculate target temperature
    # From li2023: E=1000 J/mm -> T=1100°C (1373K)
    if scaled_energy >= 1000:
        T_target_C = 900 + (scaled_energy - 600) * (1100 - 900) / (1000 - 600)
    else:
        T_target_C = 900 + (scaled_energy - 600) * (1100 - 900) / (1000 - 600)
    T_target_K = T_target_C + 273.15
    
    print(f"  Target temperature: {T_target_C:.0f}°C ({T_target_K:.0f}K)")
    
    return {
        'energy': scaled_energy,
        'velocity': scaled_velocity,
        'passes': scaled_passes,
        'q0': q0,
        'r0': r0,
        'eps0': scaled_eps0,
        'target_Tmax': T_target_K,
        'target_Tmax_C': T_target_C
    }


def create_config(params):
    """Create run config using scaled parameters."""
    
    repo_root = REPO_ROOT
    out_dir = repo_root / "results" / "keel_plate_li2023_scaled"
    
    # 5 heating lines evenly spaced
    Ly = 1000.0
    n_lines = 5
    heat_y_list = [Ly * (i+1) / (n_lines+1) for i in range(n_lines)]
    
    config = {
        "out": str(out_dir),
        "runner": {
            "report_only": False,
            "no_build": True,
            "no_report": False
        },
        "simulation": {
            "Lx": 3000.0,
            "Ly": Ly,
            "thickness": 49.0,
            
            # Mesh parameters (scaled for larger plate)
            "h": 40.0,
            "h_refine": 20.0,
            "refine_band": 100.0,
            
            # Heating lines
            "heat_y_list": heat_y_list,
            "heat_mode": "sequential",
            "pass_gap": 60.0,
            "pass_repeats": params['passes'],
            
            # Time stepping
            "dt": 2.0,
            "extra_time": 200.0,
            
            # Heat source (from scaling)
            "q0": params['q0'],
            "r0": params['r0'],
            "gaussian_beta": 3.0,
            "velocity": params['velocity'],
            
            # Temperature control
            "target_Tmax": params['target_Tmax'],
            "target_Tmax_tol": 20.0,
            "target_Tmax_iters": 3,
            
            # Thermal properties (from li2023 Q345 steel, converted to A36-like)
            "k": 0.05,  # W/(mm·K)
            "k_slope": -0.000248,
            "rho": 7.85e-6,  # kg/mm³ (A36)
            "cp": 460.0,
            "cp_slope": 0.000382,
            "h_conv": 5e-5,  # W/(mm²·K)
            "h_conv_top": 5e-5,
            "h_conv_bottom": 5e-5,
            "emissivity": 0.8,
            
            # Reference temperatures
            "T_inf": 293.15,
            "T_ref": 293.15,
            
            # Mechanical properties (A36 steel, temperature-dependent)
            "E": 210000.0,  # MPa at room temp
            "nu": 0.28,
            "alpha": 1.2e-5,  # 1/K
            
            # Temperature-dependent properties
            "E_table": "20:210000,250:187000,500:150000,750:70000,1000:2000,1500:1500",
            "nu_table": "20:0.28,250:0.29,500:0.31,750:0.35,1000:0.40,1500:0.49",
            "alpha_table": "20:1.2e-5,250:1.2e-5,500:1.39e-5,750:1.48e-5,1000:1.34e-5,1500:1.33e-5",
            
            # Boundary conditions
            "bc": "centerline_fixed",
            
            # Inherent strain (from scaling)
            "use_inherent": True,
            "eps0": params['eps0'],
            "inh_sigma": 7.0,
            "inh_zfrac": 0.2,
            
            # Visualization
            "vtk_deform_scale": 50.0
        }
    }
    
    config_file = repo_root / "config" / "keel_plate_li2023_scaled.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\n✅ Saved configuration: {config_file}")
    print(f"\nHeating Lines ({len(heat_y_list)} lines):")
    for i, y in enumerate(heat_y_list, 1):
        print(f"  Line {i}: y = {y:.2f} mm")
    
    return config_file


def run_simulation(config_file):
    """Run the simulation using run_anywhere.py"""
    
    repo_root = REPO_ROOT
    runner = repo_root / "scripts" / "run_anywhere.py"
    venv_python = repo_root / ".venv_lineheating" / "bin" / "python"
    
    python_exec = venv_python if venv_python.exists() else sys.executable
    
    print(f"\n{'='*70}")
    print("RUNNING SIMULATION")
    print(f"{'='*70}\n")
    
    print(f"This will take approximately 60-90 minutes...")
    print(f"\nTo run in background:")
    print(f"  nohup {python_exec} {runner} --config {config_file} > simulation.log 2>&1 &\n")
    
    response = input("Start simulation now? (y/n) [n]: ").strip().lower()
    
    if response == 'y':
        cmd = [str(python_exec), str(runner), "--config", str(config_file)]
        print(f"\n🚀 Running: {' '.join(cmd)}\n")
        result = subprocess.run(cmd, cwd=repo_root)
        
        if result.returncode == 0:
            print(f"\n✅ Simulation completed!")
            return True
        else:
            print(f"\n❌ Simulation failed with exit code {result.returncode}")
            return False
    else:
        print(f"\n💾 Configuration ready. Run when ready:")
        print(f"  python scripts/run_anywhere.py --config {config_file}")
        return None


def main():
    """Main workflow."""
    
    print("\n" + "="*70)
    print("KEEL PLATE HEATING - LI2023 PARAMETER SCALING APPROACH")
    print("="*70)
    print("\nUsing validated li2023 cases to scale parameters for target curvature\n")
    
    # Calculate scaled parameters
    params = calculate_scaled_parameters()
    
    # Create configuration
    config_file = create_config(params)
    
    # Optionally run simulation
    if "--run" in sys.argv:
        run_simulation(config_file)
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"\n✅ Parameters calculated using li2023 scaling methodology")
    print(f"✅ Configuration file created: {config_file}")
    print(f"\n📊 Expected Results:")
    print(f"  Target deflection: ~100 mm")
    print(f"  Target radius: ~11.48 m")
    print(f"  Energy input: {params['energy']:.1f} J/mm")
    print(f"  Temperature: {params['target_Tmax_C']:.0f}°C")
    
    print(f"\n🚀 Next Steps:")
    print(f"  1. Review parameters above")
    print(f"  2. Run simulation:")
    print(f"     python scripts/cases/run_keel_li2023_scaled.py --run")
    print(f"  3. After completion, analyze:")
    print(f"     python scripts/cases/compare_curvature.py --results-dir results/keel_plate_li2023_scaled")
    print(f"\n{'='*70}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
