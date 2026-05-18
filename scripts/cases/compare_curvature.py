"""
Compare curvature from IGES file with simulation results.

This script:
1. Analyzes NURBS surface curvature from IGES file
2. Calculates curvature from simulation deflection
3. Compares the two and generates report
"""

import numpy as np
import json
from pathlib import Path
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[2]


def analyze_iges_curvature(iges_path: Path):
    """Extract curvature information from IGES NURBS surface."""
    
    print(f"\n{'='*60}")
    print("📐 IGES FILE CURVATURE ANALYSIS")
    print(f"{'='*60}\n")
    
    # The IGES file contains NURBS surface (Entity 128)
    # For a ship keel plate, we need to estimate curvature from the surface data
    
    # From the IGES file analysis, we have coordinate data
    # Entity 128 is a NURBS surface with control points defining curvature
    
    with open(iges_path, 'r') as f:
        content = f.read()
    
    # Extract parameter section data (lines with P suffix)
    import re
    param_lines = [line for line in content.split('\n') if 'P' in line[-10:]]
    
    # Extract coordinate triplets (x, y, z) from NURBS surface
    coords = []
    for line in param_lines:
        # Find floating point numbers
        matches = re.findall(r'(-?\d+\.?\d*(?:E[+-]?\d+)?)', line)
        for match in matches:
            try:
                val = float(match)
                if abs(val) > 1.0:  # Filter out small parameters
                    coords.append(val)
            except:
                pass
    
    coords = np.array(coords)
    
    # Approximate the surface as having coordinates in groups
    # For a plate surface, z-coordinates represent the height/curvature
    likely_z = coords[(coords > 700) & (coords < 800)]  # Z-coordinates near 750mm
    likely_y = coords[(coords > 100) & (coords < 70000)]  # Y-coordinates
    
    if len(likely_z) > 10:
        # Calculate variation in Z (indicates curvature)
        z_range = np.max(likely_z) - np.min(likely_z)
        z_mean = np.mean(likely_z)
        z_std = np.std(likely_z)
        
        print("IGES Surface Geometry:")
        print(f"  Z-coordinate range: {z_range:.2f} mm")
        print(f"  Z-coordinate mean:  {z_mean:.2f} mm")
        print(f"  Z variation (std):  {z_std:.2f} mm")
        
        # For a NURBS surface with this variation, estimate radius of curvature
        # Using the formula: R ≈ L² / (8 * deflection)
        # Assuming characteristic length from the plate dimensions
        L_characteristic = 3000.0  # mm (plate length)
        
        # Estimate curvature from Z variation
        if z_range > 1.0:
            # Approximate radius of curvature
            R_iges = (L_characteristic ** 2) / (8 * z_range)
            curvature_iges = 1.0 / R_iges  # 1/mm
            
            print(f"\nEstimated IGES Curvature:")
            print(f"  Characteristic length: {L_characteristic:.0f} mm")
            print(f"  Deflection range:      {z_range:.2f} mm")
            print(f"  Radius of curvature:   {R_iges:.0f} mm ({R_iges/1000:.2f} m)")
            print(f"  Curvature (1/R):       {curvature_iges:.6f} 1/mm ({curvature_iges*1000:.6f} 1/m)")
        else:
            print(f"\nNote: IGES surface appears nearly flat (Z variation < 1mm)")
            R_iges = np.inf
            curvature_iges = 0.0
    else:
        print("⚠️  Could not extract sufficient Z-coordinates from IGES")
        R_iges = None
        curvature_iges = None
    
    return {
        'radius_mm': R_iges,
        'curvature_per_mm': curvature_iges,
        'z_range': z_range if 'z_range' in locals() else None,
        'z_mean': z_mean if 'z_mean' in locals() else None
    }


