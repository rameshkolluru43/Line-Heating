import argparse
from pathlib import Path
import numpy as np

from .elm import ELM
from .issa import issa_optimize_elm


def load_csv(path: Path) -> tuple[np.ndarray, np.ndarray]:
    data = np.loadtxt(path, delimiter=",", skiprows=1, usecols=(0, 1, 2, 3, 4))
    data = np.atleast_2d(data)
    data = np.nan_to_num(data, nan=0.0)
    X = data[:, :4]
    y = data[:, 4]
    return X, y


def standardize(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    return (X - mean) / std, mean, std


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean((y_true - y_pred) ** 2))


def r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - y_true.mean()) ** 2)
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, type=str)
    parser.add_argument("--hidden", type=int, default=20)
    parser.add_argument("--pop", type=int, default=30)
    parser.add_argument("--iters", type=int, default=40)
    parser.add_argument("--activation", type=str, default="sigmoid")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data_path = Path(args.data)
    X, y = load_csv(data_path)
    Xs, mean, std = standardize(X)

    input_dim = Xs.shape[1]

    # Baseline ELM
    rng = np.random.default_rng(args.seed)
    elm = ELM(input_dim, args.hidden, activation=args.activation)
    elm.initialize(rng)
    elm.fit(Xs, y)
    y_pred = elm.predict(Xs)
    base_mse = mse(y, y_pred)
    base_r2 = r2(y, y_pred)

    # ISSA–ELM
    issa_res = issa_optimize_elm(
        Xs,
        y,
        hidden_dim=args.hidden,
        pop_size=args.pop,
        iters=args.iters,
        activation=args.activation,
        seed=args.seed,
    )
    elm_issa = ELM(input_dim, args.hidden, activation=args.activation)
    elm_issa.fit(Xs, y, W=issa_res["W"], b=issa_res["b"])
    y_pred_issa = elm_issa.predict(Xs)
    issa_mse = mse(y, y_pred_issa)
    issa_r2 = r2(y, y_pred_issa)

    print("Baseline ELM:")
    print(f"  MSE: {base_mse:.6f}")
    print(f"  R2:  {base_r2:.6f}")
    print("ISSA–ELM:")
    print(f"  MSE: {issa_mse:.6f}")
    print(f"  R2:  {issa_r2:.6f}")

    out_dir = Path(__file__).parent / "models"
    out_dir.mkdir(parents=True, exist_ok=True)

    np.savez(
        out_dir / "baseline_elm_model.npz",
        W=elm.W,
        b=elm.b,
        beta=elm.beta,
        mean=mean,
        std=std,
        activation=args.activation,
    )
    np.savez(
        out_dir / "issa_elm_model.npz",
        W=elm_issa.W,
        b=elm_issa.b,
        beta=elm_issa.beta,
        mean=mean,
        std=std,
        activation=args.activation,
        history=issa_res["history"],
    )


if __name__ == "__main__":
    main()
