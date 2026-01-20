# Project Use Cases

This project simulates **line heating** for ship plate bending using 3D coupled thermo-mechanical finite element analysis. It supports two primary workflows:

---

## Use Case A: Forward Problem - Validate Curvature from Given Temperature

**Objective:** Given a line heating process with a specific torch temperature (e.g., 900K), simulate the thermal and mechanical response to predict and validate the resulting curvature profile.

### What You Provide:
- Plate dimensions (`Lx`, `Ly`, `thickness`)
- Torch temperature (`target_Tmax`: 900K)
- Heating parameters (velocity, torch radius, etc.)
- Heating line positions (`heat_y_list`) or arbitrary segments (`heat_lines`)

### What You Get:
- Temperature distribution over time
- Deflection/curvature profile
- Validation of predicted vs expected curvature
- VTK files for visualization in ParaView
- Detailed PDF report with plots

### Example Configuration:

**Option A: Parallel lines (heat_y_list)**

```json
{
  "out": "results/forward_validation",
  "simulation": {
    "Lx": 1000,
    "Ly": 1000,
    "thickness": 12,
    "heat_y_list": [250, 500, 750],
    "target_Tmax": 900,
    "target_Tmax_tol": 20,
    "velocity": 10,
    "r0": 25,
    "use_inherent": true,
    "eps0": 0.002,
    "vtk_deform_scale": 1
  }
}
```

**Option B: Arbitrary lines (heat_lines)**

```json
{
  "out": "results/forward_validation",
  "simulation": {
    "Lx": 1000,
    "Ly": 1000,
    "thickness": 12,
    "heat_lines": [
      {"x0": 0, "y0": 500, "x1": 1000, "y1": 500},
      {"x0": 500, "y0": 0, "x1": 500, "y1": 1000}
    ],
    "target_Tmax": 900,
    "target_Tmax_tol": 20,
    "velocity": 10,
    "r0": 25,
    "use_inherent": true,
    "eps0": 0.002,
    "vtk_deform_scale": 1
  }
}
```

### How to Run:

**Windows:**
```cmd
copy run_config.example.json run_config_forward.json
REM Edit run_config_forward.json with your parameters
python scripts\run_anywhere.py --config run_config_forward.json
```

**macOS/Linux:**
```bash
cp run_config.example.json run_config_forward.json
# Edit run_config_forward.json with your parameters
python3 scripts/run_anywhere.py --config run_config_forward.json
```

### Output Files:
- `results/forward_validation/temperature.npy` - Temperature field data
- `results/forward_validation/displacement.npy` - Displacement field data
- `results/forward_validation/results.vtk` - 3D visualization
- `results/forward_validation/results_deformed.vtk` - Deformed mesh
- `results/forward_validation/summary.json` - Simulation summary
- `results/forward_validation/report.pdf` - Full analysis report

### Key Parameters to Validate:

The curvature profile can be analyzed from:
1. **Deflection field `w(x,y)`** - Vertical displacement
2. **Curvature `κ(x,y)`** - Computed from displacement gradients
3. **Camber** - Maximum deflection along centerline
4. **Edge-to-edge camber** - Plate edge measurements

---

## Use Case B: Inverse Problem - Test Curvature Given Line Heating Profile

**Objective:** Given a target curvature profile for a plate with specific dimensions, test and optimize the line heating pattern (positions, sequences, temperatures) required to achieve that curvature.

### What You Provide:
- Target plate dimensions (`Lx`, `Ly`, `thickness`)
- Desired curvature profile (radius or specific shape)
- Line heating pattern (positions, sequence)
- Allowable temperature ranges

### What You Get:
- Optimized heating parameters
- Predicted curvature compared to target
- Heating sequence recommendations
- Process validation metrics

### Example Configuration:

```json
{
  "out": "results/inverse_optimization",
  "simulation": {
    "Lx": 2000,
    "Ly": 1000,
    "thickness": 12,
    
    "heat_y_list": [333, 667],
    "heat_mode": "sequential",
    
    "target_Tmax": 950,
    "target_Tmax_tol": 30,
    "target_Tmax_iters": 5,
    
    "velocity": 12,
    "r0": 30,
    
    "use_inherent": true,
    "eps0": 0.0025,
    "inh_zfrac": 0.5,
    
    "bc": "corner_pins"
  }
}
```

### How to Run:

**Iterative Optimization Approach:**

1. **First iteration - baseline:**
   ```cmd
   python scripts\run_anywhere.py --config run_config_inverse.json
   ```

2. **Analyze results:**
   - Check `summary.json` for curvature metrics
   - View `results_deformed.vtk` in ParaView
   - Review deflection plots in `report.pdf`

