# Ship Plate Bending — Line Heating (3D)

This repo contains a 3D coupled thermo-mechanical finite element workflow for ship-plate line heating:

- Gmsh tetrahedral mesh (with refinement around heating line(s))
- Transient 3D heat diffusion with moving Gaussian surface heat input + convection (optional radiation)
- 3D linear thermoelasticity via a C++/pybind11 module (`thermo_bindings`)
- Optional **inherent strain** surrogate to produce *residual* (permanent) bending
- Outputs: `.vtk` for ParaView, `.png` plots, `.npy` arrays, `summary.json`, and an auto-generated LaTeX/PDF report

## ⚡ Quick Start (Cross-Platform)

**✓ Works on macOS, Windows, and Linux**  
**✓ All dependencies stay in the project folder**  
**✓ Nothing installed globally**

### Automated Setup

**macOS / Linux:**
```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**
```cmd
setup.bat
```

### Validate Your Setup

```bash
python3 scripts/validate_setup.py
```

### Run a Simulation

```bash
# 1. Copy example config
cp run_config.example.json run_config.json

# 2. Run simulation
python3 scripts/run_anywhere.py --config run_config.json
```

📖 **For detailed setup instructions, see [SETUP.md](SETUP.md)**

---

## Quick start (Windows / Linux / macOS)

### 1) Prerequisites

Required:
- **Python 3.11 or 3.12** (recommended: 3.11)
- A C++ compiler (C++17)
  - Windows: Visual Studio Build Tools
  - Linux: `gcc/g++`
  - macOS: Xcode Command Line Tools
- CMake (the runner can also use the Python `cmake` package)

Recommended:
- Keep all generated outputs under the repo-level `results/` folder (so code folders stay clean)

Gmsh:
- The solver uses the **Python `gmsh` bindings** (installed via `requirements.txt`).
- A system `gmsh` executable is optional; if not found, the runner prints install hints.

Optional (for PDF report):
- `latexmk` or `pdflatex` on your `PATH` (TeX Live / MiKTeX)
  - If TeX is not installed, the report generator still writes `report.tex`.

### 2) Create a config file

Copy and edit the example JSON:

```bash
cp run_config.example.json run_config.json
```

Edit `run_config.json`:
- `out`: output folder (recommended: a folder under `results/`)
- `simulation`: parameters passed through to `thermo_fem/python/run_coupled_3d.py`
- `runner`: runner behavior (build/report toggles)

If you omit `out`, the runner defaults to `results/<config_name>`.

### 3) Run (build + simulate + report)

From the repo root:

```bash
python scripts/run_anywhere.py --config run_config.json
```

Outputs are written to your configured `out` folder. For safety, if `out` points inside a code folder like `thermo_fem/` or `python_prototype/`, the runner automatically redirects it to `results/<folder_name>`.

To force writing into a code folder (not recommended), pass:

```bash
python scripts/run_anywhere.py --allow-code-out --config run_config.json
```

## Clean generated files

Dry-run (prints what would be deleted):

```
python3 scripts/clean_generated.py
```

Actually delete generated virtualenvs + outputs:

```
python3 scripts/clean_generated.py --apply
```

Optional extras:

```
python3 scripts/clean_generated.py --apply --include-build --include-caches --include-latex-aux
```

What this does:
- Creates a local venv at `./.venv_lineheating`
- Installs Python deps from `requirements.txt`
- Builds `thermo_fem/build/cpp/thermo_bindings.*` via CMake
- Runs `thermo_fem/python/run_coupled_3d.py`
- Generates `report.tex` and (if TeX is installed) `report.pdf`

## Project layout (what file does what)

Runner / utilities:
- [scripts/run_anywhere.py](scripts/run_anywhere.py): creates venv, installs deps, builds C++ extension, runs simulation, generates report, writes `solution_manifest.json`.
- [scripts/clean_generated.py](scripts/clean_generated.py): deletes generated venvs + outputs (dry-run by default).

Simulation core:
- [thermo_fem/python/run_coupled_3d.py](thermo_fem/python/run_coupled_3d.py): main 3D workflow (mesh → thermal solve → mechanics solve → outputs).

Report generation:
- [scripts/report/make_report.py](scripts/report/make_report.py): reads an output folder (`summary.json` + plots) and writes `report.tex` (and `report.pdf` if TeX exists).

C++ extension (thermoelasticity / assembly):
- [thermo_fem/cpp/CMakeLists.txt](thermo_fem/cpp/CMakeLists.txt): builds the `thermo_bindings` pybind11 module.
- [thermo_fem/cpp/src/heat.cpp](thermo_fem/cpp/src/heat.cpp): thermal element assembly helpers.
- [thermo_fem/cpp/src/mechanics.cpp](thermo_fem/cpp/src/mechanics.cpp): 3D linear elasticity + thermal load assembly.
- [thermo_fem/cpp/src/bindings.cpp](thermo_fem/cpp/src/bindings.cpp): pybind11 bindings.

## Mathematical model (what is being solved)

Thermal (transient heat diffusion in 3D):

$$\rho c_p\,\frac{\partial T}{\partial t}=\nabla\cdot\left(k\nabla T\right)\quad\text{in }\Omega$$

Top surface heat input is a moving Gaussian flux (line-heating scan along $x$):

$$-k\nabla T\cdot\mathbf{n}=q(x,y,t) - h\,(T-T_\infty)\quad\text{on }\Gamma_{top}$$
$$q(x,y,t)=q_0\,\exp\left(-\frac{2r^2}{r_0^2}\right),\quad r^2=(x-x_s(t))^2+(y-y_\text{line})^2$$

Bottom (and optionally other faces) use convection:

$$-k\nabla T\cdot\mathbf{n} = -h\,(T-T_\infty)\quad\text{on }\Gamma_{conv}$$

Time integration uses backward Euler, giving a sparse linear solve each timestep:

$$\left(\frac{M}{\Delta t}+K_T\right)\,T^{n+1}=\frac{M}{\Delta t}\,T^{n}+f^{n+1}$$

where $M$ is the (capacity) mass matrix and $K_T$ is the conduction/Robin stiffness.

Mechanics (3D linear thermoelasticity):

$$\nabla\cdot\sigma + b = 0,\quad \sigma=\mathbb{C}:(\varepsilon-\varepsilon_{th}-\varepsilon_{inh})$$
$$\varepsilon=\tfrac{1}{2}(\nabla u+(\nabla u)^T),\quad \varepsilon_{th}=\alpha\,(T-T_{ref})\,\mathbf{I}$$

The inherent-strain term $\varepsilon_{inh}$ is an optional surrogate for inelastic/plastic effects to produce residual bending after cooldown.

### 4) Outputs

Everything is written under the configured `out` folder, including:
- `summary.json` (key inputs + thermal peak + deflection/camber metrics)
- `run.log` (full console log)
- `solution_manifest.json` (paths to key outputs)
- `report.tex`, `report.pdf`
- `results_*.vtk` (ParaView)
- `*.png` plots
- `nodes.npy`, `tet.npy`, `temperature.npy`, `displacement.npy`

---

## 📚 Documentation

- **[SETUP.md](SETUP.md)** - Detailed setup instructions for each platform
- **[PLATFORM-INDEPENDENT.md](PLATFORM-INDEPENDENT.md)** - How cross-platform support works
- **[QUICK-REFERENCE.md](QUICK-REFERENCE.md)** - Command cheat sheet for all platforms
- **[README.md](README.md)** - This file (project overview)

---

## Report-only mode

If you already have a completed output folder (with `summary.json` and plots), you can generate the report only:

```bash
python scripts/run_anywhere.py --out results/some_run --report-only
```

## Simulation parameters (high level)

You can set any CLI parameter from `thermo_fem/python/run_coupled_3d.py` in JSON under `simulation`.

A few common ones:
- Geometry/mesh: `Lx`, `Ly`, `thickness`, `h`, `h_refine`, `refine_band`
- Heating lines:
  - Single: `heat_y`
  - Multiple: `heat_y_list: [250, 500, 750]`
- Multi-pass scheduling:
  - `heat_mode: "simultaneous" | "sequential"`
  - `pass_gap` (seconds between sequential passes)
- Target peak temperature: `target_Tmax`, `target_Tmax_tol`, `target_Tmax_iters`
- Quench: `quench`, `quench_start`, `quench_h_conv`, `quench_T_inf`
- Residual bending (surrogate): `use_inherent`, `eps0`, `inh_sigma`, `inh_zfrac`
- VTK deformation: `vtk_deform_scale` (use `1` for true scale)

## Manual build (advanced)

You can also build the C++ extension manually:

```bash
cd thermo_fem
cmake -S cpp -B build/cpp -DPYBIND11_FINDPYTHON=ON
cmake --build build/cpp -j
```

Then run the solver:

```bash
cd thermo_fem/python
python run_coupled_3d.py --out outputs_3d
```

## Troubleshooting

- **No PDF produced**: install `latexmk` or `pdflatex` (TeX Live / MiKTeX). You should still get `report.tex`.
- **Build fails on Windows**: install Visual Studio Build Tools + CMake, then rerun `python scripts/run_anywhere.py --config run_config.json`.
- **ParaView looks “too deformed”**: set `vtk_deform_scale: 1` for true scale; use `results_camber_only_deformed.vtk` for thickness-preserving camber visualization.

## Notes

- Units are consistent in **mm, s, K, MPa**.
- Residual bending requires inelastic effects; in this repo it’s approximated via the inherent-strain surrogate.
