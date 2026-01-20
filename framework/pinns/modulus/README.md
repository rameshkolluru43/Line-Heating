# Modulus PINN (Line Heating)

This folder contains a Modulus Sym starter template for a coupled heat + plate deflection PINN.

## What it does
- Solves the transient heat equation for $T(x,y,t)$ with a moving Gaussian heat source.
- Solves a simplified plate equation for deflection $w(x,y,t)$ driven by temperature.
- Uses boundary conditions $T=T_{inf}$ and $w=0$ on the edges; initial condition $T=T_{ref}$ at $t=0$.

## Files
- `line_heating_pinn.py`: Modulus entrypoint.
- `conf/line_heating.yaml`: Default configuration and parameters.

## How to run (after installing Modulus Sym)
- Launch the solver with the Modulus entrypoint and config.
- Adjust parameters in `conf/line_heating.yaml` for your heating velocity, geometry, and material constants.

## Notes
- The plate equation uses a simplified thermal coupling coefficient `kappa_th`. Replace this with a physics-based thermal moment model when ready.
- Add more boundary conditions (e.g., corner pins or clamped edges) by extending constraints in `line_heating_pinn.py`.
- For comparison against FE, add a validation dataset using `PointwiseValidator`.
