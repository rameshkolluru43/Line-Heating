# FE Dataset Notes

This folder defines the dataset format used by the ISSA–ELM framework.

## Expected CSV Columns

```
speed_mm_s,energy_J_per_mm,thickness_mm,passes,deformation_mm
```

- `speed_mm_s`: heat source travel speed
- `energy_J_per_mm`: line energy input
- `thickness_mm`: plate thickness
- `passes`: number of heating passes
- `deformation_mm`: scalar deformation metric (e.g., max out-of-plane deflection after cooling)

## How to Build the Dataset

1) Run FE simulations over a parameter grid.
2) Extract a single deformation scalar from each run (e.g., max |w| from `summary.json`).
3) Assemble all runs into a single CSV.

## Example Row

```
10,800,10,1,6.35
```

This means: speed = 10 mm/s, energy = 800 J/mm, thickness = 10 mm, passes = 1, deformation = 6.35 mm.
