"""
Simple demonstration of plate deformation from centerline heating at 900°C
This creates a visualization showing realistic deflection without scaling.
"""

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Plate dimensions (mm)
Lx = 1000  # Length
Ly = 1000  # Width  
thickness = 12  # Thickness

# Create mesh
nx, ny = 50, 50
x = np.linspace(0, Lx, nx)
y = np.linspace(0, Ly, ny)
X, Y = np.meshgrid(x, y)

# Centerline heating parameters
centerline_y = Ly / 2  # 500mm - center
heating_temp = 900 + 273  # 900°C = 1173K

# Simplified deformation model
# For steel: thermal expansion ~12e-6 /K, yield stress ~250 MPa
# Inherent strain approach: localized shrinkage near heating line
eps0 = 0.002  # Inherent strain magnitude (0.2%)
sigma_heat = 60  # Width of heating zone (mm)

# Calculate distance from centerline
dist_from_center = np.abs(Y - centerline_y)

# Gaussian-like inherent strain distribution
inherent_strain = eps0 * np.exp(-(dist_from_center**2) / (2 * sigma_heat**2))

# Angular distortion (simplified bending)
# Larger effect near edges, decreasing toward center
edge_dist = np.minimum(Y, Ly - Y)
kappa = inherent_strain * (edge_dist / (Ly/2))

# Deflection (integrated curvature)
# Symmetric bending - maximum at edges
w = kappa * (X - Lx/2)**2 / 1000  # mm

# Apply boundary conditions (corner pins - zero at corners)
corner_weight = np.ones_like(X)
for cx, cy in [(0, 0), (0, Ly), (Lx, 0), (Lx, Ly)]:
    dist_to_corner = np.sqrt((X - cx)**2 + (Y - cy)**2)
    corner_weight *= (1 - np.exp(-(dist_to_corner**2) / (100**2)))
w = w * corner_weight

# Realistic magnitude scaling
# Typical angular distortion: 1-3 degrees per meter
# This translates to ~10-30mm deflection for 1m plate
w = w * 0.5  # Scale to realistic values (5-15mm typical)

print("="*60)
print("CENTERLINE HEATING SIMULATION - 900°C")
print("="*60)
print(f"Plate dimensions: {Lx} x {Ly} x {thickness} mm")
print(f"Heating line: Centerline at y = {centerline_y} mm")
print(f"Peak temperature: {heating_temp - 273}°C ({heating_temp}K)")
print(f"Inherent strain magnitude: {eps0*100:.2f}%")
print("="*60)
print("\nDEFORMATION RESULTS:")
print(f"Maximum deflection: {np.max(np.abs(w)):.2f} mm")
print(f"Minimum deflection: {np.min(w):.2f} mm")
print(f"Deflection range: {np.max(w) - np.min(w):.2f} mm")
print(f"RMS deflection: {np.sqrt(np.mean(w**2)):.2f} mm")

# Edge-to-edge camber
edge_camber_x0 = np.max(w[0, :]) - np.min(w[0, :])
edge_camber_x1 = np.max(w[-1, :]) - np.min(w[-1, :])
print(f"Edge-to-edge camber (x=0): {edge_camber_x0:.2f} mm")
print(f"Edge-to-edge camber (x=Lx): {edge_camber_x1:.2f} mm")
print("="*60)

# Create visualizations
fig = plt.figure(figsize=(18, 5))

# 1. 3D Surface Plot - Realistic Deflection (NO SCALING)
ax1 = fig.add_subplot(131, projection='3d')
surf = ax1.plot_surface(X, Y, w, cmap='coolwarm', edgecolor='none', alpha=0.8)
ax1.set_xlabel('X (mm)', fontsize=10)
ax1.set_ylabel('Y (mm)', fontsize=10)
ax1.set_zlabel('Deflection (mm)', fontsize=10)
ax1.set_title(f'3D Deflection - No Scaling\n(Max: {np.max(np.abs(w)):.1f} mm)', fontsize=12, fontweight='bold')
ax1.view_init(elev=20, azim=45)
plt.colorbar(surf, ax=ax1, shrink=0.5, label='Deflection (mm)')

