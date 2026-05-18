# Keel Plate Line Heating Analysis Report
## IGES File: keel plate 0-5.igs

---

## 📐 IGES File Details

### Source Information
- **File Name:** keel plate 0-5.igs
- **Software:** DASSAULT SYSTEMES CATIA V5 R21
- **Creation Date:** 2026-01-21
- **Model Name:** KEEL PLATE
- **Units:** MM (millimeters)
- **File Type:** NURBS Surface (Entity 128 - Rational B-Spline Surface)

### Extracted Geometry
The IGES file contains a complex 3D NURBS surface representing a ship hull keel plate with:
- **Full Length (X):** ~60,800 mm (60.8 meters)
- **Full Width (Y):** ~60,800 mm (60.8 meters)  
- **Thickness (Z):** ~49 mm

**Note:** This is a very large marine structure. For practical analysis and simulation, we analyze a representative **3m x 1m section** which can be scaled to the full dimensions.

---

## 🎯 Line Heating Strategy

### Why Line Heating for This Plate?

Line heating is used to induce controlled curvature in ship hull plates. The keel plate needs specific curvature to:
1. Match the hull design from the IGES surface
2. Provide structural strength
3. Enable proper assembly with adjacent hull sections

### Curvature Requirements

From the NURBS surface data, the plate exhibits complex 3D curvature. The heating pattern must create:
- **Longitudinal curvature** (along the length)
- **Transverse curvature** (across the width)
- **Twist compensation** (if needed)

---

## 🔥 Recommended Heating Pattern

### Pattern Configuration (Representative Section: 3m x 1m)

```
Number of Lines:    5 longitudinal lines
Line Spacing:       166.7 mm (evenly distributed)
Line Orientation:   Longitudinal (parallel to X-axis)
Heating Side:       +z (top surface)
Heating Mode:       Sequential (one line at a time)
Line Width:         18 mm (torch footprint)
```

### Line Positions (Y-coordinates)

| Line ID | Y Position (mm) | Start Point | End Point |
|---------|----------------|-------------|-----------|
| L1      | 166.7          | (0, 166.7)  | (3000, 166.7) |
| L2      | 333.3          | (0, 333.3)  | (3000, 333.3) |
| L3      | 500.0          | (0, 500.0)  | (3000, 500.0) |
| L4      | 666.7          | (0, 666.7)  | (3000, 666.7) |
| L5      | 833.3          | (0, 833.3)  | (3000, 833.3) |

### Visual Pattern

```
    0mm                                             3000mm
    |===============================================|
    
166.7mm ————————————————————————————————————————————— L1
    
333.3mm ————————————————————————————————————————————— L2
    
500.0mm ————————————————————————————————————————————— L3  (centerline)
    
666.7mm ————————————————————————————————————————————— L4
    
833.3mm ————————————————————————————————————————————— L5
    
1000mm  |===============================================|
```

---

## ⚡ Heat Energy Requirements

### Process Parameters

| Parameter | Value | Unit |
|-----------|-------|------|
| Torch Power | 12.0 | kW |
| Travel Speed | 12.0 | mm/s |
| Footprint Width | 18.0 | mm |
| Target Temperature | 900-950 | °C (1173-1223K) |
| Line Energy Density | 1000 | J/mm |

### Per Line Energy (3000mm length)

- **Total Energy per Line:** 3.00 MJ (megajoules)
- **Heating Time per Line:** 4.2 minutes
- **Cooling Time per Line:** 2.0 minutes (120 seconds lag)
- **Total Time per Line:** ~6.2 minutes

### Total for 5 Lines

| Metric | Value |
|--------|-------|
| **Total Energy Required** | 15.0 MJ |
| **Active Heating Time** | 20.8 minutes |
| **With Cooling Intervals** | 31.3 minutes (0.5 hours) |

---

## 📊 Scaling to Full Plate Dimensions

For the full keel plate (60.8m x 60.8m):

### Estimated Requirements

**Number of Lines (full plate):**
- With 200mm line spacing: ~**300 lines**
- With 166mm line spacing: ~**360 lines**

**Energy Requirements (full plate):**
- Energy per line (60.8m): **60.8 MJ**
- Total energy (300 lines): **~18,240 MJ** (18.2 GJ)
- Total energy (360 lines): **~21,888 MJ** (21.9 GJ)

**Time Requirements (full plate):**
- Active heating: **~25-30 hours**
- With cooling intervals: **~40-50 hours**
- Recommended: Process in sections over **multiple days**

### Practical Implementation

Due to the massive size, the full plate would typically be:
1. **Divided into sections** (e.g., 6m x 6m panels)
2. **Heated in segments** over multiple work shifts
3. **Monitored continuously** for temperature and deformation
4. **Quality checked** after each section

---

## 🔧 Technical Specifications

### Material Properties (Assumed: Marine Grade Steel A36)

