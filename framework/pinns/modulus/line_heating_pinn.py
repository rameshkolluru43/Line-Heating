"""Modulus PINN template for coupled heat + plate deflection.

This is a starter example to solve:
- Heat equation: rho*cp*dT/dt - k*laplacian(T) = Q(x,y,t)
- Plate equation: D*laplacian(laplacian(w)) + kappa_th*(T - T_ref) = 0

Notes:
- Uses simplified thermal-to-bending coupling (kappa_th) as a placeholder.
- Boundary conditions are minimal (T=T_inf, w=0 on edges). Adjust as needed.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

try:
    import sympy as sp
    from modulus.sym.key import Key
    from modulus.sym.node import Node
    from modulus.sym.domain import Domain
    from modulus.sym.geometry.primitives_2d import Rectangle
    from modulus.sym.eq.pde import PDE
    from modulus.sym.models.fully_connected import FullyConnectedArch
    from modulus.sym.domain.constraint import (
        PointwiseInteriorConstraint,
        PointwiseBoundaryConstraint,
        PointwiseInitialConstraint,
    )
    from modulus.sym.domain.parameterization import Parameterization
    from modulus.sym.solver import Solver
    from modulus.sym.hydra import ModulusConfig
    from modulus.sym import main as modulus_main
except Exception as exc:  # pragma: no cover - optional dependency
    raise SystemExit(
        "Modulus is required. Install modulus-sym and its dependencies before running.\n"
        f"Import error: {exc}"
    ) from exc


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


class LineHeatingPDE(PDE):
    name = "LineHeatingPDE"

    def __init__(self, p: Params):
        x, y, t = sp.symbols("x y t")

        T = sp.Function("T")(x, y, t)
        w = sp.Function("w")(x, y, t)

        rho, cp, k = p.rho, p.cp, p.k
        E, nu, h = p.E, p.nu, p.thickness
        D = E * h**3 / (12.0 * (1.0 - nu**2))

        x0 = p.v * t
        y0 = p.heat_y
        Q = p.q0 * sp.exp(-((x - x0) ** 2 + (y - y0) ** 2) / (2.0 * p.r0**2))

        heat_eq = rho * cp * sp.diff(T, t) - k * (
            sp.diff(T, x, 2) + sp.diff(T, y, 2)
        ) - Q

        plate_eq = D * (
            sp.diff(w, x, 4)
            + 2.0 * sp.diff(w, x, 2, y, 2)
            + sp.diff(w, y, 4)
        ) + p.kappa_th * (T - p.T_ref)

        self.equations = {
            "heat_eq": heat_eq,
            "plate_eq": plate_eq,
        }


def build_domain(cfg: ModulusConfig, p: Params) -> Domain:
    x, y, t = sp.symbols("x y t")
    geo = Rectangle((0.0, 0.0), (p.Lx, p.Ly))
    time = Parameterization({t: (0.0, p.t_final)})

    inputs = [Key("x"), Key("y"), Key("t")]
    outputs = [Key("T"), Key("w")]

    net = FullyConnectedArch(input_keys=inputs, output_keys=outputs)
    pde = LineHeatingPDE(p)

    nodes = [net.make_node(name="pinn")] + pde.make_nodes()

    domain = Domain()

    domain.add_constraint(
        PointwiseInteriorConstraint(
            nodes=nodes,
            geometry=geo,
            outvar={"heat_eq": 0.0, "plate_eq": 0.0},
            batch_size=cfg.batch_size.interior,
            parameterization=time,
        ),
        name="interior",
    )

    domain.add_constraint(
        PointwiseBoundaryConstraint(
            nodes=nodes,
            geometry=geo,
            outvar={"T": p.T_inf, "w": 0.0},
            batch_size=cfg.batch_size.boundary,
            parameterization=time,
        ),
        name="boundary",
    )

    domain.add_constraint(
        PointwiseInitialConstraint(
            nodes=nodes,
            geometry=geo,
            outvar={"T": p.T_ref},
            batch_size=cfg.batch_size.initial,
            parameterization=Parameterization({t: 0.0}),
        ),
        name="initial",
    )

    return domain


@modulus_main(config_path="conf", config_name="line_heating")
def run(cfg: ModulusConfig) -> None:
    params = Params(
        Lx=cfg.custom.Lx,
        Ly=cfg.custom.Ly,
        thickness=cfg.custom.thickness,
        rho=cfg.custom.rho,
        cp=cfg.custom.cp,
        k=cfg.custom.k,
        E=cfg.custom.E,
        nu=cfg.custom.nu,
        alpha=cfg.custom.alpha,
        T_ref=cfg.custom.T_ref,
        T_inf=cfg.custom.T_inf,
        q0=cfg.custom.q0,
        r0=cfg.custom.r0,
        v=cfg.custom.v,
        heat_y=cfg.custom.heat_y,
        t_final=cfg.custom.t_final,
        kappa_th=cfg.custom.kappa_th,
    )

    domain = build_domain(cfg, params)
    solver = Solver(cfg, domain)
    solver.solve()


if __name__ == "__main__":
    run()
