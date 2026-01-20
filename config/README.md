# Configuration Files

This folder contains example configuration files for running simulations.

## 🎯 Use Case-Based Configs

### Forward Problem (Validate Curvature from Given Temperature)
**File:** `config_forward_example.json`

Use this when you want to:
- Simulate heating at a specific torch temperature (e.g., 900K)
- Predict the resulting curvature profile
- Validate simulation results against experiments

**Quick Start:**
```bash
# Copy to your own config
cp config/config_forward_example.json my_config.json

# Edit as needed
nano my_config.json  # or use any editor

# Run simulation
python3 scripts/run_anywhere.py --config my_config.json
```

### Inverse Problem (Optimize Heating Pattern for Target Curvature)
**File:** `config_inverse_example.json`

Use this when you want to:
- Achieve a specific target curvature
- Optimize line heating positions and parameters
- Plan manufacturing process parameters

**Quick Start:**
```bash
# Copy to your own config
cp config/config_inverse_example.json my_config.json

# Edit parameters
nano my_config.json

# Run first iteration
python3 scripts/run_anywhere.py --config my_config.json

# Adjust parameters based on results and re-run
```

### General Example
**File:** `run_config.example.json`

Standard example configuration with common parameters.

---

## 📋 Configuration Structure

All config files follow this structure:

```json
{
  "out": "results/output_folder",
  "runner": {
    "report_only": false,
    "no_build": false,
    "no_report": false
  },
  "simulation": {
    "Lx": 1000,           // Plate length (mm)
    "Ly": 1000,           // Plate width (mm)
    "thickness": 12,      // Plate thickness (mm)
    "heat_y_list": [500], // Heating line positions (parallel to x)
    "heat_lines": [        // Optional: arbitrary line segments
      {"x0": 0, "y0": 500, "x1": 1000, "y1": 500}
    ],
    "target_Tmax": 900,   // Target torch temperature (K)
    "velocity": 10,       // Torch speed (mm/s)
    // ... more parameters
  }
}
```

---

## 🔧 Key Parameters

### Plate Geometry
- `Lx`, `Ly` - Plate dimensions (mm)
- `thickness` - Plate thickness (mm)

### Heating Configuration
- `heat_y_list` - Y-coordinates of heating lines (mm) for lines parallel to x
- `heat_lines` - Arbitrary line segments, each `{x0,y0,x1,y1}` (mm)
- `heat_mode` - `"sequential"` or `"simultaneous"`
- `pass_gap` - Time between passes (seconds)

### Temperature Control
- `target_Tmax` - Target peak temperature (K)
- `target_Tmax_tol` - Temperature tolerance (K)
- `target_Tmax_iters` - Max iterations for convergence

### Process Parameters
- `velocity` - Torch travel speed (mm/s)
- `r0` - Torch radius (mm)
- `dt` - Time step (seconds)
- `extra_time` - Additional cooling time (seconds)

### Mechanical Behavior
- `use_inherent` - Enable inherent strain model
- `eps0` - Inherent strain magnitude
- `bc` - Boundary condition (`"corner_pins"`, `"clamped"`, etc.)

---

## 📖 Documentation

For detailed parameter descriptions and workflows:

- **[Quick Start Guide](../docs/reference/QUICK-START-USE-CASES.md)** - Step-by-step tutorials
- **[Use Cases Documentation](../docs/reference/USE-CASES.md)** - Detailed theory and examples
- **[Main README](../README.md)** - Project overview

---

## 💡 Tips

### Creating Your Own Config

1. **Start with an example:**
   ```bash
   cp config/config_forward_example.json my_project.json
   ```

2. **Edit key parameters** for your case

3. **Test with coarse settings first:**
   ```json
   {
     "Lx": 500,      // Smaller plate
     "h": 60,        // Coarser mesh
     "extra_time": 200  // Less cooling time
   }
   ```

4. **Refine after testing:**
   ```json
   {
     "Lx": 2000,     // Full size
     "h": 30,        // Finer mesh
     "extra_time": 600
   }
   ```

### Running Multiple Configs

```bash
# Run different scenarios
for config in config/*.json; do
  python3 scripts/run_anywhere.py --config "$config"
done
```

### Config Naming Convention

Suggested naming:
- `forward_900K_centerline.json` - Descriptive of use case
- `inverse_3pass_optimization.json` - Indicates problem type
- `ship_hull_section_001.json` - Project-specific naming

---

## 🔍 Validation

Before running long simulations:

1. **Test with minimal config:**
   ```json
   {
     "Lx": 300, "Ly": 300,
     "h": 80,
     "dt": 10,
     "extra_time": 100
   }
   ```

2. **Verify outputs:**
   ```bash
   ls results/test_run/
   # Should see: *.vtk, summary.json, report.pdf
   ```

3. **Check results make physical sense:**
   - Temperature peak near target_Tmax
   - Deflection pattern looks reasonable
   - No error messages in console

---

## 📂 Output Structure

Results are saved to the folder specified in `"out"`:

```
results/your_run/
├── summary.json          # Key metrics
├── temperature.npy       # Temperature field
├── displacement.npy      # Displacement field
├── nodes.npy            # Mesh nodes
├── results.vtk          # ParaView visualization
├── results_deformed.vtk # Deformed mesh
└── report.pdf           # Full analysis report
```
