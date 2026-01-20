import argparse
from pathlib import Path
import numpy as np


def load_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, delimiter=",", skiprows=1, usecols=(0, 1, 2, 3, 4))
    data = np.atleast_2d(data)
    data = np.nan_to_num(data, nan=0.0)
    X = data[:, :4]
    y = data[:, 4]
    return X, y


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean((y_true - y_pred) ** 2))


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=str)
    parser.add_argument("--model", required=True, type=str)
    args = parser.parse_args()

    data_path = Path(args.data)
    model_path = Path(args.model)

    X, y = load_csv(data_path)

    model = np.load(model_path, allow_pickle=True)
    W = model["W"]
    b = model["b"]
    beta = model["beta"]
    mean = model["mean"]
    std = model["std"]
    activation = str(model["activation"])

    Xs = (X - mean) / std

    if activation == "sigmoid":
        H = 1.0 / (1.0 + np.exp(-(Xs @ W.T + b)))
    elif activation == "tanh":
        H = np.tanh(Xs @ W.T + b)
    elif activation == "relu":
        H = np.maximum(0.0, Xs @ W.T + b)
    else:
        raise ValueError(f"Unknown activation: {activation}")

    y_pred = H @ beta

    print(f"MSE: {mse(y, y_pred):.6f}")
    print(f"R2:  {r2(y, y_pred):.6f}")


if __name__ == "__main__":
    main()
