# Line-Heating Prediction Framework (ISSA–ELM)

This folder contains a self-contained framework to reproduce the paper’s data-driven predictor:

- Generate a dataset from FE simulations (or reuse existing results).
- Train a baseline ELM.
- Train an ISSA-optimized ELM (ISSA–ELM).
- Compare metrics (MSE, $R^2$, MAE) and convergence curves.

## Folder Structure

```
framework/
├── fe_dataset/          # Dataset schema + notes
├── ml/                  # ELM + ISSA implementation
└── README.md            # This file
```

## Dataset Format

Use a single CSV with columns:

```
speed_mm_s,energy_J_per_mm,thickness_mm,passes,deformation_mm
```

See [fe_dataset/README.md](fe_dataset/README.md) for details and a schema.

## Quick Start

1) Prepare a CSV dataset (from FE runs or experiments).

2) Train baseline ELM and ISSA–ELM:

```
/opt/homebrew/bin/python3.11 framework/ml/train.py \
  --data framework/fe_dataset/dataset.csv \
  --hidden 20 \
  --pop 30 \
  --iters 40
```

3) Evaluate saved models:

```
/opt/homebrew/bin/python3.11 framework/ml/evaluate.py \
  --data framework/fe_dataset/dataset.csv \
  --model framework/ml/models/issa_elm_model.npz
```

## Notes

- This framework uses NumPy only (no external ML libraries).
- It follows the paper’s workflow: ELM + ISSA optimization of input weights and biases.
- You can plug in your FE-generated dataset from the existing solver.
