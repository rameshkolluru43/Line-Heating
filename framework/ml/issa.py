import numpy as np
from .elm import ELM


def issa_optimize_elm(
    X: np.ndarray,
    y: np.ndarray,
    hidden_dim: int,
    pop_size: int = 30,
    iters: int = 40,
    bounds: tuple[float, float] = (-1.0, 1.0),
    activation: str = "sigmoid",
    seed: int = 42,
) -> dict:
    """Optimize ELM input weights and biases using improved SSA (ISSA).

    Returns dict with best W, b, history.
    """
    rng = np.random.default_rng(seed)
    low, high = bounds

    input_dim = X.shape[1]
    dim = hidden_dim * input_dim + hidden_dim

    # Population: each salp encodes flattened [W, b]
    pop = rng.uniform(low, high, size=(pop_size, dim))

    def decode(vec: np.ndarray):
        W = vec[: hidden_dim * input_dim].reshape(hidden_dim, input_dim)
        b = vec[hidden_dim * input_dim :]
        return W, b

    def fitness(vec: np.ndarray) -> float:
        W, b = decode(vec)
        model = ELM(input_dim, hidden_dim, activation=activation)
        model.fit(X, y, W=W, b=b)
        pred = model.predict(X)
        return float(np.mean((pred - y) ** 2))

    # Evaluate initial population
    scores = np.array([fitness(v) for v in pop])
    best_idx = int(np.argmin(scores))
    food = pop[best_idx].copy()
    best_score = scores[best_idx]

    history = [best_score]

    for l in range(1, iters + 1):
        # attenuation factor
        A_l = np.exp(-2.0 * (l / iters) ** 2)
        # adaptive inertia (cosine decay)
        w = 0.5 * (1.0 + np.cos(np.pi * l / iters))

        # Update leader
        c1 = 2.0 * np.exp(-((4.0 * l / iters) ** 2))
        c2 = rng.random(dim)
        c3 = rng.random(dim)

        leader = pop[0].copy()
        leader = np.where(
            c3 < 0.5,
            A_l * (food + c1 * ((high - low) * c2 + low)),
            A_l * (food - c1 * ((high - low) * c2 + low)),
        )
        pop[0] = np.clip(leader, low, high)

        # Update followers
        for i in range(1, pop_size):
            pop[i] = w * 0.5 * (pop[i] + pop[i - 1])
            pop[i] = np.clip(pop[i], low, high)

        # Evaluate
        scores = np.array([fitness(v) for v in pop])
        idx = int(np.argmin(scores))
        if scores[idx] < best_score:
            best_score = scores[idx]
            food = pop[idx].copy()

        history.append(best_score)

    W_best, b_best = decode(food)
    return {
        "W": W_best,
        "b": b_best,
        "best_mse": best_score,
        "history": np.array(history),
    }