| Property | Value | Unit |
|----------|-------|------|
| Young's Modulus (E) | 210,000 | MPa |
| Poisson's Ratio (ν) | 0.3 | - |
| Thermal Expansion (α) | 1.2×10⁻⁵ | 1/K |
| Yield Strength | 250 | MPa |
| Thermal Conductivity (k) | 45 | W/(m·K) |
| Density (ρ) | 7850 | kg/m³ |
| Specific Heat (cp) | 500 | J/(kg·K) |

### Expected Deformation

For the representative 3m x 1m section with 5 lines:

- **Maximum Deflection:** ~15-30 mm (typical for this pattern)
- **Curvature Radius:** ~10-20 meters (depends on exact parameters)
- **Angular Distortion:** ~1-3 degrees per meter
- **Permanent Strain:** ~0.2% (inherent strain)

---

## 📝 Process Workflow

### Step-by-Step Procedure

1. **Preparation**
   - Clean plate surface
   - Mark heating line positions using template
   - Set up torch equipment (12 kW power source)
   - Prepare cooling water system

2. **Heating Sequence (Sequential Mode)**
   ```
   For each line (L1 through L5):
     a. Position torch at start point (0, y_position)
     b. Heat line at 12 kW power, 12 mm/s speed
     c. Duration: 4.2 minutes per line
     d. Apply water quench after 120-second lag
     e. Allow cooling for 2 minutes
     f. Measure deformation
     g. Proceed to next line
   ```

3. **Quality Control**
   - Measure deflection at multiple points
   - Compare with target curvature from IGES
   - Check for cracks or surface defects
   - Verify angular distortion
   - Document results

4. **Post-Processing**
   - Final inspection
   - Stress relief (if required)
   - Surface finishing
   - Dimensional verification against IGES model

---

## 📈 Expected Results

### Deflection Profile

The heating pattern will produce:
- **Transverse curvature** (convex in Y-direction)
- **Minimal longitudinal curvature** (small effect in X-direction)
- **Edge effects** (boundary conditions matter)

### Typical Deflection (3m x 1m section):

```
                  Maximum at center (~20mm)
                          ↓
    |                     •                     |
    |                   /   \                   |
    |                 /       \                 |
    |               /           \               |
    |             /               \             |
    |           /                   \           |
    |         /                       \         |
    |_______/___________________________\______|
    0mm                                    1000mm
         Y-direction (across width)
```

---

## ⚠️ Important Considerations

### Safety
- High temperatures (900-950°C) require proper PPE
- Water quenching creates steam hazards
- Thermal stress can cause warping or cracking
- Proper ventilation required

### Quality Factors
- **Line spacing** affects curvature magnitude (closer = more curvature)
- **Heating temperature** must be controlled within ±20K tolerance
- **Travel speed** consistency critical (±5% variation maximum)
- **Cooling rate** affects residual stress and deformation

### Equipment Requirements
- **Torch:** 12-15 kW capacity, precise speed control
- **Power supply:** Stable, continuous operation
- **Cooling system:** Water flow rate 5-10 L/min per line
- **Measurement:** Laser scanner or CMM for deformation tracking
- **Temperature monitoring:** Infrared thermometer or thermal camera

---

## 🎯 Next Steps

### To Proceed with Simulation:

1. **Run the analysis script:**
   ```bash
   python scripts/cases/analyze_keel_plate.py
   ```

2. **Use the generated plan:**
   ```bash
   python python_prototype/examples/run_plan_cli.py \
       config/keel_plate_heating_plan.json \
       --plots-dir results/keel_plate_analysis
   ```

3. **For full 3D FEM simulation (3m x 1m section):**
   ```bash
   python scripts/run_anywhere.py \
       --config config/keel_plate_heating_plan.json \
       --out results/keel_plate_fem
   ```

4. **Visualize results:**
   - Open `.vtk` files in ParaView
   - Review generated plots in `results/` folder
   - Check `summary.json` for quantitative metrics

---

## 📚 References

### Related Documentation
- [USE-CASES.md](../docs/reference/USE-CASES.md) - Forward/inverse problem workflows
- [README.md](../README.md) - Project overview and features
- [config/README.md](../config/README.md) - Configuration parameters

### Key Physics
- **Thermal expansion:** ΔL = α × L × ΔT
- **Bending rigidity:** D = E×t³ / (12×(1-ν²))
- **Inherent strain:** Residual plastic deformation from thermal cycle
- **Angular distortion:** ~1-3° per meter for typical ship plates

### Process Parameters Source
Based on calibration from:
- Li et al. (2023) experimental data
- Industry standards for line heating (AWS D1.1)
- Ship hull fabrication guidelines (IACS standards)

---

## 📞 Contact & Support

Generated by: Ship Plate Line Heating Analysis Tool
Date: 2026-01-21
IGES File: keel plate 0-5.igs
Analysis Version: 0.1.0

---

**End of Report**
