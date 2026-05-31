# Ship Plate Line Heating — Publishable Manuscript

This folder contains the LaTeX source for a **publishable manuscript** that describes the 3D thermo-mechanical FEM workflow for ship-plate line heating, its validation against Li et al. (2023) benchmark cases, and keel-plate demonstrations. All content is derived from the project’s data, reports, and documentation.

## Structure

- **`main.tex`** — Master file; includes sections and sets up document class, packages, and paths.
- **`sections/`** — Section files: abstract, introduction, methods, validation, results, discussion, conclusion, appendix (reproducibility).
- **`references.bib`** — BibTeX database (fill in exact Li et al. 2023 citation when submitting).
- **`figures/`** — Self-contained local figures used by the manuscript.

## Building the PDF

**From the repository root:**

```bash
cd publication2
make
```

Or manually:

```bash
cd publication2
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Using `latexmk` (if installed):

```bash
cd publication2
latexmk -pdf main.tex
```

## Figure paths

Figures are loaded from the local `figures/` directory in this package:

- `figures/li2023_*.png` — generated validation plots (parity, residual, speed sweep, and process comparison). Regenerate with `scripts/make_publication_validation_figures.py`.
- `figures/li2023_case*_surface_panel.png` — journal-style Li2023 FEM response panels; use one representative case in the main paper and keep the rest as supplementary material.
- `figures/keel_practical_*.png` and `figures/keel_practical_surface_panel.png` — keel-plate demonstration panels.

If any result-derived PNGs are missing, regenerate them by running the corresponding simulation and figure-generation scripts from the repo root, then copy the selected publication figures into `publication2/figures/`.

## Customization for submission

1. **Author/affiliation:** Edit `main.tex` (title, author, affiliation blocks if needed).
2. **References:** Complete the Li et al. (2023) entry in `references.bib` with journal, volume, pages, DOI.
3. **Journal template:** For a specific journal, replace the `article` setup in `main.tex` with the journal’s class (e.g. `elsarticle`, `sagej`, etc.) and adjust margins/packages as required.
4. **Figures:** Keep the main paper figure set small: one validation surface panel, parity/residual/speed-sweep plots, one process-comparison plot, and one keel demonstration panel. Move remaining case-wise surface panels to supplementary material.

## Data and reproducibility

- Validation tables (Li2023, keel-plate) are typed from the project’s `summary.json` outputs and existing reports.
- Executed verification artifacts are written by `scripts/execute_planned_work_items.py` to `results/velocity_dependent_eps0_calibration.*`, `results/keel_thermal_unit_audit.*`, `results/verification_energy_scaffold.*`, and `results/planned_work_execution_status.json`.
- The representative Case 6 mesh/time-step sensitivity matrix is stored in `results/li2023_case_006_mesh_dt_sensitivity.csv`.
- The diagnostic Case 6 J2 elastoplastic vs. calibrated inherent-strain comparison is summarized in `ELASTOPLASTIC_INHERENT_STRAIN_COMPARISON.md` and stored in `results/li2023_case_006_elastoplastic_inherent_comparison.csv`.
- Electromagnetic induction heating beyond prescribed surface flux is available through `--heat-source-mode induction_skin`; the Li2023 runner exposes it through `scripts/run_li2023_induction_cases.py --heat-source-mode induction_skin`.
- Reproducibility commands are listed in the appendix; run them from the **repository root**.

## Cleaning

```bash
make cleanaux   # Remove .aux, .bbl, .log, etc.
make clean      # Also remove main.pdf
```
