# PINNs with DeepXDE (Thermal Line Heating)

This guide provides a minimal DeepXDE PINN setup for line heating.

## Physics (template)
- Heat equation:
  $$\rho c_p \frac{\partial T}{\partial t} - k \nabla^2 T = Q(x,y,t)$$
- Plate equation (simplified coupling):
  $$D\nabla^4 w + \kappa_{th}(T - T_{ref}) = 0$$

## Files
- Entrypoint: [framework/pinns/deepxde/line_heating_pinn.py](framework/pinns/deepxde/line_heating_pinn.py)
- README: [framework/pinns/deepxde/README.md](framework/pinns/deepxde/README.md)

## Suggested workflow
1) Match the heat input to your FE runs (target $T_{max}$, scan speed).
2) Train for sufficient epochs (PINNs may need many).
3) Evaluate $w$ at $t_{final}$ to get deflection.

## Next steps
- Add data‑based constraints from FE runs.
- Replace `kappa_th` with a calibrated thermoelastic coupling.
