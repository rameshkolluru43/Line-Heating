# Keel Plate FEM Simulation Summary

## ✅ What Has Been Completed

### 1. IGES File Analysis
- **File:** `IGESFiles/keel plate 0-5.igs`
- **Extracted Dimensions:** 60.8m x 60.8m x 49mm (full plate)
- **Analyzed Section:** 3m x 1m x 49mm (representative section)
- **Script:** [scripts/cases/analyze_keel_plate.py](scripts/cases/analyze_keel_plate.py)

### 2. Heating Plan Generation
- **Generated Plan:** [config/keel_plate_heating_plan.json](config/keel_plate_heating_plan.json)
- **Number of Lines:** 5 longitudinal heating lines
- **Line Spacing:** 166.7 mm
- **Total Energy:** 15 MJ for 3m x 1m section
- **Process Time:** 31.3 minutes (with cooling)

### 3. FEM Simulation Setup
- **Simulation Script:** [scripts/cases/run_keel_simulation.py](scripts/cases/run_keel_simulation.py)
- **Heat Lines File:** [config/keel_plate_heat_lines.json](config/keel_plate_heat_lines.json)
- **Output Directory:** `results/keel_plate_simulation/`

### 4. Mesh Generation ✅ COMPLETED
```
✅ 3D Tetrahedral Mesh Successfully Generated:
   - 23,114 nodes
   - 84,598 tetrahedral elements  
   - Mesh quality: Good (no ill-shaped elements)
   - File: results/keel_plate_simulation/mesh.msh (4.2 MB)
```

---

## ⏱️ What Was In Progress (Interrupted)

The **thermal simulation** was starting when interrupted. This simulation would have:
1. Solved transient 3D heat diffusion for each of the 5 heating lines
2. Calculated temperature distribution over time
3. Solved 3D thermoelastic deflection
4. Generated VTK files for ParaView visualization
5. Created deflection plots and summary statistics

**Estimated Time:** 30-60 minutes for full simulation (5 passes × 350 seconds each)

---

## 🚀 How to Run the Complete Simulation

### Option 1: Run the Full Simulation (Recommended)

```bash
cd /Users/rameshkolluru/MyProjects/Ship_Plate_Bending_LineHeating
source .venv_lineheating/bin/activate
python scripts/cases/run_keel_simulation.py
```

**Note:** This will take 30-60 minutes. Let it run to completion without interruption.

### Option 2: Run with Custom Parameters

You can modify [scripts/cases/run_keel_simulation.py](scripts/cases/run_keel_simulation.py) to adjust:
- Mesh size (currently `h=40mm`, `h_refine=20mm`)
- Time step (currently `dt=1.0s`)
- Material properties
- Quench parameters

### Option 3: Run a Smaller Test Case First

To verify the setup works with a faster simulation:

```bash
cd thermo_fem/python
python run_coupled_3d.py \
  --Lx 500 --Ly 300 --thickness 12 \
  --h 50 --h-refine 25 --refine-band 80 \
  --heat-y 150 \
  --q0 10 --r0 9 --velocity 12 \
  --dt 1.0 --extra-time 50 \
  --target-Tmax 1173 \
  --out ../../results/test_simulation
```

This smaller case (500mm × 300mm × 12mm) will run in ~5-10 minutes.

---

## 📊 Expected Results

When the simulation completes, you will get:

### Output Files

```
results/keel_plate_simulation/
├── mesh.msh                    # Gmsh mesh file
├── undeformed.vtk             # Initial geometry
├── deformed.vtk               # Final deflected shape
├── temp_distribution_*.vtk    # Temperature fields at time steps
├── summary.json               # Quantitative metrics
├── deflection_solution.npy    # Deflection array
├── heat_solution.npy          # Temperature array
└── *.png                      # Plots (temperature, deflection)
```

### Expected Deflection

For the 3m × 1m × 49mm section with 5 heating lines:

```
Typical Results:
- Maximum Deflection:    15-30 mm
- Curvature Radius:      10-20 m
- Angular Distortion:    1-3 degrees per meter
- Peak Temperature:      900-950°C (controlled)
```

