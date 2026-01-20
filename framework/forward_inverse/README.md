# Forward & Inverse Problems (Line Heating)

This folder provides lightweight tools to:
- **Forward**: run FE with a heat input and read deflection results.
- **Inverse**: estimate heat input for a target deflection using the ELM surrogate.

## Forward (FE)
Use a JSON config (same format as `scripts/run_anywhere.py`).

Example:
- `python -m framework.forward_inverse.forward_fe --config config/fe_run_v10.json`

Output: JSON with `w_min_mm`, `w_max_mm`, and `w_max_abs_mm`.

## Inverse (Surrogate)
Solve for inputs that match a scalar deflection target.

Example:
- `python -m framework.forward_inverse.inverse_surrogate --target-deflection-mm 3.2`

Notes:
- The inverse currently targets **max |w|** only.
- Energy input is weakly identified because the training set does not vary energy.
- The line pattern output is a default evenly‑spaced list based on `passes` and `Ly`.

## Extending to full patterns
To infer actual line patterns (multiple lines, spacing, sequential timing) you should:
1) Include `heat_y_list`, `heat_mode`, and `pass_gap` in the training dataset.
2) Train a surrogate on those inputs.
3) Solve the inverse on the extended feature set.