3. **Adjust parameters:**
   - Modify `heat_y_list` (line positions)
   - Adjust `target_Tmax` (heating intensity)
   - Change `velocity` (heating speed)
   - Tune `eps0` (inherent strain magnitude)

4. **Re-run until target curvature achieved**

### Parameter Sweep Example:

Run multiple configurations to find optimal heating pattern:

```bash
# Create multiple configs with different line positions
for positions in "250,500,750" "300,600,900" "400,800"; do
  sed "s/\"heat_y_list\": .*/\"heat_y_list\": [$positions],/" run_config.example.json > config_$positions.json
  python3 scripts/run_anywhere.py --config config_$positions.json
done
```

### Validation Metrics:

Compare achieved vs target curvature:
1. **Radius of curvature** - From `summary.json`
2. **Camber measurements** - Edge-to-edge deflection
3. **Curvature uniformity** - `κ_x`, `κ_y`, `κ_xy` fields
4. **Residual stress** - If stress analysis enabled

---

## Comparison: Forward vs Inverse

| Aspect | Forward (Use Case A) | Inverse (Use Case B) |
|--------|---------------------|---------------------|
| **Input** | Torch temperature, heating path | Target curvature, plate dimensions |
| **Output** | Resulting curvature profile | Required heating parameters |
| **Goal** | Validate physics model | Optimize manufacturing process |
| **Iterations** | Single simulation | Multiple simulations (optimization) |
| **Use Case** | Research, validation | Manufacturing planning |

---

## Advanced Features

### Multi-Pass Heating

For complex curvature profiles, use multiple passes:

```json
{
  "heat_y_list": [200, 400, 600, 800],
  "heat_mode": "sequential",
  "pass_gap": 50
}
```

### Temperature Control

Auto-adjust power to maintain target temperature:

```json
{
  "target_Tmax": 900,
  "target_Tmax_tol": 20,
  "target_Tmax_iters": 3
}
```

### Quenching

Include water quenching effects:

```json
{
  "quench": true,
  "quench_h_conv": 0.005,
  "quench_T_inf": 293
}
```

### Inherent Strain Method

For permanent deformation (residual bending):

```json
{
  "use_inherent": true,
  "eps0": 0.002,
  "inh_sigma": 60,
  "inh_zfrac": 0.5
}
```

### Elastoplastic (J2) Mechanics (Experimental)

Enable a stateful J2 elastoplastic update (one integration point per element) and disable inherent strain:

```json
{
  "use_elastoplastic": true,
  "sigma_y0": 250.0,
  "hardening_H": 1000.0,
  "plastic_iters": 3,
  "plastic_tol": 1e-6
}
```

### Li et al. (2023) Reproduction + Tuning

This workflow mirrors the settings used by [scripts/run_li2023_cases.py](scripts/run_li2023_cases.py) and is designed to make tuning systematic and repeatable.

#### Method (High-Level)
1. **Thermal calibration:** use a target peak temperature ($T_{max}$) mapped from energy-per-length to keep peak temperatures realistic.
2. **Inherent strain baseline:** run each case with a fixed $\varepsilon_{0,ref}$ to measure linear response.
3. **Scaling law:** fit a single coefficient $C$ with fixed exponents to scale $\varepsilon_0$ across speed, energy, thickness, and pass count.
4. **Re-run with tuned $\varepsilon_0$** and compare deflection to experiments.

#### Scaling Law (Current)
$$
\varepsilon_0 = C \left(\frac{E}{E_{ref}}\right)^a \left(\frac{V_{ref}}{V}\right)^b \left(\frac{H_{ref}}{H}\right)^p \left[1 + (N-1)\,\delta\right]
$$

**Reference values:**
- $E_{ref}=600$ J/mm
- $V_{ref}=6$ mm/s
- $H_{ref}=14$ mm
- $\varepsilon_{0,ref}=0.01$

**Fixed exponents (current):**
- $a=0.35$ (energy sensitivity)
- $b=0.10$ (speed sensitivity)
- $p=0.25$ (thickness factor)
- $\delta$ (linear pass factor; calibration may use small negative values)

Only $C$ and $\delta$ are tuned; $C$ is fitted by least squares using the baseline runs for each parameter set.

#### Required Settings (Match Paper Assumptions)
These are the key settings used in the Li et al. batch runs:

```json
{
  "Lx": 400,
  "Ly": 300,
  "r0": 7,
  "gaussian_beta": 3.0,
  "bc": "centerline_fixed",
  "h_conv_top": 5e-5,
  "h_conv_bottom": 5e-5,
  "emissivity": 0.8,
  "target_Tmax": "mapped from energy (600–1000 J/mm -> 900–1100 C)",
  "target_Tmax_tol": 20,
  "target_Tmax_iters": 3,
  "pass_repeats": "= N_heats",
  "use_inherent": true,
  "inh_sigma": 7,
  "inh_zfrac": 0.2,
  "E_table": "20:205000,250:187000,500:150000,750:70000,1000:2000,1500:1500",
  "nu_table": "20:0.28,250:0.29,500:0.31,750:0.35,1000:0.40,1500:0.49",
  "alpha_table": "20:1.1e-5,250:1.2e-5,500:1.39e-5,750:1.48e-5,1000:1.34e-5,1500:1.33e-5"
}
```