### Deflection Pattern

The plate will exhibit:
- **Transverse curvature** (bending across the width)
- **Convex shape** (heated side becomes shorter → bends away from heat)
- **Gradual transition** at edges
- **Symmetric pattern** (for symmetric line distribution)

---

## 📈 Visualization in ParaView

Once the simulation completes:

1. **Open ParaView**
2. **Load files:**
   - `undeformed.vtk` → Shows original mesh with temperature
   - `deformed.vtk` → Shows deflected shape
3. **Apply Warp By Vector:**
   - Vector: `displacement`
   - Scale: 1.0 (realistic) or 10.0 (exaggerated for visualization)
4. **Color by:**
   - `Temperature` → See thermal distribution
   - `w_deflection` → See out-of-plane deflection
   - `von_Mises` → See stress distribution

---

## 🔧 Troubleshooting

### If Simulation Takes Too Long

**Reduce mesh resolution:**
```python
# In scripts/cases/run_keel_simulation.py, line ~108
h = 60.0  # Instead of 40.0
h_refine = 30.0  # Instead of 20.0
```

### If Memory Issues Occur

**Reduce plate size or increase mesh size:**
```python
# Use a smaller representative section
Lx = 1500.0  # Instead of 3000.0
Ly = 500.0   # Instead of 1000.0
```

### If You Want Faster Results

**Use simultaneous heating (all lines at once):**
```python
# In run_fem_simulation(), line ~151
sequential=False  # Instead of True
```

This reduces simulation time from ~60 min to ~15 min but gives different results (all lines heat simultaneously instead of sequentially).

---

## 📝 Parameter Summary

### Plate Geometry
- Length: 3000 mm
- Width: 1000 mm
- Thickness: 49 mm

### Heating Parameters
- Torch Power: 12 kW
- Travel Speed: 12 mm/s
- Footprint radius: 9 mm
- Peak Flux: 94.3 W/mm²
- Target Temperature: 900°C (1173 K)

### Mesh Parameters
- Global size: 40 mm
- Refined size: 20 mm
- Refinement band: 80 mm around heating lines
- Total nodes: 23,114
- Total elements: 84,598

### Material Properties (Steel A36)
- Young's modulus: 210,000 MPa
- Poisson's ratio: 0.3
- Thermal expansion: 1.2×10⁻⁵ /K
- Thermal conductivity: 0.045 W/(mm·K)
- Density: 7.85×10⁻⁶ kg/mm³
- Specific heat: 500 J/(kg·K)

### Time Parameters
- Time step: 1.0 s
- Scan time per line: 250 s (4.2 min)
- Cooling between passes: 120 s (2 min)
- Extra cooling at end: 100 s (1.7 min)
- **Total simulation time: ~1750 s (29 min)**

---

## 🎯 Next Steps

1. **Run the full simulation** (30-60 minutes)
   ```bash
   python scripts/cases/run_keel_simulation.py
   ```

2. **Monitor progress** (in another terminal)
   ```bash
   tail -f results/logs/simulation_log.txt
   ```

3. **Check results** when complete
   ```bash
   ls -lh results/keel_plate_simulation/
   ```

4. **Visualize in ParaView**
   - Load `undeformed.vtk` and `deformed.vtk`
   - Compare temperature and deflection distributions

5. **Scale to full plate** if needed
   - Multiply deflection results by geometric scaling factor
   - Apply to full 60.8m × 60.8m plate in sections

---

## 📚 Documentation

- **IGES Analysis Report:** [docs/reports/KEEL_PLATE_ANALYSIS_REPORT.md](docs/reports/KEEL_PLATE_ANALYSIS_REPORT.md)
- **Thermo-FEM README:** [thermo_fem/README.md](thermo_fem/README.md)
- **Project README:** [README.md](README.md)
- **Use Cases Guide:** [docs/reference/USE-CASES.md](docs/reference/USE-CASES.md)

---

**Status:** Ready to run ✅  
**Last Updated:** January 21, 2026  
**Mesh Generated:** ✅ Complete  
**Thermal Simulation:** ⏳ Pending (ready to execute)