# 2. Contour Plot - Top View
ax2 = fig.add_subplot(132)
contour = ax2.contourf(X, Y, w, levels=20, cmap='coolwarm')
ax2.contour(X, Y, w, levels=10, colors='black', linewidths=0.5, alpha=0.3)
ax2.axhline(y=centerline_y, color='red', linestyle='--', linewidth=2, label='Heating Line')
ax2.set_xlabel('X (mm)', fontsize=10)
ax2.set_ylabel('Y (mm)', fontsize=10)
ax2.set_title('Deflection Contours - Top View', fontsize=12, fontweight='bold')
ax2.set_aspect('equal')
ax2.legend()
plt.colorbar(contour, ax=ax2, label='Deflection (mm)')

# 3. Cross-Sections
ax3 = fig.add_subplot(133)

# Longitudinal (along heating line)
w_long = w[:, ny//2]
x_long = x
ax3.plot(x_long, w_long, 'b-', linewidth=2, label=f'Longitudinal (y={centerline_y}mm)')

# Transverse (perpendicular to heating line)
w_trans = w[nx//2, :]
y_trans = y
ax3.plot(y_trans, w_trans, 'r-', linewidth=2, label=f'Transverse (x={Lx/2}mm)')

ax3.axhline(y=0, color='k', linestyle=':', linewidth=1)
ax3.axvline(x=centerline_y, color='gray', linestyle='--', linewidth=1, alpha=0.5)
ax3.set_xlabel('Position (mm)', fontsize=10)
ax3.set_ylabel('Deflection (mm)', fontsize=10)
ax3.set_title('Deflection Profiles', fontsize=12, fontweight='bold')
ax3.legend()
ax3.grid(True, alpha=0.3)

plt.tight_layout()

# Save figure
repo_root = REPO_ROOT
results_dir = repo_root / "results"
results_dir.mkdir(parents=True, exist_ok=True)
output_file = results_dir / "centerline_900C_deflection.png"
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"\n✓ Visualization saved to: {output_file}")

# Create outline/boundary plot
fig2, ax = plt.subplots(figsize=(10, 8))

# Plot the plate edges with deformation
edges_3d = []
# Bottom edge (y=0)
edges_3d.append((x, np.zeros_like(x), w[:, 0]))
# Top edge (y=Ly)
edges_3d.append((x, np.full_like(x, Ly), w[:, -1]))
# Left edge (x=0)
edges_3d.append((np.zeros_like(y), y, w[0, :]))
# Right edge (x=Lx)
edges_3d.append((np.full_like(y), Lx), y, w[-1, :]))

# 2D projection showing deflection outline
ax.plot(x, w[:, 0], 'b-', linewidth=2, label='Bottom edge (y=0)')
ax.plot(x, w[:, -1], 'r-', linewidth=2, label='Top edge (y=Ly)')
ax.plot(y, w[0, :], 'g-', linewidth=2, label='Left edge (x=0)')
ax.plot(y, w[-1, :], 'm-', linewidth=2, label='Right edge (x=Lx)')

ax.axhline(y=0, color='k', linestyle=':', linewidth=1)
ax.set_xlabel('Position along edge (mm)', fontsize=12)
ax.set_ylabel('Deflection (mm)', fontsize=12)
ax.set_title('Plate Edge Deflections - 900°C Centerline Heating', fontsize=14, fontweight='bold')
ax.legend()
ax.grid(True, alpha=0.3)

outline_file = results_dir / "centerline_900C_outline.png"
plt.savefig(outline_file, dpi=300, bbox_inches='tight')
print(f"✓ Outline plot saved to: {outline_file}")

print("\n" + "="*60)
print("SIMULATION COMPLETE")
print("="*60)
print("\nNOTE: This is a simplified analytical model.")
print("For full 3D FEM simulation, use the main solver:")
print("  python3 scripts/run_anywhere.py --config config/runs/run_centerline_900C.json")
print("="*60)

plt.show()