#### eps0 Model Fragment (Reference)

```json
"eps0_model": {
  "type": "power_law",
  "C": 0.038,
  "E_ref": 600.0,
  "V_ref": 6.0,
  "H_ref": 14.0,
  "a": 0.35,
  "b": 0.10,
  "p": 0.25,
  "delta": 0.40
}
```

#### Tuning Guidance
- If **high-energy cases are too stiff**, lower $a$ (energy exponent).
- If **fast cases are under-predicted**, reduce $b$ (speed sensitivity).
- If **multi-pass cases are over-predicted**, reduce $\delta$.
- If **thicker plates bend too much**, increase $p$ (thickness penalty).
- Keep **$T_{max}$ in a realistic range** by mapping energy to target temperature.

#### Output to Inspect
- Comparison table: [results/li2023_comparison.csv](results/li2023_comparison.csv)
- Per-case report: [results/li2023_case_001/report.pdf](results/li2023_case_001/report.pdf) (example)

---

## Validation Workflow

### 1. Run Simulation

```bash
python3 scripts/run_anywhere.py --config run_config.json
```

### 2. Analyze Results

**View in ParaView:**
```bash
paraview results/your_run/results_deformed.vtk
```

**Check Metrics:**
```python
import json
with open('results/your_run/summary.json') as f:
    data = json.load(f)
    print(f"Max deflection: {data['max_deflection_mm']:.2f} mm")
    print(f"Edge camber: {data['edge_to_edge_camber_mm']:.2f} mm")
```

**Load NumPy Data:**
```python
import numpy as np
displacement = np.load('results/your_run/displacement.npy')
temperature = np.load('results/your_run/temperature.npy')
```

### 3. Compare with Target

**For Forward Problem:**
- Compare simulated curvature with experimental measurements
- Validate temperature profiles with thermocouple data

**For Inverse Problem:**
- Calculate deviation from target curvature
- Iterate parameters if needed

---

## Example Scenarios

### Scenario 1: Center Pass Validation (Forward)

Validate a single centerline pass at 900K:

```json
{
  "Lx": 1000, "Ly": 1000, "thickness": 12,
  "heat_y_list": [500],
  "target_Tmax": 900,
  "velocity": 10
}
```

Expected: Symmetric curvature profile, max deflection at center.

### Scenario 2: Three-Pass Optimization (Inverse)

Find optimal positions for three passes to achieve uniform curvature:

```json
{
  "Lx": 2000, "Ly": 1500, "thickness": 15,
  "heat_y_list": [375, 750, 1125],
  "target_Tmax": 950,
  "velocity": 12
}
```

Goal: Minimize curvature variation across plate.

### Scenario 3: Ship Hull Section (Forward)

Validate complex heating pattern for ship hull:

```json
{
  "Lx": 5000, "Ly": 3000, "thickness": 18,
  "heat_y_list": [500, 1000, 1500, 2000, 2500],
  "heat_mode": "sequential",
  "target_Tmax": 950
}
```

See `python_prototype/examples/run_ship_hull_case.py` for details.

---

## Post-Processing Tools

### Extract Camber Profile

```python
# See: thermo_fem/python/compute_edge_to_edge_camber.py
python thermo_fem/python/compute_edge_to_edge_camber.py results/your_run/
```

### Analyze Deformation

```python
# See: thermo_fem/python/analyze_deformation.py
python thermo_fem/python/analyze_deformation.py results/your_run/
```

### Parameter Sweep

```python
# See: thermo_fem/python/run_param_sweep_3d.py
python thermo_fem/python/run_param_sweep_3d.py --param velocity --values 8,10,12,15
```

---

## References

- **Heat Transfer Model:** Transient 3D conduction with moving Gaussian heat source
- **Mechanical Model:** Linear thermoelasticity with inherent strain option
- **Mesh:** Adaptive tetrahedral mesh with refinement around heating lines
- **Units:** mm, s, K, MPa (N/mm²)

For implementation details, see:
- [thermo_fem/python/run_coupled_3d.py](thermo_fem/python/run_coupled_3d.py) - Main solver
- [python_prototype/line_heating/](python_prototype/line_heating/) - Planning tools
- [docs/inherent_strain_models.tex](docs/inherent_strain_models.tex) - Theory
