# Forward & Inverse Problems (Line Heating)

This guide explains forward and inverse usage in this repo.

## Forward problem
**Given**: heat input or temperature target + quench settings.  
**Return**: deflection metrics (max |w|, camber).

Use the FE runner with a config file and read `summary.json`.

- Entrypoint: [framework/forward_inverse/forward_fe.py](framework/forward_inverse/forward_fe.py)
- Config format: same as `scripts/run_anywhere.py`

## Inverse problem (surrogate)
**Given**: target deflection (scalar).  
**Return**: estimated speed and energy + a default line pattern.

- Entrypoint: [framework/forward_inverse/inverse_surrogate.py](framework/forward_inverse/inverse_surrogate.py)

## Limitations
- Current dataset does not vary energy, so energy estimates are weakly constrained.
- The inverse is for scalar deflection, not a full spatial pattern.

## Next steps
- Add `heat_y_list`, `heat_mode`, `pass_gap`, and energy to the dataset.
- Train on multiple patterns.
- Use inverse optimization on the expanded feature set for true line‑pattern recovery.
