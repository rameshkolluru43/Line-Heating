# Ship Plate Bending Line Heating

This repository contains a 3D finite-element workflow for simulating and planning line-heating operations used in ship-plate forming. It combines a transient thermal solver, thermo-mechanical deformation prediction, validation scripts, inverse planning tools, and a publication-ready manuscript package.

The project is designed for two main engineering questions:

- **Forward analysis:** given plate geometry, material data, and a heating plan, predict temperature evolution, residual deflection, camber, and curvature.
- **Inverse planning:** given a target camber or curvature profile, search for heating-line locations and process parameters that reproduce the target shape.

## Current Capabilities

- Generate 3D unstructured tetrahedral meshes in Gmsh with local refinement around heating lines.
- Solve transient 3D heat conduction with moving Gaussian, full-line Gaussian, or reduced skin-depth heat input.
- Model convection, optional radiation, and quenching through Robin-type boundary terms.
- Support simultaneous and sequential multi-line or multi-pass heating schedules.
- Use temperature-dependent Q345 material properties from Li et al. (2023) benchmark data.
- Solve thermo-mechanical deformation using linear tetrahedral elasticity and thermal strain loads.
- Represent permanent residual bending through a calibrated inherent-strain surrogate.
- Optionally run a J2 elastoplastic mechanics path for exploratory studies.
- Calibrate and validate against Li et al. (2023) line-heating benchmark cases.
- Run keel-plate demonstration cases with practical multi-line heating schedules.
- Evaluate forward and inverse line-heating plans through JSON configuration files.
- Produce VTK fields for ParaView, PNG figures, NumPy arrays, summary JSON, CSV comparisons, and LaTeX/PDF reports.
- Maintain a self-contained manuscript package in `publication2/` for journal-style presentation.

## Numerical Method

The solver uses a one-way coupled thermo-mechanical workflow. The transient thermal problem is solved first over the heating and cooling schedule; the resulting temperature field then drives the mechanical deformation solve.

### Thermal model

The heat-transfer problem is transient 3D conduction with heat input and surface losses:

```text
rho cp(T) dT/dt = div(k(T) grad T) + Q(x,t)
```

Surface terms include prescribed heat flux, convection, quenching, and optional linearized radiation. The finite-element discretization uses linear 4-node tetrahedral elements. Time integration uses backward Euler:

```text
(M/dt + K + Kbc) T(n+1) = (M/dt) T(n) + f_heat(n+1) + f_bc(n+1)
```

Temperature-dependent conductivity and heat capacity are updated with Picard fixed-point iterations inside each time step. The sparse systems are assembled in Python/C++ helpers and solved with SciPy sparse solvers.

### Mechanical model

Mechanical equilibrium is solved after the thermal analysis:

```text
div(sigma) = 0
sigma = D(T) : (epsilon - epsilon_th - epsilon_inh)
epsilon_th = alpha(T) (T - Tref) I
```

The main validation workflow uses linear thermoelasticity plus a calibrated inherent-strain field to represent permanent line-heating bending. This is an engineering residual-deformation model, not a fully coupled transient elastoplastic forming simulation. An optional J2 elastoplastic path is implemented for exploratory comparisons.

### Mesh and accuracy

The active validation meshes are engineering-resolution unstructured tet4 grids:

- Li2023 plate cases: typically about 8.5k to 9.6k nodes and 30k to 37k tetrahedra.
- Keel-plate demonstrations: about 8k to 23k nodes and 24k to 88k tetrahedra, depending on mesh settings.

Linear tetrahedra provide nominal second-order spatial behavior for smooth elliptic problems, while backward Euler is first-order accurate in time. In practice, localized moving heat sources, unstructured grids, centroid-based surface flux integration, and the inherent-strain surrogate limit the effective accuracy.

A representative Li2023 Case 6 mesh/time-step sensitivity matrix has been completed:

