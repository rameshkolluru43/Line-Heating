# DeepXDE PINN (Line Heating)

This is a DeepXDE PINN template for a coupled heat + plate deflection model.

## Run
Use the standard Python entrypoint and pass parameters as needed.

Key outputs:
- `w_min_mm`, `w_max_mm`, `w_max_abs_mm` printed to stdout
- `pinn_results.npz` containing a grid of $w(x,y)$ at final time

## Notes
- The thermal‑to‑bending coupling uses a simplified coefficient `kappa_th`.
- For accuracy, replace with a physics‑based thermoelastic moment model.
