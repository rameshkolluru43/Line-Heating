# Quick Start Guide - Two Main Use Cases

## Use Case A: Forward Problem - Validate Curvature Profile

**Goal:** Given torch temperature (900K), predict the resulting curvature.

### Steps:

1. **Copy the forward example config:**
   ```bash
   # Windows
   copy config_forward_example.json my_forward_config.json
   
   # macOS/Linux
   cp config_forward_example.json my_forward_config.json
   ```

2. **Edit key parameters** (or keep defaults):
   ```json
   {
     "Lx": 1000,           // Plate length (mm)
     "Ly": 1000,           // Plate width (mm)
     "thickness": 12,      // Plate thickness (mm)
     "heat_y_list": [500], // Line position (centerline)
     "target_Tmax": 900,   // Torch temperature (K)
     "velocity": 10        // Torch speed (mm/s)
   }
   ```

3. **Run simulation:**
   ```bash
   # Windows
   python scripts\run_anywhere.py --config my_forward_config.json
   
   # macOS/Linux
   python3 scripts/run_anywhere.py --config my_forward_config.json
   ```

4. **View results:**
   - Open `results/forward_900K_validation/report.pdf`
   - Load `results/forward_900K_validation/results_deformed.vtk` in ParaView
   - Check `results/forward_900K_validation/summary.json` for metrics

5. **Validate curvature:**
   ```python
   import json
   with open('results/forward_900K_validation/summary.json') as f:
       data = json.load(f)
       print(f"Maximum deflection: {data.get('max_deflection_mm', 'N/A')} mm")
       print(f"Edge-to-edge camber: {data.get('camber_mm', 'N/A')} mm")
   ```

---

## Use Case B: Inverse Problem - Optimize Heating Pattern

**Goal:** Find the heating pattern that achieves a target curvature on a given plate.

### Steps:

1. **Copy the inverse example config:**
   ```bash
   # Windows
   copy config_inverse_example.json my_inverse_config.json
   
   # macOS/Linux
   cp config_inverse_example.json my_inverse_config.json
   ```

2. **Define your plate and initial heating pattern:**
   ```json
   {
     "Lx": 2000,                    // Your plate length
     "Ly": 1500,                    // Your plate width
     "thickness": 15,               // Your plate thickness
     "heat_y_list": [375, 750, 1125], // Initial guess for line positions
     "target_Tmax": 950             // Starting temperature
   }
   ```

3. **Run first iteration:**
   ```bash
   python scripts\run_anywhere.py --config my_inverse_config.json
   ```

4. **Check results:**
   ```bash
   # View deflection in ParaView
   paraview results/inverse_curvature_optimization/results_deformed.vtk
   
   # Check summary
   cat results/inverse_curvature_optimization/summary.json
   ```

5. **Adjust parameters based on results:**

   **If curvature is too small:**
   ```json
   {
     "eps0": 0.003,           // Increase from 0.0025
     "target_Tmax": 1000,     // Increase from 950
     "velocity": 10           // Decrease from 12 (slower = more heat)
   }
   ```

   **If curvature is too large:**
   ```json
   {
     "eps0": 0.002,           // Decrease from 0.0025
     "target_Tmax": 900,      // Decrease from 950
     "velocity": 15           // Increase from 12 (faster = less heat)
   }
   ```

   **If curvature is uneven:**
   ```json
   {
     "heat_y_list": [400, 800, 1200],  // Adjust line spacing
     "pass_gap": 150                    // Increase gap between passes
   }
   ```

6. **Re-run and iterate:**
   ```bash
   python scripts\run_anywhere.py --config my_inverse_config.json
   ```

7. **Compare iterations:**
   ```python
   import json
   import numpy as np
   
   # Load results from multiple runs
   with open('results/run1/summary.json') as f:
       run1 = json.load(f)
   with open('results/run2/summary.json') as f:
       run2 = json.load(f)
   
   # Compare key metrics
   print(f"Run 1 max deflection: {run1.get('max_deflection_mm')} mm")
   print(f"Run 2 max deflection: {run2.get('max_deflection_mm')} mm")
   ```

---

## Key Parameters to Adjust

### For Both Use Cases:

| Parameter | Description | Typical Range | Effect |
|-----------|-------------|---------------|--------|
| `target_Tmax` | Torch temperature (K) | 850-1050 | Higher → more curvature |
| `velocity` | Torch speed (mm/s) | 8-20 | Slower → more heat input |
| `r0` | Torch radius (mm) | 20-40 | Larger → wider heating zone |
| `eps0` | Inherent strain | 0.001-0.004 | Higher → more permanent bending |
| `thickness` | Plate thickness (mm) | 8-25 | Thicker → less curvature |

