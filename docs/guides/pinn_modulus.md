# PINNs with Modulus (Thermal Line Heating)

This guide shows a minimal Modulus Sym setup to predict plate deflection from thermal line heating.

## Physics (template)
- Heat equation:
  $$\rho c_p \frac{\partial T}{\partial t} - k \nabla^2 T = Q(x,y,t)$$
- Plate equation (simplified coupling):
  $$D\nabla^4 w + \kappa_{th}(T - T_{ref}) = 0$$

This is a starting point; replace $\kappa_{th}$ with a proper thermoelastic moment model for higher fidelity.

## Where to edit
- Model entrypoint: [framework/pinns/modulus/line_heating_pinn.py](framework/pinns/modulus/line_heating_pinn.py)
- Parameters/config: [framework/pinns/modulus/conf/line_heating.yaml](framework/pinns/modulus/conf/line_heating.yaml)

## Suggested workflow
1) Tune the heat source parameters to match your FE runs (target $T_{max}$ and scan speed).
2) Validate deflection $w$ against FE outputs (e.g., max |w| from summary.json).
3) Add data loss terms if you want the PINN to fit both physics and FE data.

## Outputs
Use Modulus inferencers to sample $w(x,y,t)$ at the final time, then compute the deflection metric.