| Setting | `dt` (s) | `h_refine` (mm) | `T_peak` (K) | `|w|max` (mm) |
| --- | ---: | ---: | ---: | ---: |
| Baseline paper setting | 2.0 | 5.0 | 1176.9 | 7.722 |
| Refined time step | 1.0 | 5.0 | 1169.3 | 7.724 |
| Refined heating-band mesh | 2.0 | 2.5 | 1173.2 | 8.819 |
| Refined mesh + time step | 1.0 | 2.5 | 1174.9 | 8.819 |

For this case, halving the time step changes `|w|max` by only about 0.03%, while refining the heating-band mesh changes it by about 14.2%. Broader convergence across additional cases is still recommended before making general convergence claims.

## Heat-Source Modes

The core solver supports three heat-source idealizations:

- `moving_gaussian`: a localized Gaussian spot moving along a line at torch speed.
- `line_gaussian`: a full-line Gaussian heat band applied over the active segment.
- `induction_skin`: a reduced thermal model that distributes absorbed line power through thickness using a prescribed electromagnetic skin-depth expression.

The induction option is a thermal approximation. It does not solve the surrounding coil electromagnetic field.

## Repository Layout

- `thermo_fem/python/run_coupled_3d.py` - main 3D mesh, thermal, mechanics, and output driver.
- `thermo_fem/cpp/` - C++17 and pybind11 finite-element assembly routines.
- `scripts/run_anywhere.py` - cross-platform runner that sets up dependencies, builds, runs, and reports.
- `scripts/run_li2023_cases.py` - Li2023 benchmark runner.
- `scripts/run_li2023_induction_cases.py` - induction-skin variant for Li2023-style runs.
- `scripts/plan_line_heating.py` - forward and inverse line-heating planner.
- `scripts/execute_planned_work_items.py` - calibration, audit, and verification artifact generator.
- `scripts/make_publication_*.py` - figure-generation utilities for manuscript outputs.
- `config/` - example and production JSON configurations.
- `results/` - generated result summaries, comparisons, arrays, and diagnostics.
- `docs/` - theory notes, setup guides, reports, and workflow references.
- `publication2/` - active publication manuscript, figures, bibliography, and build files.
- `publication/` - earlier manuscript package retained for reference.

## Quick Start

### 1. Install prerequisites

Required:

- Python 3.11 or 3.12
- C++17 compiler
- CMake
- Python packages listed in `requirements.txt`

Platform notes:

- macOS: install Xcode Command Line Tools.
- Linux: install `gcc`, `g++`, and CMake.
- Windows: install Visual Studio Build Tools and CMake.

Automated setup:

```bash
chmod +x setup/setup.sh
./setup/setup.sh
```

On Windows:

```cmd
setup\setup.bat
```

Validate the environment:

```bash
python3 scripts/validate_setup.py
```

### 2. Run a configured simulation

Copy an example configuration and run from the repository root:

```bash
cp config/run_config.example.json run_config.json
python3 scripts/run_anywhere.py --config run_config.json
```

The runner creates a local virtual environment if needed, installs dependencies, builds the C++ extension, runs the solver, and generates report files.

### 3. Run forward or inverse planning

Forward plan evaluation:

```bash
python3 scripts/plan_line_heating.py --config config/plan_forward_example.json
```

Inverse planning:

```bash
python3 scripts/plan_line_heating.py --config config/plan_example.json
```

Outputs are written to the configured `out` folder, normally under `results/`.

## Common Simulation Parameters

Most solver options can be supplied under the `simulation` section of a JSON config.

- Geometry and mesh: `Lx`, `Ly`, `thickness`, `h`, `h_refine`, `refine_band`
- Heating lines: `heat_y`, `heat_y_list`, or arbitrary `heat_lines`
- Process parameters: `E`, `velocity`, `r0`, `passes`, `heat_mode`, `pass_gap`
- Thermal controls: `dt`, `extra_time`, `target_Tmax`, `target_Tmax_iters`
- Boundary conditions: `h_conv`, `h_conv_top`, `h_conv_bottom`, radiation emissivity
- Quenching: `quench`, `quench_start`, `quench_h_conv`, `quench_T_inf`
- Residual bending: `use_inherent`, `eps0`, `inh_sigma`, `inh_zfrac`
- Output controls: `vtk_deform_scale`, `energy_balance`, output directory

