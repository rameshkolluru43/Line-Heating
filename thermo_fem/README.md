# 3D Coupled Thermo-Mechanical FEM for Line Heating

Full 3D finite element implementation for ship plate line heating simulation.

## Quick Start

### Build C++ Library
```bash
cd thermo_fem
cmake -S . -B build -DPYBIND11_FINDPYTHON=ON
cmake --build build -j4
```

### Run Verification Tests
```bash
cd python
python3.11 verify_mechanics.py
python3.11 verify_thermal.py
```

### Run 3D Coupled Simulation
```bash
cd python
python3.11 run_coupled_3d.py --Lx 1000 --Ly 900 --thickness 12 --h 50
```

Note: for cleaner project organization, prefer writing outputs under the repo-level `results/` folder.

To auto-tune heat input to a desired peak temperature (e.g. ~900K), and write both undeformed/deformed VTK:
```bash
cd python
python3.11 run_coupled_3d.py --Lx 200 --Ly 140 --thickness 10 --h 60 --h-refine 25 --refine-band 35 --dt 1.0 --extra-time 5 --target-Tmax 900 --vtk-deform-scale 10 --out ../../results/outputs_3d_target900
```

## Implementation Status

### ✅ Steps 1-5 Complete

1. **Gmsh 3D mesh generation** - Tetrahedral elements with surface identification
2. **Transient thermal solver** - 3D heat conduction with backward Euler
3. **Moving Gaussian heat source** - Surface flux q = q₀ exp(-2r²/r₀²)
4. **Convection boundaries** - Robin BC on top/bottom surfaces
5. **Linear thermoelastic solver** - C++ FEM with thermal strain coupling

### ✅ Extensions Implemented

- **Temperature-dependent properties**: simple linear models for $k(T)$ and $c_p(T)$ with Picard iterations.
- **Radiation (optional)**: linearized Stefan–Boltzmann radiation as an equivalent Robin term.
- **Plasticity surrogate**: optional isotropic inherent strain field (adds to thermal eigenstrain).
- **Parameter sweeps**: subprocess-driven sweeps writing a `manifest.csv` dataset.

### 🔧 Core Components

**C++ library** (`cpp/`):
- `mechanics.cpp`: 3D elasticity (stiffness + thermal loads)
- `heat.cpp`: Thermal assembly
- `bindings.cpp`: Python interface via pybind11

**Python scripts** (`python/`):
- `run_coupled_3d.py`: Full thermo-mechanical simulation
- `verify_mechanics.py`: FEM verification tests (all passing ✓)
- `verify_thermal.py`: Thermal sanity checks (regression guard)
- `run_param_sweep_3d.py`: Parameter sweep + dataset manifest generator
- `run_plate_heat_moving.py`: 2D thermal solver (legacy)

### Next

- **More physical plasticity**: true elastoplastic integration + residual stresses (beyond inherent-strain surrogate).
- **Validation scaffolding**: compare to experiments/benchmarks and add calibrated parameter sets.

## Usage Details

See sections below for full parameter list and outputs.

### Parameter Sweeps (dataset generation)

```bash
cd python
python3.11 run_param_sweep_3d.py --out sweep_demo --q0 10 12 --velocity 10 12 --Lx 200 --Ly 140 --thickness 10 --h 60 --h-refine 25 --refine-band 35 --dt 1.0 --extra-time 5 --baseline-q0 10 --baseline-velocity 10
```

This produces per-case folders under `sweep_demo/` and a summary CSV at `sweep_demo/manifest.csv`.
Each run also writes `summary.json` with peak-temperature time/location and deflection extrema.

## Old 2D Prototype
```bash
cd thermo_fem
cmake -S . -B build -DPYBIND11_FINDPYTHON=ON
cmake --build build
```
Requirements: `pybind11` CMake package. Install via `pip install pybind11` or set `PYBIND11_ROOT`.

Run
```bash
cd thermo_fem
PYTHONPATH=build:python python python/run_plate_heat.py --Lx 1.0 --Ly 1.0 --h 0.1 --steps 500 --dt 1e-4 --solver explicit --bc --bc-value 0.0
```
Requires: `gmsh`, `numpy`, `scipy`, `matplotlib`, and built `thermo_bindings` on `PYTHONPATH`.

Thermal Deflection
To compute and plot thermal deflections in addition to temperature:
```bash
PYTHONPATH=build:python python python/run_plate_heat.py --Lx 1000 --Ly 500 --h 20 --thickness 10 --line-q 0.3 --line-width 20 --steps 500 --dt 5e-4 --solver implicit --bc --bc-value 293 --plot --compute-deflection
```
This will generate:
- `temperature.png`: Temperature distribution
- `deflection.png`: Out-of-plane thermal deflection
- `deflection_3d.png`: 3D surface plot of deflection

Notes
- Solvers: `--solver explicit` (lumped explicit Euler; small `dt` for stability) or `--solver implicit` (backward Euler; unconditionally stable but costlier per step).
- `--bc` applies Dirichlet temperature on the outer rectangle (value via `--bc-value`).
- Robin/Neumann: `--h-conv` with `--T-inf` adds convection; `--q-edge` adds boundary flux (positive into domain).
- `--compute-deflection`: Enables thermal deflection computation based on thermal strains and simplified plate theory.
- Material properties: `--E` (Young's modulus, MPa), `--nu` (Poisson's ratio), `--alpha` (thermal expansion coefficient, 1/K), `--T-ref` (reference temperature, K).
- Assembly currently covers 2D conduction; elasticity/thermo-mechanical coupling can be added in `cpp/src` with new bindings.