def analyze_simulation_curvature(results_dir: Path):
    """Calculate curvature from simulation deflection results."""
    
    print(f"\n{'='*60}")
    print("📊 SIMULATION CURVATURE ANALYSIS")
    print(f"{'='*60}\n")
    
    # Load summary
    summary_file = results_dir / "summary.json"
    with open(summary_file, 'r') as f:
        summary = json.load(f)
    
    print("Simulation Results:")
    print(f"  Peak Temperature:  {summary.get('T_max_K', 0):.1f} K ({summary.get('T_max_K', 0)-273:.1f}°C)")
    print(f"  Max Deflection:    {summary.get('max_deflection_mm', 0):.3f} mm")
    print(f"  Min Deflection:    {summary.get('min_deflection_mm', 0):.3f} mm")
    print(f"  RMS Deflection:    {summary.get('rms_deflection_mm', 0):.3f} mm")
    
    # Load displacement data
    disp_file = results_dir / "displacement.npy"
    nodes_file = results_dir / "nodes.npy"
    
    if disp_file.exists() and nodes_file.exists():
        displacement = np.load(disp_file)  # (n_nodes, 3) - [ux, uy, uz]
        nodes = np.load(nodes_file)  # (n_nodes, 3) - [x, y, z]
        
        # Deflection in z-direction
        w = displacement[:, 2]
        x_coords = nodes[:, 0]
        y_coords = nodes[:, 1]
        
        print(f"\nDeflection Statistics:")
        print(f"  Number of nodes:   {len(w):,}")
        print(f"  Max deflection:    {np.max(w):.3f} mm")
        print(f"  Min deflection:    {np.min(w):.3f} mm")
        print(f"  Deflection range:  {np.max(w) - np.min(w):.3f} mm")
        print(f"  Mean deflection:   {np.mean(w):.3f} mm")
        print(f"  Std deflection:    {np.std(w):.3f} mm")
        
        # Calculate curvature along different directions
        
        # 1. Transverse curvature (across width, Y-direction)
        # Find nodes at mid-length (x ≈ Lx/2)
        Lx = np.max(x_coords)
        Ly = np.max(y_coords)
        
        mid_x = Lx / 2.0
        tol_x = 100.0  # mm tolerance
        
        midline_mask = np.abs(x_coords - mid_x) < tol_x
        midline_y = y_coords[midline_mask]
        midline_w = w[midline_mask]
        
        # Sort by y
        sort_idx = np.argsort(midline_y)
        midline_y_sorted = midline_y[sort_idx]
        midline_w_sorted = midline_w[sort_idx]
        
        if len(midline_w_sorted) > 10:
            # Fit parabola to transverse deflection: w = a*y^2 + b*y + c
            # Curvature κ = 2*a
            
            # Center the y-coordinates
            y_centered = midline_y_sorted - Ly/2.0
            
            # Polynomial fit
            coeffs = np.polyfit(y_centered, midline_w_sorted, 2)
            a, b, c = coeffs
            
            # Curvature
            kappa_transverse = 2 * a  # 1/mm
            
            # Radius of curvature
            if abs(kappa_transverse) > 1e-10:
                R_transverse = 1.0 / abs(kappa_transverse)
            else:
                R_transverse = np.inf
            
            # Deflection at edges vs center
            w_center = c
            w_edges = np.polyval(coeffs, [-Ly/2.0, Ly/2.0])
            edge_to_edge_camber = np.max(w_edges) - np.min(w_edges)
            
            print(f"\nTransverse Curvature (Y-direction, at mid-length):")
            print(f"  Sample points:     {len(midline_w_sorted)}")
            print(f"  Fitted curvature:  κ = {kappa_transverse:.6f} 1/mm ({kappa_transverse*1000:.6f} 1/m)")
            print(f"  Radius of curv.:   R = {R_transverse:.0f} mm ({R_transverse/1000:.2f} m)")
            print(f"  Center deflection: {w_center:.3f} mm")
            print(f"  Edge-to-edge:      {edge_to_edge_camber:.3f} mm")
        else:
            R_transverse = None
            kappa_transverse = None
            print(f"\n⚠️  Insufficient midline points for transverse curvature")
        
        # 2. Longitudinal curvature (along length, X-direction)
        # Find nodes at mid-width (y ≈ Ly/2)
        mid_y = Ly / 2.0
        tol_y = 100.0
        
        centerline_mask = np.abs(y_coords - mid_y) < tol_y
        centerline_x = x_coords[centerline_mask]
        centerline_w = w[centerline_mask]
        
        sort_idx = np.argsort(centerline_x)
        centerline_x_sorted = centerline_x[sort_idx]
        centerline_w_sorted = centerline_w[sort_idx]
        
        if len(centerline_w_sorted) > 10:
            x_centered = centerline_x_sorted - Lx/2.0
            coeffs_long = np.polyfit(x_centered, centerline_w_sorted, 2)
            a_long, b_long, c_long = coeffs_long
            
            kappa_longitudinal = 2 * a_long
            
            if abs(kappa_longitudinal) > 1e-10:
                R_longitudinal = 1.0 / abs(kappa_longitudinal)
            else:
                R_longitudinal = np.inf
            
            print(f"\nLongitudinal Curvature (X-direction, at mid-width):")
            print(f"  Sample points:     {len(centerline_w_sorted)}")
            print(f"  Fitted curvature:  κ = {kappa_longitudinal:.6f} 1/mm ({kappa_longitudinal*1000:.6f} 1/m)")
            print(f"  Radius of curv.:   R = {R_longitudinal:.0f} mm ({R_longitudinal/1000:.2f} m)")
        else:
            R_longitudinal = None
            kappa_longitudinal = None
            print(f"\n⚠️  Insufficient centerline points for longitudinal curvature")
        
        # 3. Average curvature estimate
        deflection_range = np.max(w) - np.min(w)
        R_avg = (Ly ** 2) / (8 * deflection_range) if deflection_range > 0 else np.inf
        kappa_avg = 1.0 / R_avg if R_avg != np.inf else 0.0
        
        print(f"\nAverage Curvature (from deflection range):")
        print(f"  Deflection range:  {deflection_range:.3f} mm")
        print(f"  Characteristic L:  {Ly:.0f} mm (plate width)")
        print(f"  Radius estimate:   R = {R_avg:.0f} mm ({R_avg/1000:.2f} m)")
        print(f"  Curvature:         κ = {kappa_avg:.6f} 1/mm ({kappa_avg*1000:.6f} 1/m)")
        
        return {
            'R_transverse_mm': R_transverse,
            'kappa_transverse_per_mm': kappa_transverse,
            'R_longitudinal_mm': R_longitudinal,
            'kappa_longitudinal_per_mm': kappa_longitudinal,
            'R_avg_mm': R_avg,
            'kappa_avg_per_mm': kappa_avg,
            'deflection_range_mm': deflection_range,
            'max_deflection_mm': np.max(w),
            'min_deflection_mm': np.min(w)
        }
    else:
        print("⚠️  Displacement/nodes files not found")
        return None


