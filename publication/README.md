# Ship Plate Line Heating — Publishable Manuscript

This folder contains the LaTeX source for a **publishable manuscript** that describes the 3D thermo-mechanical FEM workflow for ship-plate line heating, its validation against Li et al. (2023) benchmark cases, and keel-plate demonstrations. All content is derived from the project’s data, reports, and documentation.

## Structure

- **`main.tex`** — Master file; includes sections and sets up document class, packages, and paths.
- **`sections/`** — Section files: abstract, introduction, methods, validation, results, discussion, conclusion, appendix (reproducibility).
- **`references.bib`** — BibTeX database (fill in exact Li et al. 2023 citation when submitting).
- **`figures/`** — Optional local figures; main figures are in `../results/...` (see below).

## Building the PDF

**From the repository root:**

```bash
cd publication
make
```

Or manually:

```bash
cd publication
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Using `latexmk` (if installed):

```bash
cd publication
latexmk -pdf main.tex
```

## Figure paths

Figures are loaded from the **results** directory of the main project:

- `../results/li2023_case_090_v8_full_four_cases_lowE_single/*.png` — Li2023 Case 90 (temperature, deflection, mesh, camber).
- `../results/keel_plate_practical/*.png` — Keel-plate practical (deflection, curvature, heating profiles).

If any of these result folders or PNGs are missing, regenerate them by running the corresponding simulations from the repo root (see appendix in the manuscript or the main project README). The manuscript is intended to be built **from inside the repo** so that `../results/` resolves correctly.

## Customization for submission

1. **Author/affiliation:** Edit `main.tex` (title, author, affiliation blocks if needed).
2. **References:** Complete the Li et al. (2023) entry in `references.bib` with journal, volume, pages, DOI.
3. **Journal template:** For a specific journal, replace the `article` setup in `main.tex` with the journal’s class (e.g. `elsarticle`, `sagej`, etc.) and adjust margins/packages as required.
4. **Figures:** To make a self-contained submission package, copy or symlink the needed PNGs from `../results/...` into `figures/` and change the figure paths in `sections/validation.tex` and `sections/results.tex` to `figures/...`.

## Data and reproducibility

- Validation tables (Li2023, keel-plate) are typed from the project’s `summary.json` outputs and existing reports.
- Reproducibility commands are listed in the appendix; run them from the **repository root**.

## Cleaning

```bash
make cleanaux   # Remove .aux, .bbl, .log, etc.
make clean      # Also remove main.pdf
```
