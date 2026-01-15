"""Plotting utilities for prototype results.

Requires matplotlib. Functions return (fig, ax) to allow saving or further tweaks.
"""
from __future__ import annotations

from typing import Dict, Iterable, Sequence, Tuple

import numpy as np

try:
    import matplotlib.pyplot as plt
    from matplotlib import cm
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError("matplotlib is required for plotting") from exc


def plot_field_heatmap(x: np.ndarray, y: np.ndarray, field: np.ndarray, title: str, cmap: str = "viridis"):
    fig, ax = plt.subplots(figsize=(6, 4))
    # imshow expects (rows, cols) mapped to (y, x); origin lower keeps coordinates natural.
    im = ax.imshow(field, origin="lower", extent=[x.min(), x.max(), y.min(), y.max()], cmap=cmap, aspect="auto")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_title(title)
    fig.colorbar(im, ax=ax, shrink=0.8)
    return fig, ax


def plot_curvature_fields(x: np.ndarray, y: np.ndarray, kx: np.ndarray, ky: np.ndarray, kxy: np.ndarray):
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5))
    for ax, data, label in zip(
        axes,
        (kx, ky, kxy),
        ("kappa_x [1/mm]", "kappa_y [1/mm]", "kappa_xy [1/mm]"),
    ):
        im = ax.imshow(data, origin="lower", extent=[x.min(), x.max(), y.min(), y.max()], cmap="coolwarm", aspect="auto")
        ax.set_xlabel("x [mm]")
        ax.set_ylabel("y [mm]")
        ax.set_title(label)
        fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    return fig, axes


def plot_field_surface(x: np.ndarray, y: np.ndarray, field: np.ndarray, title: str):
    """3D surface plot of a scalar field (e.g., deflection or curvature)."""
    X, Y = np.meshgrid(x, y)
    fig = plt.figure(figsize=(6, 4))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(X, Y, field, cmap=cm.viridis, linewidth=0, antialiased=True)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_zlabel(title)
    ax.set_title(title)
    fig.colorbar(surf, shrink=0.6, aspect=10)
    return fig, ax


def plot_curvature_surfaces(x: np.ndarray, y: np.ndarray, kx: np.ndarray, ky: np.ndarray, kxy: np.ndarray):
    """3D surface plots for curvature components."""
    X, Y = np.meshgrid(x, y)
    titles = ["kappa_x [1/mm]", "kappa_y [1/mm]", "kappa_xy [1/mm]"]
    data = [kx, ky, kxy]
    figs_axes = []
    for title, field in zip(titles, data):
        fig = plt.figure(figsize=(6, 4))
        ax = fig.add_subplot(111, projection="3d")
        surf = ax.plot_surface(X, Y, field, cmap=cm.coolwarm, linewidth=0, antialiased=True)
        ax.set_xlabel("x [mm]")
        ax.set_ylabel("y [mm]")
        ax.set_zlabel(title)
        ax.set_title(title)
        fig.colorbar(surf, shrink=0.6, aspect=10)
        figs_axes.append((fig, ax))
    return figs_axes


def plot_lines_overlay(lines: Sequence[Dict[str, object]], plate_length: float, plate_width: float):
    """Plot heating lines on the plate footprint."""
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.set_xlim(0, plate_length)
    ax.set_ylim(0, plate_width)
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("y [mm]")
    ax.set_title("Heating lines")
    for ln in lines:
        pts = ln.get("points", [])
        if len(pts) < 2:
            continue
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, label=ln.get("name", ln.get("id", "line")))
        # draw direction arrow near end
        ax.annotate("", xy=(xs[-1], ys[-1]), xytext=(xs[-2], ys[-2]), arrowprops=dict(arrowstyle="->", color="black"))
    if lines:
        ax.legend()
    ax.set_aspect("equal", adjustable="box")
    return fig, ax


def plot_pass_energy(pass_results: Iterable[Dict[str, float]]):
    labels = []
    energies = []
    for pr in pass_results:
        labels.append(pr.get("pass_id", "?"))
        energies.append(pr.get("line_energy_J_per_mm", 0.0))
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(labels, energies)
    ax.set_ylabel("Line energy [J/mm]")
    ax.set_title("Per-pass line energy")
    return fig, ax


def plot_shrinkage(pass_results: Iterable[Dict[str, float]]):
    labels = []
    eps = []
    for pr in pass_results:
        labels.append(pr.get("pass_id", "?"))
        eps.append(pr.get("shrinkage_eps", 0.0))
    fig, ax = plt.subplots(figsize=(5, 3))
    ax.bar(labels, eps)
    ax.set_ylabel("Shrinkage strain ε")
    ax.set_title("Per-pass shrinkage")
    return fig, ax


def plot_deflection_profiles_along_lines(
    x: np.ndarray,
    y: np.ndarray,
    w: np.ndarray,
    lines: Sequence[Dict[str, object]],
):
    """Plot deflection w(x) sampled along each heating line using nearest-y row.

    For straight lines parallel to x, we pick the closest grid row to the line's
    y-offset and plot w versus x.
    """
    fig, ax = plt.subplots(figsize=(6, 4))
    for ln in lines:
        pts = ln.get("points", [])
        if len(pts) < 2:
            continue
        y_line = pts[0][1]
        # nearest grid row index for this line's y
        j = int(np.abs(y - y_line).argmin())
        ax.plot(x, w[j, :], label=ln.get("name", ln.get("id", "line")))
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("Deflection w [mm]")
    ax.set_title("Deflection profiles along heating lines")
    if lines:
        ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig, ax


def plot_deflection_profiles_comparison(
    x: np.ndarray,
    y: np.ndarray,
    w_a: np.ndarray,
    w_b: np.ndarray,
    lines: Sequence[Dict[str, object]],
    label_a: str,
    label_b: str,
):
    """Overlay deflection profiles for two scenarios along the same lines."""
    fig, ax = plt.subplots(figsize=(7.5, 4))
    fig.subplots_adjust(right=0.75)  # reserve space for an outside legend
    for ln in lines:
        pts = ln.get("points", [])
        if len(pts) < 2:
            continue
        y_line = pts[0][1]
        j = int(np.abs(y - y_line).argmin())
        base_name = ln.get("name", ln.get("id", "line"))
        ax.plot(x, w_a[j, :], label=f"{base_name} ({label_a})")
        ax.plot(x, w_b[j, :], linestyle="--", label=f"{base_name} ({label_b})")
    ax.set_xlabel("x [mm]")
    ax.set_ylabel("Deflection w [mm]")
    ax.set_title("Deflection profiles comparison")
    if lines:
        ax.legend(
            loc="upper left",
            bbox_to_anchor=(1.02, 1.0),
            borderaxespad=0.0,
            fontsize=8,
            framealpha=0.9,
        )
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig, ax
