#!/usr/bin/env python3
"""Cross-platform runner for the 3D line-heating simulation.

What it does:
- Creates a local venv (./.venv_lineheating)
- Installs Python deps from requirements.txt
- Builds the C++ pybind11 module (thermo_bindings) via CMake
- Runs thermo_fem/python/run_coupled_3d.py with provided args
- Generates a LaTeX report and compiles to PDF when a TeX engine is available

Usage examples:
  python scripts/run_anywhere.py --out outputs/run1 -- \
    --Lx 1000 --Ly 1000 --thickness 12 --h 40 --h-refine 10 --refine-band 160 \
    --heat-y-list 250,500,750 --heat-mode sequential --pass-gap 0 \
    --target-Tmax 900 --dt 5 --extra-time 400 --quench --quench-h-conv 5e-3 \
    --bc corner_pins --use-inherent --eps0 0.002 --inh-sigma 60 --inh-zfrac 0.5

  # If you already have an output folder and only want the report:
  python scripts/run_anywhere.py --report-only --out outputs/run1
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def _looks_like_repo(path: Path) -> bool:
    return (
        (path / "requirements.txt").exists()
        and (path / "thermo_fem").is_dir()
        and (path / "scripts").is_dir()
    )


def _resolve_repo_root() -> Path:
    env_root = os.environ.get("LINEHEATING_REPO")
    if env_root:
        env_path = Path(env_root).expanduser().resolve()
        if _looks_like_repo(env_path):
            return env_path

    cwd = Path.cwd().resolve()
    if _looks_like_repo(cwd):
        return cwd

    exe_dir = Path(sys.executable).resolve().parent
    if _looks_like_repo(exe_dir):
        return exe_dir

    file_root = Path(__file__).resolve().parents[1]
    if _looks_like_repo(file_root):
        return file_root

    raise SystemExit(
        "Could not locate repository root. Run from the repo directory or set LINEHEATING_REPO."
    )


REPO_ROOT = _resolve_repo_root()
VENV_DIR = REPO_ROOT / ".venv_lineheating"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
RESULTS_ROOT = REPO_ROOT / "results"


def _default_run_name(config_path: Path | None) -> str:
    if config_path is not None:
        stem = config_path.stem.strip()
        if stem:
            return stem
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"run_{ts}"


def _normalize_out_dir(out_dir: Path, *, allow_code_out: bool) -> Path:
    """Ensure outputs go to a non-code folder by default.

    If out_dir is a relative path into a known code folder (e.g. thermo_fem/python/...),
    redirect it to RESULTS_ROOT/<basename> unless allow_code_out is True.
    """
    out_dir = Path(out_dir)

    if not out_dir.is_absolute():
        out_dir = (REPO_ROOT / out_dir).resolve()

    if allow_code_out:
        return out_dir

    try:
        rel = out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except Exception:
        # Outside repo (absolute elsewhere) -> fine.
        return out_dir

    if len(rel.parts) == 0:
        return out_dir

    top = rel.parts[0]
    code_tops = {"thermo_fem", "python_prototype", "scripts", "docs", "LiteratureDocs"}
    if top in code_tops:
        redirected = (RESULTS_ROOT / out_dir.name).resolve()
        print(
            f"[run_anywhere] Redirecting output from '{rel}' to 'results/{out_dir.name}' "
            "(use --allow-code-out to keep it under code folders)."
        )
        return redirected

    return out_dir


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _to_cli_args(sim_cfg: dict) -> list[str]:
    """Convert a JSON dict into CLI args for run_coupled_3d.py.

    Conventions:
    - Keys can be snake_case or already dash-separated; they map to --kebab-case.
    - True booleans become flags: --quench, --use-inherent, etc.
    - False/None are omitted.
    - Lists become comma-separated (used for heat_y_list).
    """
    args: list[str] = []

    def key_to_flag(k: str) -> str:
        k = str(k).strip()
        if k.startswith("--"):
            return k
        return "--" + k.replace("_", "-")

    for key, value in sim_cfg.items():
        if value is None:
            continue
        flag = key_to_flag(str(key))

        if isinstance(value, bool):
            if value:
                args.append(flag)
            continue

        if isinstance(value, (list, tuple)):
            if len(value) == 0:
                continue
            if any(isinstance(v, (dict, list, tuple)) for v in value):
                args.extend([flag, json.dumps(value)])
            else:
                # Special-case common lists: heat_y_list, etc.
                args.extend([flag, ",".join(str(v) for v in value)])
            continue

        if isinstance(value, dict):
            args.extend([flag, json.dumps(value)])
            continue

        args.extend([flag, str(value)])

    return args


def _run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    subprocess.check_call(cmd, cwd=str(cwd) if cwd else None, env=env)


def _capture(cmd: list[str], *, cwd: Path | None, env: dict[str, str] | None, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as f:
        p = subprocess.Popen(cmd, cwd=str(cwd) if cwd else None, env=env, stdout=f, stderr=subprocess.STDOUT)
        rc = p.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)


def _venv_env(venv_dir: Path) -> dict[str, str]:
    """Return a clean environment for venv execution.

    This removes user/global Python path injections that can cause the venv
    to pick up system site-packages (e.g., PYTHONPATH). It also ensures the
    venv bin directory is first on PATH.
    """
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONUSERBASE", None)
    env["PYTHONNOUSERSITE"] = "1"
    vbin = str(_venv_python(venv_dir).parent)
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = vbin + os.pathsep + env.get("PATH", "")
    return env


def _venv_python(venv_dir: Path) -> Path:
    if platform.system().lower().startswith("win"):
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_pip(venv_dir: Path) -> list[str]:
    return [str(_venv_python(venv_dir)), "-m", "pip"]


def _ensure_python_version() -> None:
    # This repo previously hit numpy/binary issues on very new Python versions.
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11+ is required (recommended: 3.11-3.12).")
    if sys.version_info >= (3, 14):
        print(
            f"[run_anywhere] Warning: Python 3.{sys.version_info.minor} detected. "
            "This project is tested on Python 3.11-3.12. Proceed with caution."
        )


def _ensure_venv(venv_dir: Path) -> None:
    if venv_dir.exists():
        return
    print(f"[run_anywhere] Creating venv: {venv_dir}")
    import venv

    venv.EnvBuilder(with_pip=True).create(str(venv_dir))


def _install_python_deps(venv_dir: Path) -> None:
    if not REQUIREMENTS.exists():
        raise SystemExit(f"Missing requirements file: {REQUIREMENTS}")

    print("[run_anywhere] Installing Python deps...")
    env = _venv_env(venv_dir)
    _run(_venv_pip(venv_dir) + ["install", "--upgrade", "pip", "setuptools", "wheel"], env=env)
    _run(_venv_pip(venv_dir) + ["install", "-r", str(REQUIREMENTS)], env=env)


def _check_gmsh(venv_dir: Path) -> None:
    """Check that Gmsh is usable (Python bindings, and optionally system binary)."""
    vpy = _venv_python(venv_dir)

    # Ensure the Python bindings import.
    try:
        subprocess.check_call([str(vpy), "-c", "import gmsh; print(gmsh.__version__)"], env=_venv_env(venv_dir))
    except Exception as exc:
        raise SystemExit(
            "Failed to import the Python 'gmsh' package inside the venv. "
            "Re-run the runner, or check that pip installed requirements successfully."
        ) from exc

    # The solver uses the Python bindings, so a system 'gmsh' executable is not required.
    # Still, many users expect it, so we provide install hints.
    if shutil.which("gmsh") is None:
        sys_name = platform.system().lower()
        print("[run_anywhere] Note: system 'gmsh' executable not found on PATH (optional).")
        if "darwin" in sys_name or "mac" in sys_name:
            print("  Install with: brew install gmsh")
        elif "linux" in sys_name:
            print("  Install with: sudo apt-get install gmsh  (Debian/Ubuntu)")
            print("  or: sudo dnf install gmsh           (Fedora/RHEL)")
        elif "windows" in sys_name:
            print("  Install with: choco install gmsh   (Chocolatey)")
            print("  or download from: https://gmsh.info/")


def _pybind11_cmake_dir(venv_python: Path) -> str:
    code = (
        "import pybind11, pathlib; "
        "p = pathlib.Path(pybind11.get_cmake_dir()); "
        "print(str(p))"
    )
    out = subprocess.check_output([str(venv_python), "-c", code], text=True, env=_venv_env(venv_python.parent.parent)).strip()
    if not out:
        raise RuntimeError("Failed to locate pybind11 CMake dir")
    return out


def _build_cpp_extension(venv_dir: Path) -> None:
    print("[run_anywhere] Building C++ extension (thermo_bindings) via CMake...")
    vpy = _venv_python(venv_dir)
    cmake_exe = shutil.which("cmake")

    # If cmake is not on PATH, the pip 'cmake' package usually provides it as a module.
    if cmake_exe is None:
        # Try module form: python -m cmake
        try:
            subprocess.check_call([str(vpy), "-m", "cmake", "--version"], stdout=subprocess.DEVNULL, env=_venv_env(venv_dir))
            cmake_cmd = [str(vpy), "-m", "cmake"]
        except Exception as exc:
            raise SystemExit(
                "CMake not found. Install CMake (or ensure it is on PATH)."
            ) from exc
    else:
        cmake_cmd = [cmake_exe]

    build_dir = REPO_ROOT / "thermo_fem" / "build" / "cpp"
    src_dir = REPO_ROOT / "thermo_fem" / "cpp"

    pybind_dir = _pybind11_cmake_dir(vpy)

    cfg = "Release"
    # Force CMake to use the venv Python for FindPython/pybind11.
    vpy_str = str(vpy)
    _run(
        cmake_cmd
        + [
            "-S",
            str(src_dir),
            "-B",
            str(build_dir),
            "-DPYBIND11_FINDPYTHON=ON",
            f"-Dpybind11_DIR={pybind_dir}",
            f"-DPython_EXECUTABLE={vpy_str}",
            f"-DPython3_EXECUTABLE={vpy_str}",
        ],
        cwd=REPO_ROOT,
        env=_venv_env(venv_dir),
    )

    # Multi-config generators (Visual Studio) need --config.
    _run(cmake_cmd + ["--build", str(build_dir), "--config", cfg, "-j"], cwd=REPO_ROOT, env=_venv_env(venv_dir))


def _run_simulation(venv_dir: Path, out_dir: Path, sim_args: list[str]) -> None:
    vpy = _venv_python(venv_dir)
    sim = REPO_ROOT / "thermo_fem" / "python" / "run_coupled_3d.py"

    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "run.log"

    # Ensure the simulation writes outputs into the same out_dir.
    sim_args = list(sim_args)
    if "--out" not in sim_args:
        sim_args += ["--out", str(out_dir.resolve())]

    cmd = [str(vpy), str(sim)] + sim_args

    print(f"[run_anywhere] Running simulation -> {out_dir}")
    _capture(cmd, cwd=REPO_ROOT / "thermo_fem" / "python", env=_venv_env(venv_dir), log_path=log_path)


def _make_report(venv_dir: Path, out_dir: Path) -> tuple[Path, Path | None]:
    vpy = _venv_python(venv_dir)
    report_tool = REPO_ROOT / "scripts" / "report" / "make_report.py"
    cmd = [str(vpy), str(report_tool), "--out", str(out_dir)]

    print("[run_anywhere] Generating LaTeX report...")
    _run(cmd, cwd=REPO_ROOT, env=_venv_env(venv_dir))

    tex_path = out_dir / "report.tex"
    pdf_path = out_dir / "report.pdf"

    if pdf_path.exists():
        return tex_path, pdf_path
    return tex_path, None


def main() -> None:
    _ensure_python_version()

    parser = argparse.ArgumentParser(description="Cross-platform runner for Ship Plate Line Heating")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help=(
            "Path to JSON config file. If provided, it drives out/runner/simulation parameters. "
            "CLI sim args after '--' are ignored."
        ),
    )
    parser.add_argument("--out", type=str, default=None, help="Output directory for results/report (overrides config)")
    parser.add_argument(
        "--allow-code-out",
        action="store_true",
        help=(
            "Allow writing outputs under code folders (e.g. thermo_fem/python). "
            "By default, such paths are redirected to ./results/<name>."
        ),
    )
    parser.add_argument("--report-only", action="store_true", help="Only generate the report for an existing output folder")
    parser.add_argument("--no-build", action="store_true", help="Skip C++ extension build")
    parser.add_argument("--no-report", action="store_true", help="Skip LaTeX report generation")
    parser.add_argument("sim_args", nargs=argparse.REMAINDER, help="Args after -- are passed to run_coupled_3d.py")

    args = parser.parse_args()

    sim_args: list[str] = []
    cfg = None
    cfg_path: Path | None = None
    if args.config is not None:
        cfg_path = Path(args.config)
        cfg = _load_config(cfg_path)

    # Determine out_dir (CLI overrides config). Default to ./results/<run_name>.
    if args.out is not None:
        out_dir = Path(args.out)
    elif cfg is not None and "out" in cfg and cfg["out"]:
        out_dir = Path(cfg["out"])
    else:
        out_dir = RESULTS_ROOT / _default_run_name(cfg_path)

    out_dir = _normalize_out_dir(out_dir, allow_code_out=args.allow_code_out)

    # Determine runner flags (CLI overrides config)
    if cfg is not None:
        runner_cfg = cfg.get("runner", {}) if isinstance(cfg, dict) else {}
        if not args.report_only:
            args.report_only = bool(runner_cfg.get("report_only", False))
        if not args.no_build:
            args.no_build = bool(runner_cfg.get("no_build", False))
        if not args.no_report:
            args.no_report = bool(runner_cfg.get("no_report", False))

    if cfg is not None:
        sim_cfg = cfg.get("simulation", {})
        if not isinstance(sim_cfg, dict):
            raise SystemExit("Config field 'simulation' must be an object/dict")
        sim_args = _to_cli_args(sim_cfg)
    else:
        # Strip a leading '--' if present (common pattern: script.py --out X -- --Lx 1000 ...)
        sim_args = list(args.sim_args)
        if sim_args[:1] == ["--"]:
            sim_args = sim_args[1:]

    print("[run_anywhere] System:")
    print(f"  OS: {platform.system()} {platform.release()}")
    print(f"  Python: {sys.version.split()[0]}")

    _ensure_venv(VENV_DIR)
    _install_python_deps(VENV_DIR)
    _check_gmsh(VENV_DIR)

    if not args.report_only:
        if not args.no_build:
            _build_cpp_extension(VENV_DIR)
        _run_simulation(VENV_DIR, out_dir, sim_args)

    tex_path = None
    pdf_path = None
    if not args.no_report:
        tex_path, pdf_path = _make_report(VENV_DIR, out_dir)

    manifest = {
        "out_dir": str(out_dir),
        "summary_json": str(out_dir / "summary.json"),
        "run_log": str(out_dir / "run.log"),
        "report_tex": (None if tex_path is None else str(tex_path)),
        "report_pdf": (None if pdf_path is None else str(pdf_path)),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version.split()[0],
        },
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "solution_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("[run_anywhere] Done")
    print(f"  Manifest: {out_dir / 'solution_manifest.json'}")
    if not args.no_report:
        print(f"  Report LaTeX: {out_dir / 'report.tex'}")
        if pdf_path is not None:
            print(f"  Report PDF: {pdf_path}")
        else:
            print("  Report PDF: not built (no TeX engine found). See report.tex.")


if __name__ == "__main__":
    main()
