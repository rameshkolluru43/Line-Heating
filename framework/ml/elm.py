import numpy as np


def _activation(name: str):
    if name == "sigmoid":
        return lambda x: 1.0 / (1.0 + np.exp(-x))
    if name == "tanh":
        return np.tanh
    if name == "relu":
        return lambda x: np.maximum(0.0, x)
    raise ValueError(f"Unknown activation: {name}")


class ELM:
    def __init__(self, input_dim: int, hidden_dim: int, activation: str = "sigmoid") -> None:
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.activation_name = activation
        self.activation = _activation(activation)
        self.W = None
        self.b = None
        self.beta = None

    def initialize(self, rng: np.random.Generator, low: float = -1.0, high: float = 1.0) -> None:
        self.W = rng.uniform(low, high, size=(self.hidden_dim, self.input_dim))
        self.b = rng.uniform(low, high, size=(self.hidden_dim,))

    def fit(self, X: np.ndarray, y: np.ndarray, W: np.ndarray | None = None, b: np.ndarray | None = None) -> None:
        if W is not None:
            self.W = W
        if b is not None:
            self.b = b
        if self.W is None or self.b is None:
            raise ValueError("ELM weights not initialized")

        H = self.activation(X @ self.W.T + self.b)
        self.beta = np.linalg.pinv(H) @ y

    def predict(self, X: np.ndarray) -> np.ndarray:
        if self.W is None or self.b is None or self.beta is None:
            raise ValueError("ELM model not fitted")
        H = self.activation(X @ self.W.T + self.b)
        return H @ self.beta
