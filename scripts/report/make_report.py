#!/usr/bin/env python3
"""Generate a LaTeX report (and compile to PDF if possible) for a run output folder."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess


def _latex_escape(s: str) -> str:
    # Minimal escaping for common characters.
    repl = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(repl.get(ch, ch) for ch in s)


def _find_fig(out_dir: Path, name: str) -> Path | None:
    p = out_dir / name
    return p if p.exists() else None


def _write_tex(out_dir: Path, summary: dict) -> Path:
    inputs = summary.get("inputs", {})
    thermal = summary.get("thermal", {})
    mech = summary.get("mechanics", {})

    figs = [
        ("Mesh", _find_fig(out_dir, "mesh_3d.png")),
        ("Temperature (top)", _find_fig(out_dir, "temperature_top.png")),
        ("Deflection (top)", _find_fig(out_dir, "deflection_top.png")),
        ("Deflection (3D)", _find_fig(out_dir, "deflection_3d.png")),
        ("Deflection overlay", _find_fig(out_dir, "deflection_3d_overlay.png")),
        ("Heating-line profiles", _find_fig(out_dir, "heating_line_profiles.png")),
        ("Camber width profile", _find_fig(out_dir, "camber_width_profile.png")),
    ]
    figs = [(cap, p) for cap, p in figs if p is not None]

    def fnum(x, default="-"):
        try:
            return f"{float(x):.6g}"
        except Exception:
            return default

    tex = r"""
\documentclass[11pt]{article}
\usepackage[margin=1in]{geometry}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{hyperref}
\usepackage{float}

\title{Ship Plate Line Heating Simulation Report}
\author{Auto-generated}
\date{\today}

\begin{document}
\maketitle

\section*{Run Summary}

\begin{tabular}{@{}ll@{}}
\toprule
Output folder: & \texttt{%(out_dir)s}\\
BC: & \texttt{%(bc)s}\\
Heat mode: & \texttt{%(heat_mode)s}\\
Heating lines (y, mm): & \texttt{%(heat_y_list)s}\\
\bottomrule
\end{tabular}

\section*{Key Metrics}

\begin{tabular}{@{}lll@{}}
\toprule
Category & Metric & Value\\
\midrule
Thermal & $T_{\max,global}$ (K) & %(T_max_global)s\\
Thermal & $t$ at $T_{\max}$ (s) & %(t_at_T_max)s\\
Thermal & $x$ source at $T_{\max}$ (mm) & %(x_src_at_T_max)s\\
Mechanics & $w_{\min}$ (mm, negative=down) & %(w_min)s\\
Mechanics & $w_{\max}$ (mm) & %(w_max)s\\
Mechanics & Camber midspan edge-to-edge (mm) & %(camber)s\\
\bottomrule
\end{tabular}

\section*{Inputs (selected)}

\begin{tabular}{@{}ll@{}}
\toprule
Geometry (mm) & $L_x=%(Lx)s$, $L_y=%(Ly)s$, $t=%(thickness)s$\\
Mesh (mm) & $h=%(h)s$, $h_{ref}=%(h_refine)s$, band=%(refine_band)s\\
Heat source & $q_0=%(q0)s$ W/mm$^2$, $r_0=%(r0)s$ mm, $v=%(velocity)s$ mm/s\\
Time & $\Delta t=%(dt)s$ s, steps=%(steps)s, total=%(total_time)s s\\
Quench & enabled=%(quench)s, start=%(quench_start)s s, $h=%(quench_h)s$ W/mm$^2$/K\\
Inherent & enabled=%(use_inherent)s, $\epsilon_0=%(eps0)s$, $\sigma=%(inh_sigma)s$ mm, $zfrac=%(inh_zfrac)s$\\
\bottomrule
\end{tabular}

"""

    for cap, p in figs:
        tex += "\n\\begin{figure}[H]\n"
        tex += "\\centering\n"
        tex += f"\\includegraphics[width=0.95\\linewidth]{{{_latex_escape(p.name)}}}\n"
        tex += f"\\caption{{{_latex_escape(cap)}}}\n"
        tex += "\\end{figure}\n"

    tex += "\n\\end{document}\n"

    payload = {
        "out_dir": _latex_escape(str(out_dir)),
        "bc": _latex_escape(str(inputs.get("bc", "-"))),
        "heat_mode": _latex_escape(str(inputs.get("heat_mode", "simultaneous"))),
        "heat_y_list": _latex_escape(",".join(str(x) for x in inputs.get("heat_y_list", [])) or "-"),
        "T_max_global": fnum(thermal.get("T_max_global")),
        "t_at_T_max": fnum(thermal.get("t_at_T_max_global")),
        "x_src_at_T_max": fnum(thermal.get("x_source_at_T_max_global")),
        "w_min": fnum(mech.get("w_min")),
        "w_max": fnum(mech.get("w_max")),
        "camber": fnum(mech.get("camber_midspan_edge_to_edge_mm", mech.get("camber_midspan_edge_to_edge_mm"))),
        "Lx": fnum(inputs.get("Lx")),
        "Ly": fnum(inputs.get("Ly")),
        "thickness": fnum(inputs.get("thickness")),
        "h": fnum(inputs.get("h")),
        "h_refine": fnum(inputs.get("h_refine")),
        "refine_band": fnum(inputs.get("refine_band")),
        "q0": fnum(inputs.get("q0")),
        "r0": fnum(inputs.get("r0")),
        "velocity": fnum(inputs.get("velocity")),
        "dt": fnum(inputs.get("dt")),
        "steps": fnum(inputs.get("steps")),
        "total_time": fnum(inputs.get("total_time")),
        "quench": _latex_escape(str(bool(inputs.get("quench", False)))),
        "quench_start": fnum(inputs.get("quench_start")),
        "quench_h": fnum(inputs.get("quench_h_conv")),
        "use_inherent": _latex_escape(str(bool(inputs.get("use_inherent", False)))),
        "eps0": fnum(inputs.get("eps0")),
        "inh_sigma": fnum(inputs.get("inh_sigma")),
        "inh_zfrac": fnum(inputs.get("inh_zfrac")),
    }

    tex_filled = tex % payload
    tex_path = out_dir / "report.tex"
    tex_path.write_text(tex_filled, encoding="utf-8")
    return tex_path


def _compile_pdf(out_dir: Path, tex_path: Path) -> Path | None:
    # Try latexmk first, then pdflatex.
    latexmk = shutil.which("latexmk")
    pdflatex = shutil.which("pdflatex")

    if latexmk:
        subprocess.check_call([latexmk, "-pdf", "-interaction=nonstopmode", tex_path.name], cwd=str(out_dir))
    elif pdflatex:
        subprocess.check_call([pdflatex, "-interaction=nonstopmode", tex_path.name], cwd=str(out_dir))
        subprocess.check_call([pdflatex, "-interaction=nonstopmode", tex_path.name], cwd=str(out_dir))
    else:
        return None

    pdf_path = out_dir / "report.pdf"
    return pdf_path if pdf_path.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output folder containing summary.json and plots")
    args = ap.parse_args()

    out_dir = Path(args.out)
    summary_path = out_dir / "summary.json"
    if not summary_path.exists():
        raise SystemExit(f"Missing {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    tex_path = _write_tex(out_dir, summary)

    pdf = _compile_pdf(out_dir, tex_path)
    if pdf is None:
        print("[make_report] Wrote report.tex (no TeX engine found to build PDF)")
    else:
        print(f"[make_report] Wrote {pdf}")


if __name__ == "__main__":
    main()
