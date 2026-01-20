"""DeepXDE PINN for coupled heat + plate deflection (template).

Solves:
- Heat: rho*cp*dT/dt - k*(d2T/dx2 + d2T/dy2) = Q(x,y,t)
- Plate: D*∇^4 w + kappa_th*(T - T_ref) = 0 (simplified coupling)

Outputs: T(x,y,t), w(x,y,t)
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
import deepxde as dde


@dataclass
class Params:
    Lx: float = 1000.0
    Ly: float = 1000.0
    thickness: float = 12.0
    rho: float = 7.85e-6
    cp: float = 500.0
    k: float = 0.045
    E: float = 210000.0
    nu: float = 0.3
    alpha: float = 1.2e-5
    T_ref: float = 293.0
    T_inf: float = 293.0
    q0: float = 8.4
    r0: float = 25.0
    v: float = 10.0
    heat_y: float = 500.0
    t_final: float = 400.0
    kappa_th: float = 1.0


def build_pde(p: Params):
    def pde(x, y):
        T = y[:, 0:1]
        w = y[:, 1:2]

        x_pos = x[:, 0:1]
        y_pos = x[:, 1:2]
        t = x[:, 2:3]

        D = p.E * p.thickness**3 / (12.0 * (1.0 - p.nu**2))

        x0 = p.v * t
        y0 = p.heat_y
        Q = p.q0 * dde.backend.exp(-((x_pos - x0) ** 2 + (y_pos - y0) ** 2) / (2.0 * p.r0**2))

        T_t = dde.grad.jacobian(T, x, i=0, j=2)
        T_xx = dde.grad.hessian(T, x, i=0, j=0)
        T_yy = dde.grad.hessian(T, x, i=0, j=1)

        w_xx = dde.grad.hessian(w, x, i=0, j=0)
        w_yy = dde.grad.hessian(w, x, i=0, j=1)
        w_xxxx = dde.grad.hessian(w_xx, x, i=0, j=0)
        w_yyyy = dde.grad.hessian(w_yy, x, i=0, j=1)
        w_xxyy = dde.grad.hessian(w_xx, x, i=0, j=1)

        heat_eq = p.rho * p.cp * T_t - p.k * (T_xx + T_yy) - Q
        plate_eq = D * (w_xxxx + 2.0 * w_xxyy + w_yyyy) + p.kappa_th * (T - p.T_ref)

        return [heat_eq, plate_eq]

    return pde


def build_model(p: Params, layers: list[int], activation: str, initializer: str, lr: float):
    geom = dde.geometry.Rectangle([0.0, 0.0], [p.Lx, p.Ly])
    timedomain = dde.geometry.TimeDomain(0.0, p.t_final)
    geomtime = dde.geometry.GeometryXTime(geom, timedomain)

    def boundary(_x, on_boundary):
        return on_boundary

    bc_T = dde.icbc.DirichletBC(geomtime, lambda _x: p.T_inf, boundary, component=0)
    bc_w = dde.icbc.DirichletBC(geomtime, lambda _x: 0.0, boundary, component=1)

    ic_T = dde.icbc.IC(geomtime, lambda _x: p.T_ref, lambda _x, on_initial: on_initial, component=0)

    data = dde.data.TimePDE(
        geomtime,
        build_pde(p),
        [bc_T, bc_w, ic_T],
        num_domain=6000,
        num_boundary=2000,
        num_initial=2000,
    )

    net = dde.maps.FNN(layers, activation, initializer)
    model = dde.Model(data, net)
    model.compile("adam", lr=lr)
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepXDE PINN for line heating")
    parser.add_argument("--Lx", type=float, default=1000.0)
    parser.add_argument("--Ly", type=float, default=1000.0)
    parser.add_argument("--thickness", type=float, default=12.0)
    parser.add_argument("--rho", type=float, default=7.85e-6)
    parser.add_argument("--cp", type=float, default=500.0)
    parser.add_argument("--k", type=float, default=0.045)
    parser.add_argument("--E", type=float, default=210000.0)
    parser.add_argument("--nu", type=float, default=0.3)
    parser.add_argument("--alpha", type=float, default=1.2e-5)
    parser.add_argument("--T-ref", type=float, default=293.0)
    parser.add_argument("--T-inf", type=float, default=293.0)
    parser.add_argument("--q0", type=float, default=8.4)
    parser.add_argument("--r0", type=float, default=25.0)
    parser.add_argument("--v", type=float, default=10.0)
    parser.add_argument(
        "--heat-y",
        type=float,
        default=None,
        help="Heating-line y position (mm). Default: Ly/2 (centerline).",
    )
    parser.add_argument("--t-final", type=float, default=400.0)
    parser.add_argument("--kappa-th", type=float, default=1.0)

    parser.add_argument("--layers", type=int, nargs="+", default=[3, 128, 128, 128, 2])
    parser.add_argument("--activation", type=str, default="tanh")
    parser.add_argument("--initializer", type=str, default="Glorot normal")
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--epochs", type=int, default=5000)

    parser.add_argument("--output", type=str, default="pinn_results.npz")

    args = parser.parse_args()

    p = Params(
        Lx=args.Lx,
        Ly=args.Ly,
        thickness=args.thickness,
        rho=args.rho,
        cp=args.cp,
        k=args.k,
        E=args.E,
        nu=args.nu,
        alpha=args.alpha,
        T_ref=args.T_ref,
        T_inf=args.T_inf,
        q0=args.q0,
        r0=args.r0,
        v=args.v,
        heat_y=(args.Ly / 2.0 if args.heat_y is None else args.heat_y),
        t_final=args.t_final,
        kappa_th=args.kappa_th,
    )

    model = build_model(p, args.layers, args.activation, args.initializer, args.lr)
    model.train(epochs=args.epochs)

    # Sample deflection at final time
    n = 50
    xs = np.linspace(0.0, p.Lx, n)
    ys = np.linspace(0.0, p.Ly, n)
    X, Y = np.meshgrid(xs, ys)
    T = np.full_like(X, p.t_final)
    pts = np.stack([X.ravel(), Y.ravel(), T.ravel()], axis=1)
    preds = model.predict(pts)
    w = preds[:, 1].reshape(X.shape)

    np.savez(
        args.output,
        x=xs,
        y=ys,
        w=w,
        w_min=float(np.min(w)),
        w_max=float(np.max(w)),
        w_max_abs=float(np.max(np.abs(w))),
    )

    print({
        "output": args.output,
        "w_min_mm": float(np.min(w)),
        "w_max_mm": float(np.max(w)),
        "w_max_abs_mm": float(np.max(np.abs(w))),
    })


if __name__ == "__main__":
    main()
