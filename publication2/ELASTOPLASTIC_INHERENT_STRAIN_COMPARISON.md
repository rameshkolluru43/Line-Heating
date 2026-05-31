# Elastoplastic vs. Inherent-Strain Comparison: Work Completed

## Purpose

This note records the work completed to fill the manuscript table comparing the calibrated inherent-strain surrogate with the optional J2 elastoplastic mechanics path for one representative Li2023 benchmark case.

The goal was to support the reviewer-facing statement:

> One representative Li2023 case is compared using the calibrated inherent-strain model and the optional J2 elastoplastic model. The comparison reports residual deflection, peak temperature, and a plasticity indicator.

## Representative Case Selected

Li2023 Case 6 was used as the representative comparison case.

- Velocity: 11 mm/s
- Energy input: 600 J/mm
- Thickness: 14 mm
- Passes: 2
- Mesh: baseline Li2023 mesh, `h = 20 mm`, `h_refine = 5 mm`
- Time step: `dt = 2 s`
- Boundary condition: `centerline_fixed`
- Heat source: moving Gaussian, sequential passes

Case 6 was chosen because it is a calibrated multi-pass Li2023 case and already exists in the archived validation dataset.

## Data Generated

The comparison data are stored in:

- `results/li2023_case_006_elastoplastic_inherent_comparison.csv`
- `results/li2023_case_006_v9_table2_extended/summary.json`
- `results/li2023_case_006_j2_elastoplastic_strong_compare/summary.json`

The J2 elastoplastic run configuration is stored in:

- `results/li2023_case_006_j2_elastoplastic_strong_compare.json`

## Main Results

| Model | `|w|max` (mm) | `Tpeak` (K) | Plasticity indicator |
|---|---:|---:|---|
| Inherent strain, calibrated | 7.722 | 1176.9 | `eps0 = 4.7736e-2`; no resolved plastic-strain field |
| Elastoplastic J2, strong-coupled | 0.096 | 1176.9 | `epbar_max = 5.8846e-2`; mean `4.3067e-4`; p95 `2.9913e-3`; active elements `5342/36780` = `14.5%` |

## Interpretation

The strong-coupled J2 run confirms that the thermal cycle produces localized yielding. However, the residual deflection from the current optional J2 path is much smaller than the calibrated inherent-strain result.

Therefore, the comparison should be presented as a diagnostic spot check, not as independent elastoplastic validation of the inherent-strain surrogate.

Recommended manuscript wording:

> The J2 run advances equivalent plastic strain through the saved thermal history using the same mesh and thermal loading as the calibrated Case 6 run. It confirms that the thermal cycle can trigger localized yielding, but the present optional elastoplastic path does not reproduce the calibrated residual-deflection magnitude. The comparison is therefore retained as a diagnostic verification item rather than treated as independent validation of the inherent-strain calibration.

## Code Changes Made

The solver was updated in:

- `thermo_fem/python/run_coupled_3d.py`

Completed solver changes:

- Made the `--strong-coupling` elastoplastic branch reachable.
- Advanced J2 plastic state through the saved thermal history when `--use-elastoplastic --strong-coupling` is enabled.
- Stored equivalent plastic-strain summary metrics in `summary.json`:
  - `plastic_epbar_min`
  - `plastic_epbar_max`
  - `plastic_epbar_mean`
  - `plastic_epbar_p95`
  - `plastic_elements_active`
  - `plastic_elements_total`

## Manuscript Updates Made

Updated manuscript files:

- `publication2/sections/validation.tex`
- `publication2/sections/discussion.tex`
- `publication2/sections/conclusion.tex`

Completed manuscript changes:

- Added a new diagnostic comparison table in the validation section.
- Updated discussion language so the elastoplastic comparison is no longer described as missing.
- Clarified that the J2 result is diagnostic and does not yet establish physical equivalence with the calibrated inherent-strain model.
- Updated the conclusion to state that the J2 spot check has been completed, while full elastoplastic validation still requires further development.

## Verification

The following checks were completed:

- Strong-coupled J2 Case 6 run completed successfully.
- Plastic-strain summary metrics were written to the J2 `summary.json`.
- `publication2/main.tex` compiled successfully with `latexmk -pdf main.tex`.
- No linter errors were reported for the modified solver and manuscript files.

Existing LaTeX overfull warnings remain in unrelated sections, but the new comparison table compiles.

