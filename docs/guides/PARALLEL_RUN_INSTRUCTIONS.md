# Parallel FEM Simulation - Setup Complete & Running Instructions

## ✅ What's Been Set Up

### 1. **Parallel Computing Configuration**
- **CPU Cores:** 8 cores available
- **BLAS/LAPACK:** OpenBLAS with multi-threading support
- **Parallel Execution:** Enabled via environment variables

### 2. **Optimized Simulation Scripts**

#### A. Full Resolution (Original Plan)
- **Script:** [scripts/cases/run_keel_simulation_parallel.py](scripts/cases/run_keel_simulation_parallel.py)
- **Mesh:** 23,114 nodes, 84,598 elements
- **Time:** ~30-60 minutes
- **Accuracy:** High

#### B. Fast Version (Recommended) ✅
- **Script:** [scripts/cases/run_keel_fast_parallel.py](scripts/cases/run_keel_fast_parallel.py)
- **Mesh:** 14,564 nodes, 51,146 elements (40% smaller)
- **Time:** ~15-20 minutes
- **Accuracy:** Good (coarser mesh but faster)

### 3. **Optimization Strategies Applied**

```
Performance Optimizations:
✓ 8-thread parallel BLAS operations
✓ Coarser mesh (h=50mm vs 40mm)
✓ Larger time steps (dt=2.0s vs 1.0s)
✓ Simultaneous heating (all lines at once - faster)
✓ Reduced cooling time
✓ Fewer temperature tuning iterations
```

---

## 🚀 How to Run (Without Interruption)

### Option 1: Run in Background with nohup (Recommended)

```bash
cd /Users/rameshkolluru/MyProjects/Ship_Plate_Bending_LineHeating
source .venv_lineheating/bin/activate

# Run fast version
nohup python scripts/cases/run_keel_fast_parallel.py > results/logs/simulation_output.log 2>&1 &

# Save the process ID
echo $! > results/logs/simulation.pid
```

**Monitor progress:**
```bash
# Watch the log in real-time
tail -f results/logs/simulation_output.log

# Check if still running
ps -p $(cat results/logs/simulation.pid)
```

**Stop if needed:**
```bash
kill $(cat results/logs/simulation.pid)
```

### Option 2: Run with screen/tmux (Terminal persists)

```bash
# Start screen session
screen -S keel_simulation

# Inside screen, run:
cd /Users/rameshkolluru/MyProjects/Ship_Plate_Bending_LineHeating
source .venv_lineheating/bin/activate
python scripts/cases/run_keel_fast_parallel.py

# Detach: Press Ctrl+A then D
# Reattach later: screen -r keel_simulation
```

### Option 3: Run Directly (Keep terminal open)

```bash
cd /Users/rameshkolluru/MyProjects/Ship_Plate_Bending_LineHeating
source .venv_lineheating/bin/activate
python scripts/cases/run_keel_fast_parallel.py
```

**⚠️ Keep the terminal window open for 15-20 minutes**

---

## 📊 What the Simulation Does

### Phase 1: Mesh Generation (✅ Completed)
```
Time: ~1-2 minutes
Output: mesh.msh (3.0 MB)
Status: ✅ DONE
```

### Phase 2: Thermal Simulation (In Progress)
```
Steps:
1. Auto-tune heat flux to reach 900°C
2. Solve 3D heat diffusion over time
3. Calculate temperature at each node
4. Apply moving Gaussian heat source
   
Time: ~10-15 minutes
Output: Temperature fields, VTK files
```

### Phase 3: Mechanical Simulation  
```
Steps:
1. Solve 3D thermoelastic equations
2. Calculate deflection from thermal strain
3. Generate deformed geometry
4. Compute stress/strain fields

Time: ~3-5 minutes
Output: Deflection fields, deformed.vtk
```

### Phase 4: Results & Visualization
```
Generates:
- undeformed.vtk, deformed.vtk
- summary.json (metrics)
- deflection_solution.npy
- heat_solution.npy
- PNG plots

Time: ~1 minute
```

---

## 📈 Expected Results

### Mesh Statistics (Completed ✅)
```
Nodes:     14,564
Elements:  51,146 (tetrahedral)
Quality:   Excellent (no ill-shaped elements)
File Size: ~2.7 MB
```

### Thermal Results (Expected)
```
Peak Temperature:     900-950°C (1173-1223 K)
Heating Time:         250 s (4.2 min) per line
Total Simulation:     ~300 s (5 min)
Temperature Profile:  Gaussian distribution
```

### Deflection Results (Expected)
```
Maximum Deflection:   15-30 mm
Curvature Radius:     10-20 m
Pattern:              Transverse bending
RMS Deflection:       5-10 mm
```

