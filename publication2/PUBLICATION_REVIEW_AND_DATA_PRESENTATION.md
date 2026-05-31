# Publication Review and Data Presentation Plan

## Executive Verdict

The strongest publishable framing for `publication2` is:

> A reproducible 3D thermo-mechanical FEM and inherent-strain workflow for ship plate line heating, validated on the available Li et al. Q345 benchmark subset, with a process-scheduling study showing that sequential thermal cycles are essential for multi-pass forming accuracy.

This is stronger than framing the paper as an induction-heating or inverse-planning paper. The induction skin-depth source and inverse workflow should be presented as implemented extensions or demonstrations unless full validation data are added.

## Publication Readiness

| Area | Current Status | Risk | Recommendation |
|---|---:|---:|---|
| Validation metrics | Strong for available 11-case subset | Medium | Keep calibration-anchor and non-anchor validation metrics separate. |
| Surface figures | Good journal-style panels exist | Medium | Use only one Li2023 surface panel in the main paper; move remaining case panels to supplementary material. |
| Process comparison | Strong contribution | Low | Emphasize the 50% underprediction from collapsed multi-pass scheduling and recovery by sequential scheduling. |
| Keel demonstration | Useful application example | Medium | State clearly that it is not experimental validation without target/measured keel data. |
| Inherent-strain model | Effective but surrogate-based | High | Add fitted law, parameters, objective, and sensitivity if space permits. |
| References | Better than earlier draft but Li2023 still incomplete | High | Complete the benchmark citation before submission. |
| Numerical verification | Case 6 mesh/time-step matrix completed | Medium | Report it as a representative spot check; avoid general convergence claims until more cases/refinement levels are run. |
| Induction model | Skin-depth source implemented | Medium | Describe as an electromagnetic heating approximation, not a full Maxwell coil-field solver. |

## Best Data Representation for Journal Submission

### Main Paper Figures

Use a compact main figure set:

1. **Validation parity plot**: FEM vs experiment with calibration anchors and non-anchor validation cases marked separately.
2. **Residual plot**: percent error by case, highlighting the speed-sweep bias in cases 1--5.
3. **Speed-sweep plot**: experimental and FEM deflection vs speed for cases 1--5.
4. **Process-comparison plot**: moving torch vs collapsed line source vs sequential line source for multi-pass cases.
5. **Representative Li2023 FEM surface panel**: use Case 90 only in the main paper.
6. **Keel-plate demonstration panel**: heating plan, residual deflection, curvature/camber, and one amplified 3D surface.

### Supplementary Figures

Move these to supplementary material:

- Li2023 surface panels for cases 1--7 and 87--89.
- Extra temperature/deflection-only plots.
- Extra inverse-planning diagrams unless inverse planning becomes a central validated contribution.
- Additional keel snapshots not directly tied to a quantitative claim.

## FEM Surface Figure Rules

For publication, FEM surfaces should be quantitative panels, not standalone 3D screenshots.

### Temperature

- Show **top-view contour of peak or selected-time top-surface temperature**.
- Label colorbar as `Temperature (K)` or `Temperature (C)`.
- Overlay heating path and direction arrow.
- Use the same temperature scale for comparable cases.
- If the saved field is final temperature rather than peak temperature, label it as final temperature and do not call it peak.

### Residual Deflection

- Show **top-view filled contour of residual transverse displacement** after cooling.
- Label colorbar as `Residual deflection w (mm)`.
- Use a diverging colormap centered at zero if both positive and negative deflection occur.
- Mark maximum/minimum locations when helpful.
- Use consistent sign convention throughout the text and captions.

### Curvature

- Use curvature maps mainly for the keel demonstration.
- Label as `Mean curvature (1/m)`, `Longitudinal curvature (1/m)`, or `Transverse curvature (1/m)`.
- State how curvature is computed from the deflection surface.
- If smoothing is used, report it in the caption or methods.
- Prefer section profiles for quantitative interpretation because curvature is a second derivative and can be noisy.

### 3D Surface

- Use only once per major case.
- State deformation scale factor in the caption, e.g. `out-of-plane deformation amplified 20x`.
- Do not use the 3D surface for numerical validation; use contours and profiles for claims.

## Manuscript-Level Critical Review

### Strengths

- The validation subset is presented honestly with calibration and non-anchor cases separated.
- The process-comparison result is compelling and easy to publish: collapsing multi-pass thermal cycles produces about 50% error, while sequential scheduling recovers the benchmark response.
- The current figure package includes parity, residual, speed-sweep, process-comparison, and surface panel plots, which are the right evidence types for reviewers.
- The repository-oriented reproducibility package is a strong point for a numerical-method paper.

### Major Issues to Fix Before Submission

- Complete the Li et al. 2023 bibliographic entry in `references.bib`.
- Avoid saying “broad validation”; use “available benchmark subset” because rows 8--86 are missing.
- Keep the keel section framed as demonstration unless target or measured keel data are added.
- Add a clearer inherent-strain calibration subsection with fitted law, parameters, objective function, and sensitivity.
- Make sure the temperature field panel is accurately labeled as peak, selected-time, or final temperature.
- Do not overclaim the induction skin-depth source as a full electromagnetic solver.
- Use the completed Case 6 mesh/time-step matrix as a representative discretization spot check; do not generalize it as full convergence for all cases.

## Recommended Target Journal

Best near-term target: **Journal of Ship Production and Design**.

Why: the paper is about ship plate forming, process simulation, validation, and production planning. This is a better match than a mechanics-only journal unless the paper is expanded with full elastoplastic residual-stress validation.

Secondary target: **Ocean Engineering**, if the introduction and discussion are strengthened around naval architecture and ship-production engineering relevance.

Less suitable: **Marine Structures**, unless the paper is reframed around structural mechanics and residual deformation physics.

## Submission Action List

1. Keep only one representative Li2023 surface panel in the main paper.
2. Move remaining case-wise surface panels to supplementary material.
3. Complete the Li2023 reference and add 10--15 more line-heating/inherent-strain references.
4. Add an inherent-strain calibration subsection with exact law and fitted parameters.
5. Add a short numerical-verification table from the scaffold, but do not claim convergence until repeated runs are complete.
6. Add a note that `induction_skin` is a skin-depth electromagnetic heating approximation, not a coil-field Maxwell solver.
7. Rebuild `publication2/main.pdf` and perform page-by-page visual QA before submission.