def plot_curvature_comparison(results_dir: Path, sim_results: dict):
    """Create visualization of curvature."""
    
    # Load data
    displacement = np.load(results_dir / "displacement.npy")
    nodes = np.load(results_dir / "nodes.npy")
    
    w = displacement[:, 2]
    x_coords = nodes[:, 0]
    y_coords = nodes[:, 1]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 1. Deflection contour
    ax = axes[0, 0]
    scatter = ax.scatter(x_coords, y_coords, c=w, cmap='RdBu_r', s=1, vmin=np.min(w), vmax=np.max(w))
    ax.set_xlabel('X (mm)')
    ax.set_ylabel('Y (mm)')
    ax.set_title('Deflection Field (Z-direction)')
    ax.set_aspect('equal')
    plt.colorbar(scatter, ax=ax, label='Deflection (mm)')
    
    # 2. Transverse profile (mid-length)
    ax = axes[0, 1]
    Lx = np.max(x_coords)
    Ly = np.max(y_coords)
    mid_x = Lx / 2.0
    midline_mask = np.abs(x_coords - mid_x) < 100.0
    midline_y = y_coords[midline_mask]
    midline_w = w[midline_mask]
    sort_idx = np.argsort(midline_y)
    ax.plot(midline_y[sort_idx], midline_w[sort_idx], 'b.-', label='Simulation')
    
    # Fit curve
    y_centered = midline_y[sort_idx] - Ly/2.0
    coeffs = np.polyfit(y_centered, midline_w[sort_idx], 2)
    y_fit = np.linspace(-Ly/2.0, Ly/2.0, 100)
    w_fit = np.polyval(coeffs, y_fit)
    ax.plot(y_fit + Ly/2.0, w_fit, 'r--', label=f'Fitted (R={sim_results["R_transverse_mm"]/1000:.1f}m)')
    
    ax.set_xlabel('Y Position (mm)')
    ax.set_ylabel('Deflection (mm)')
    ax.set_title(f'Transverse Profile at X={mid_x:.0f}mm')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 3. Longitudinal profile (mid-width)
    ax = axes[1, 0]
    mid_y = Ly / 2.0
    centerline_mask = np.abs(y_coords - mid_y) < 100.0
    centerline_x = x_coords[centerline_mask]
    centerline_w = w[centerline_mask]
    sort_idx = np.argsort(centerline_x)
    ax.plot(centerline_x[sort_idx], centerline_w[sort_idx], 'b.-', label='Simulation')
    
    # Fit curve
    x_centered = centerline_x[sort_idx] - Lx/2.0
    coeffs_long = np.polyfit(x_centered, centerline_w[sort_idx], 2)
    x_fit = np.linspace(-Lx/2.0, Lx/2.0, 100)
    w_fit_long = np.polyval(coeffs_long, x_fit)
    ax.plot(x_fit + Lx/2.0, w_fit_long, 'r--', label=f'Fitted (R={sim_results["R_longitudinal_mm"]/1000:.1f}m)')
    
    ax.set_xlabel('X Position (mm)')
    ax.set_ylabel('Deflection (mm)')
    ax.set_title(f'Longitudinal Profile at Y={mid_y:.0f}mm')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 4. Curvature summary
    ax = axes[1, 1]
    ax.axis('off')
    
    summary_text = f"""
SIMULATION CURVATURE RESULTS

Transverse (Y-direction):
  Radius: {sim_results['R_transverse_mm']/1000:.2f} m
  Curvature: {sim_results['kappa_transverse_per_mm']*1000:.4f} 1/m
  
Longitudinal (X-direction):
  Radius: {sim_results['R_longitudinal_mm']/1000:.2f} m
  Curvature: {sim_results['kappa_longitudinal_per_mm']*1000:.4f} 1/m
  
Average Estimate:
  Radius: {sim_results['R_avg_mm']/1000:.2f} m
  Curvature: {sim_results['kappa_avg_per_mm']*1000:.4f} 1/m
  
Deflection Statistics:
  Maximum: {sim_results['max_deflection_mm']:.2f} mm
  Minimum: {sim_results['min_deflection_mm']:.2f} mm
  Range: {sim_results['deflection_range_mm']:.2f} mm
"""
    
    ax.text(0.1, 0.5, summary_text, fontsize=10, family='monospace',
            verticalalignment='center', transform=ax.transAxes)
    
    plt.tight_layout()
    
    output_file = results_dir / "curvature_analysis.png"
    plt.savefig(output_file, dpi=150, bbox_inches='tight')
    print(f"\n✅ Saved curvature analysis plot: {output_file}")
    
    return output_file