## Outputs

Each run writes a structured output folder. Typical files include:

- `summary.json` - key inputs, mesh size, thermal peak, deflection, camber, and curvature metrics.
- `solution_manifest.json` - paths to important generated artifacts.
- `run.log` - console log for the simulation.
- `nodes.npy`, `tet.npy`, `temperature.npy`, `displacement.npy` - numerical arrays.
- `results_*.vtk` - ParaView visualization files.
- `*.png` - mesh, temperature, deflection, camber, and validation plots.
- `report.tex` and optionally `report.pdf` - generated run report.

## Validation and Publication Artifacts

The repository includes scripts and generated artifacts for a publishable validation workflow:

- Li2023 benchmark validation tables and plots.
- Velocity-dependent inherent-strain calibration artifacts.
- Keel-plate thermal unit audits.
- Energy-response verification scaffolds.
- Process comparisons between moving Gaussian, line Gaussian, and induction-skin sources.
- Journal-style figures in `publication2/figures/`.
- A complete LaTeX manuscript in `publication2/main.tex`.

Build the active manuscript:

```bash
cd publication2
make
```

or manually:

```bash
cd publication2
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

## Standalone Executable

You can package the runner as a native executable for a target OS. The executable still expects the repository data and scripts to be present.

```bash
python -m pip install -r requirements-build.txt
python scripts/build_executable.py --onefile --name lineheating
./dist/lineheating --config run_config.json
```

## Manual Build

To build the C++ extension directly:

```bash
cd thermo_fem
cmake -S cpp -B build/cpp -DPYBIND11_FINDPYTHON=ON
cmake --build build/cpp -j
```

Then run the Python driver:

```bash
cd python
python run_coupled_3d.py --out ../../results/manual_run
```

## Cleaning Generated Files

Preview cleanup:

```bash
python3 scripts/clean_generated.py
```

Apply cleanup:

```bash
python3 scripts/clean_generated.py --apply
```

Include build and cache artifacts:

```bash
python3 scripts/clean_generated.py --apply --include-build --include-caches --include-latex-aux
```

## Documentation

- `docs/reference/QUICK-START-USE-CASES.md` - step-by-step usage examples.
- `docs/reference/USE-CASES.md` - forward and inverse problem descriptions.
- `docs/guides/SETUP.md` - installation details.
- `docs/guides/OFFLINE-SETUP.md` - air-gapped setup.
- `docs/guides/QUICK-REFERENCE.md` - command reference.
- `docs/guides/WINDOWS-VS-TROUBLESHOOTING.md` - Windows compiler troubleshooting.
- `publication2/README.md` - manuscript package instructions.
- `publication2/ELASTOPLASTIC_INHERENT_STRAIN_COMPARISON.md` - diagnostic J2 elastoplastic vs. calibrated inherent-strain comparison.
- `results/li2023_case_006_mesh_dt_sensitivity.csv` - completed Case 6 mesh/time-step sensitivity matrix.

## Current Limitations

- The main validation workflow uses an inherent-strain surrogate for residual bending rather than fully coupled transient elastoplastic forming.
- The induction-skin option is a reduced thermal deposition model, not a complete electromagnetic field solver.
- Wall-clock runtimes are not consistently logged in all archived summaries.
- A representative Case 6 mesh/time-step sensitivity matrix is complete, but broader convergence over additional cases and refinement levels is still needed for publication-grade numerical verification.
- The active manuscript bibliography should be completed with the final Li et al. (2023) citation details before submission.

## Units

The project uses a consistent engineering unit system:

- length: mm
- time: s
- temperature: K or degrees C where explicitly noted
- stress/modulus: MPa
- force: N
- energy: J

## License and Citation

No license file is currently included. Add a project license before public distribution. For academic use, cite the manuscript and the Li et al. (2023) benchmark source once the bibliography details are finalized.