---

## 🔍 Monitoring Progress

### Check Log File
```bash
# View last 20 lines
tail -20 results/logs/simulation_output.log

# Watch in real-time
tail -f results/logs/simulation_output.log

# Search for specific info
grep -i "temperature\|deflection\|completed" results/logs/simulation_output.log
```

### Check Output Directory
```bash
ls -lh results/keel_plate_fast_parallel/

# Count VTK files (shows progress)
ls results/keel_plate_fast_parallel/*.vtk 2>/dev/null | wc -l
```

### Expected Log Messages
```
Info: Meshing 3D... (1-2 min)
Info: Done meshing 3D
Info: Writing mesh.msh...
Auto-tuning q0 to target peak T... (2-3 min)
Thermal solve: time step 1/125... (10-12 min)
Solving mechanics (deflection)... (3-5 min)
Writing VTK files...
✅ SIMULATION COMPLETED
```

---

## 🎯 When Simulation Completes

### 1. Check Results
```bash
cd results/keel_plate_fast_parallel
ls -lh

# View summary
cat summary.json | python -m json.tool
```

### 2. Load in Python
```python
import numpy as np
import json

# Load deflection
w = np.load('deflection_solution.npy')
print(f"Max deflection: {np.max(np.abs(w)):.3f} mm")

# Load summary
with open('summary.json') as f:
    summary = json.load(f)
print(f"Peak temperature: {summary['T_max_K']:.1f} K")
```

### 3. Visualize in ParaView
```
1. Open ParaView
2. File → Open → undeformed.vtk
3. File → Open → deformed.vtk
4. Apply → Warp By Vector (displacement)
5. Color by: Temperature or w_deflection
```

---

## 🔧 Troubleshooting

### If Simulation Stalls
```bash
# Check if process is running
ps aux | grep python | grep run_keel

# Check memory usage
top -pid $(cat results/logs/simulation.pid)

# If hung, kill and restart
kill $(cat results/logs/simulation.pid)
```

### If Out of Memory
```bash
# Reduce mesh size further
# Edit scripts/cases/run_keel_fast_parallel.py:
h = 60.0  # Instead of 50.0
h_refine = 30.0  # Instead of 25.0
```

### If Taking Too Long
```bash
# Use even faster settings
dt = 3.0  # Instead of 2.0
extra_time = 25.0  # Instead of 50.0
```

---

## 📊 Performance Comparison

| Version | Nodes | Elements | Time | Accuracy |
|---------|-------|----------|------|----------|
| Full | 23,114 | 84,598 | 30-60 min | High |
| Fast ✅ | 14,564 | 51,146 | 15-20 min | Good |
| Ultra-fast | ~8,000 | ~30,000 | 5-10 min | Moderate |

---

## 📝 Current Status

```
✅ Mesh Generation: COMPLETED
   - 14,564 nodes, 51,146 elements
   - Quality: Excellent
   - File: results/keel_plate_fast_parallel/mesh.msh

⏳ Thermal Simulation: READY TO RUN
   - Script: scripts/cases/run_keel_fast_parallel.py
   - Parallel: 8 threads enabled
   - Time: ~15-20 minutes

⏳ Deflection Calculation: PENDING
   - Depends on thermal completion
   - Time: ~3-5 minutes additional
```

---

## 🚀 Recommended Next Step

**Run the simulation in background:**

```bash
cd /Users/rameshkolluru/MyProjects/Ship_Plate_Bending_LineHeating
source .venv_lineheating/bin/activate

# Run in background
nohup python scripts/cases/run_keel_fast_parallel.py > results/logs/simulation_output.log 2>&1 &
echo $! > results/logs/simulation.pid

# Monitor
tail -f results/logs/simulation_output.log

# Check status anytime
ps -p $(cat results/logs/simulation.pid) && echo "Still running" || echo "Completed"
```

Let it run for **15-20 minutes** without interruption.

---

## 📚 Related Files

- **Analysis:** [docs/reports/KEEL_PLATE_ANALYSIS_REPORT.md](docs/reports/KEEL_PLATE_ANALYSIS_REPORT.md)
- **Status:** [docs/status/SIMULATION_STATUS.md](docs/status/SIMULATION_STATUS.md)
- **Fast Script:** [scripts/cases/run_keel_fast_parallel.py](scripts/cases/run_keel_fast_parallel.py)
- **Full Script:** [scripts/cases/run_keel_simulation_parallel.py](scripts/cases/run_keel_simulation_parallel.py)
- **Config:** [config/keel_plate_heating_plan.json](config/keel_plate_heating_plan.json)

---

**Ready to Run!** ✅  
Just execute the nohup command above and let it complete.