def main():
    """Main comparison function."""
    
    import sys
    
    repo_root = REPO_ROOT
    iges_file = repo_root / "IGESFiles" / "keel plate 0-5.igs"
    
    # Allow custom results directory from command line
    if "--results-dir" in sys.argv:
        idx = sys.argv.index("--results-dir")
        if idx + 1 < len(sys.argv):
            results_dir = Path(sys.argv[idx + 1])
        else:
            results_dir = repo_root / "results" / "keel_plate_fast_parallel"
    else:
        results_dir = repo_root / "results" / "keel_plate_fast_parallel"

    if not results_dir.is_absolute():
        results_dir = repo_root / results_dir
    
    print(f"\n{'='*60}")
    print("🔬 CURVATURE COMPARISON: IGES vs SIMULATION")
    print(f"{'='*60}\n")
    
    # Analyze IGES
    iges_results = analyze_iges_curvature(iges_file)
    
    # Analyze simulation
    sim_results = analyze_simulation_curvature(results_dir)
    
    if iges_results and sim_results:
        print(f"\n{'='*60}")
        print("📊 COMPARISON SUMMARY")
        print(f"{'='*60}\n")
        
        print("IGES File (Design Intent):")
        if iges_results['radius_mm'] and iges_results['radius_mm'] != np.inf:
            print(f"  Estimated Radius:    {iges_results['radius_mm']:.0f} mm ({iges_results['radius_mm']/1000:.2f} m)")
            print(f"  Estimated Curvature: {iges_results['curvature_per_mm']*1000:.4f} 1/m")
        else:
            print(f"  Surface appears nearly flat or curvature not determinable")
        
        print(f"\nSimulation Results (Achieved):")
        print(f"  Transverse Radius:    {sim_results['R_transverse_mm']:.0f} mm ({sim_results['R_transverse_mm']/1000:.2f} m)")
        print(f"  Transverse Curvature: {sim_results['kappa_transverse_per_mm']*1000:.4f} 1/m")
        print(f"  Longitud. Radius:     {sim_results['R_longitudinal_mm']:.0f} mm ({sim_results['R_longitudinal_mm']/1000:.2f} m)")
        print(f"  Longitud. Curvature:  {sim_results['kappa_longitudinal_per_mm']*1000:.4f} 1/m")
        
        # Generate visualization
        plot_file = plot_curvature_comparison(results_dir, sim_results)
        
        # Save comparison report
        comparison = {
            'iges_analysis': iges_results,
            'simulation_results': sim_results,
            'units': {
                'radius': 'mm',
                'curvature': '1/mm',
                'deflection': 'mm'
            }
        }
        
        report_file = results_dir / "curvature_comparison.json"
        with open(report_file, 'w') as f:
            json.dump(comparison, f, indent=2)
        
        print(f"\n✅ Saved comparison report: {report_file}")
        print(f"✅ Saved curvature plot: {plot_file}")
        
        print(f"\n{'='*60}")
        print("✅ ANALYSIS COMPLETE")
        print(f"{'='*60}\n")
        
        return 0
    else:
        print("\n❌ Could not complete comparison")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
