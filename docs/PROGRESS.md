# Progress Made

## Planner & Post-Processing
- Implemented inverse planner using Nelder–Mead and solver wrapper.
- Added G-code exporter from plan JSON.
- Added example planner config.
- Added CSV logging for optimization evaluations.
- Added final-report-only option to suppress intermediate reports.

## Calibration & Solver Enhancements
- Calibrated inherent-strain scaling and pass/energy adjustments.
- Added Gaussian beta control and energy-dependent tuning.
- Added elastoplastic J2 option with consistent tangent.
- Added adaptive time stepping and strong coupling option.

## Documentation & Reporting
- Created Li2023 update summary and full LaTeX report.
- Added process LaTeX document for the planner run.
- Generated and stored PDFs for reports.

## Runs Completed
- Li2023 four-case calibration (final tuned set).
- Planner demo run with logs, report, and exported G-code.