### For Inverse Problem Only:

| Parameter | Description | How to Adjust |
|-----------|-------------|---------------|
| `heat_y_list` | Line positions | Spread evenly for uniform curvature |
| `pass_gap` | Time between passes (s) | Increase for cooler intermediate passes |
| `inh_sigma` | Inherent strain width (mm) | Increase for wider deformation zone |
| `quench_h_conv` | Quenching intensity | Higher → stronger cooling effect |

---

## Validation Checklist

### For Forward Problem (Use Case A):

- [ ] Temperature peak reaches `target_Tmax` ± tolerance
- [ ] Deflection pattern is symmetric (for centerline pass)
- [ ] Curvature values match expected physics
- [ ] Results are mesh-independent (try coarser/finer mesh)
- [ ] Compare with experimental data (if available)

### For Inverse Problem (Use Case B):

- [ ] Achieved curvature is within tolerance of target
- [ ] Heating pattern is manufacturable
- [ ] Temperature stays below material limits
- [ ] Process time is acceptable
- [ ] Multiple passes don't interfere (check `pass_gap`)

---

## Common Issues and Solutions

### Issue: Simulation too slow

**Solution:**
```json
{
  "h": 60,              // Increase from 40 (coarser mesh)
  "h_refine": 15,       // Increase from 10
  "dt": 10,             // Increase from 5 (larger time steps)
  "extra_time": 300     // Decrease from 600
}
```

### Issue: Curvature too small

**Solution:**
```json
{
  "use_inherent": true,    // Enable if false
  "eps0": 0.003,           // Increase
  "target_Tmax": 1000,     // Increase
  "velocity": 8            // Decrease (slower)
}
```

### Issue: Results not converging (inverse problem)

**Solution:**
1. Start with simpler pattern (single line)
2. Use wider tolerance: `"target_Tmax_tol": 50`
3. Increase iterations: `"target_Tmax_iters": 10`
4. Check material properties in code

### Issue: Out of memory

**Solution:**
```json
{
  "Lx": 800,            // Reduce plate size for testing
  "Ly": 800,
  "h": 60,              // Coarser mesh
  "refine_band": 120    // Smaller refinement zone
}
```

---

## Next Steps

### After Forward Validation:

1. **Parameter sensitivity study:**
   - Vary `target_Tmax` (850, 900, 950, 1000 K)
   - Vary `velocity` (8, 10, 12, 15 mm/s)
   - Compare resulting curvatures

2. **Multi-pass analysis:**
   ```json
   "heat_y_list": [250, 500, 750]
   ```

3. **Different boundary conditions:**
   ```json
   "bc": "clamped"  // or "corner_pins", "free_edges"
   ```

### After Inverse Optimization:

1. **Verify with finer mesh:**
   ```json
   "h": 30,
   "h_refine": 7
   ```

2. **Test robustness:**
   - Add ±5% variation to `target_Tmax`
   - Add ±10% variation to `velocity`
   - Check if curvature stays acceptable

3. **Generate manufacturing instructions:**
   - Extract line positions from `heat_y_list`
   - Document `target_Tmax` and `velocity`
   - Create process card with timings

---

## Visualization Tips

### ParaView:

1. Load `results_deformed.vtk`
2. Apply "Warp By Vector" filter (scale: 1-10)
3. Color by "Displacement" magnitude
4. Use "Clip" to see internal temperature

### Python Analysis:

```python
import numpy as np
import matplotlib.pyplot as plt

# Load data
nodes = np.load('results/your_run/nodes.npy')
displacement = np.load('results/your_run/displacement.npy')

# Plot deflection along centerline
x = nodes[:, 0]
w = displacement[:, 2]
plt.plot(x, w)
plt.xlabel('Position (mm)')
plt.ylabel('Deflection (mm)')
plt.title('Deflection Profile')
plt.show()
```

---

## Getting Help

- **Use Cases Guide:** [USE-CASES.md](USE-CASES.md)
- **Setup Issues:** [SETUP.md](SETUP.md)
- **Windows Compiler:** [WINDOWS-VS-TROUBLESHOOTING.md](WINDOWS-VS-TROUBLESHOOTING.md)
- **Offline Install:** [OFFLINE-SETUP.md](OFFLINE-SETUP.md)
- **Example Scripts:** `python_prototype/examples/`
- **Main Solver:** `thermo_fem/python/run_coupled_3d.py`
