#!/usr/bin/env python3
"""
Validate the project setup and dependencies across platforms.
Checks that all required tools and libraries are properly configured.
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    @classmethod
    def disable(cls):
        """Disable colors for Windows or when not in terminal"""
        cls.GREEN = cls.YELLOW = cls.RED = cls.BLUE = cls.BOLD = cls.RESET = ''


if platform.system() == 'Windows' or not sys.stdout.isatty():
    Colors.disable()


def check(condition: bool, message: str, is_optional: bool = False) -> bool:
    """Print check result with appropriate formatting"""
    if condition:
        print(f"  {Colors.GREEN}✓{Colors.RESET} {message}")
        return True
    else:
        symbol = f"{Colors.YELLOW}⚠{Colors.RESET}" if is_optional else f"{Colors.RED}✗{Colors.RESET}"
        print(f"  {symbol} {message}")
        return False if not is_optional else True


def run_command(cmd: list[str], capture: bool = True) -> tuple[bool, str]:
    """Run a command and return success status and output"""
    try:
        if capture:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0, result.stdout.strip()
        else:
            result = subprocess.run(cmd, timeout=10)
            return result.returncode == 0, ""
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        return False, ""


def check_python() -> dict:
    """Check Python installation"""
    print(f"\n{Colors.BOLD}Python Environment{Colors.RESET}")
    
    results = {"required": True, "satisfied": False}
    
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    # Accept Python 3.11, 3.12, or 3.13+ with a warning
    if version.major == 3 and version.minor >= 11:
        if version.minor <= 12:
            check(True, f"Python {version_str} (supported)")
            results["satisfied"] = True
        else:
            check(True, f"Python {version_str} (newer than tested, but should work)", is_optional=False)
            results["satisfied"] = True
            print(f"    {Colors.YELLOW}Note: This project is tested on Python 3.11-3.12{Colors.RESET}")
            print(f"    {Colors.YELLOW}Python 3.{version.minor} may work but hasn't been fully tested{Colors.RESET}")
    else:
        check(False, f"Python {version_str} (need 3.11 or newer)")
    
    # Check for venv module
    try:
        import venv
        check(True, "venv module available")
    except ImportError:
        check(False, "venv module not available")
        results["satisfied"] = False
    
    return results


def check_compiler() -> dict:
    """Check C++ compiler availability"""
    print(f"\n{Colors.BOLD}C++ Compiler{Colors.RESET}")
    
    results = {"required": True, "satisfied": False}
    system = platform.system()
    
    if system == "Windows":
        # Check for cl.exe (Visual Studio)
        success, _ = run_command(["where", "cl.exe"])
        if success:
            check(True, "Visual Studio C++ compiler found")
            results["satisfied"] = True
        else:
            # Check for common VS installations
            vs_paths = [
                "C:\\Program Files\\Microsoft Visual Studio\\2022",
                "C:\\Program Files\\Microsoft Visual Studio\\2019",
                "C:\\Program Files (x86)\\Microsoft Visual Studio\\2022",
                "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019",
            ]
            for path in vs_paths:
                if Path(path).exists():
                    check(True, f"Visual Studio installation found at {path}")
                    results["satisfied"] = True
                    break
            else:
                check(False, "Visual Studio Build Tools not found")
    else:
        # Check for g++ or clang++
        for compiler in ["g++", "clang++"]:
            if shutil.which(compiler):
                success, version = run_command([compiler, "--version"])
                if success:
                    version_line = version.split('\n')[0]
                    check(True, f"{compiler} found: {version_line}")
                    results["satisfied"] = True
                    break
        else:
            check(False, "No C++ compiler (g++ or clang++) found")
    
    return results


def check_cmake() -> dict:
    """Check CMake availability"""
    print(f"\n{Colors.BOLD}CMake{Colors.RESET}")
    
    results = {"required": False, "satisfied": False}
    
    if shutil.which("cmake"):
        success, version = run_command(["cmake", "--version"])
        if success:
            version_line = version.split('\n')[0]
            check(True, f"System CMake found: {version_line}")
            results["satisfied"] = True
    else:
        check(True, "System CMake not found (Python package will be used)", is_optional=True)
        results["satisfied"] = True  # Not critical since we have pip cmake
    
    return results


def check_git() -> dict:
    """Check Git availability"""
    print(f"\n{Colors.BOLD}Version Control{Colors.RESET}")
    
    results = {"required": False, "satisfied": False}
    
    if shutil.which("git"):
        success, version = run_command(["git", "--version"])
        if success:
            check(True, f"Git found: {version}", is_optional=True)
            results["satisfied"] = True
    else:
        check(False, "Git not found (optional for development)", is_optional=True)
        results["satisfied"] = True
    
    return results


def check_optional_tools() -> dict:
    """Check optional tools"""
    print(f"\n{Colors.BOLD}Optional Tools{Colors.RESET}")
    
    results = {"required": False, "satisfied": True}
    
    # Gmsh
    if shutil.which("gmsh"):
        check(True, "Gmsh executable found", is_optional=True)
    else:
        check(False, "Gmsh executable not found (Python bindings will be used)", is_optional=True)
    
    # LaTeX
    latex_found = False
    for latex_cmd in ["latexmk", "pdflatex"]:
        if shutil.which(latex_cmd):
            check(True, f"{latex_cmd} found", is_optional=True)
            latex_found = True
            break
    
    if not latex_found:
        check(False, "LaTeX not found (PDF reports will not be generated)", is_optional=True)
    
    return results


def check_project_structure() -> dict:
    """Check project directory structure"""
    print(f"\n{Colors.BOLD}Project Structure{Colors.RESET}")
    
    results = {"required": True, "satisfied": True}
    repo_root = Path(__file__).resolve().parents[1]
    
    required_paths = [
        ("requirements.txt", "Python requirements file"),
        ("run_config.example.json", "Example configuration"),
        ("scripts/run_anywhere.py", "Main runner script"),
        ("thermo_fem/cpp/CMakeLists.txt", "C++ build configuration"),
        ("thermo_fem/python/run_coupled_3d.py", "Main simulation script"),
    ]
    
    for rel_path, description in required_paths:
        full_path = repo_root / rel_path
        if full_path.exists():
            check(True, f"{description} exists")
        else:
            check(False, f"{description} missing")
            results["satisfied"] = False
    
    # Check if results directory can be created
    results_dir = repo_root / "results"
    try:
        results_dir.mkdir(exist_ok=True)
        check(True, "Results directory accessible")
    except Exception as e:
        check(False, f"Cannot create results directory: {e}")
        results["satisfied"] = False
    
    return results


def check_python_packages() -> dict:
    """Check if Python packages can be imported (if venv exists)"""
    print(f"\n{Colors.BOLD}Python Packages (in venv if it exists){Colors.RESET}")
    
    results = {"required": False, "satisfied": True}
    repo_root = Path(__file__).resolve().parents[1]
    venv_dir = repo_root / ".venv_lineheating"
    
    if not venv_dir.exists():
        check(True, "Virtual environment not yet created (run setup first)", is_optional=True)
        return results
    
    # Find Python in venv
    if platform.system() == "Windows":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
    
    if not venv_python.exists():
        check(False, "Virtual environment exists but Python not found", is_optional=True)
        return results
    
    packages = ["numpy", "scipy", "matplotlib", "gmsh", "pybind11", "cmake"]
    
    for package in packages:
        success, output = run_command([str(venv_python), "-c", f"import {package}; print({package}.__version__)"])
        if success:
            check(True, f"{package} {output} installed", is_optional=True)
        else:
            check(False, f"{package} not installed", is_optional=True)
    
    return results


def print_summary(all_results: dict):
    """Print validation summary"""
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}Summary{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    
    all_satisfied = True
    required_satisfied = True
    
    for category, result in all_results.items():
        status = "✓" if result["satisfied"] else "✗"
        color = Colors.GREEN if result["satisfied"] else (Colors.YELLOW if not result["required"] else Colors.RED)
        req_str = "(required)" if result["required"] else "(optional)"
        
        print(f"{color}{status}{Colors.RESET} {category}: {req_str}")
        
        if not result["satisfied"]:
            all_satisfied = False
            if result["required"]:
                required_satisfied = False
    
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")
    
    if required_satisfied:
        print(f"{Colors.GREEN}✓ All required dependencies satisfied!{Colors.RESET}")
        print(f"\nTo set up the project:")
        system = platform.system()
        if system == "Windows":
            print(f"  {Colors.BLUE}setup.bat{Colors.RESET}")
        else:
            print(f"  {Colors.BLUE}./setup.sh{Colors.RESET}")
    else:
        print(f"{Colors.RED}✗ Some required dependencies are missing!{Colors.RESET}")
        print(f"\nPlease install missing dependencies and run validation again.")
        print(f"See {Colors.BLUE}SETUP.md{Colors.RESET} for detailed installation instructions.")
    
    if not all_satisfied and required_satisfied:
        print(f"\n{Colors.YELLOW}Note:{Colors.RESET} Optional dependencies are missing but not required for basic operation.")
    
    print()
    return 0 if required_satisfied else 1


def main():
    """Main validation routine"""
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}Ship Plate Line Heating - Setup Validation{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"\nPlatform: {platform.system()} {platform.release()}")
    print(f"Architecture: {platform.machine()}")
    
    all_results = {
        "Python": check_python(),
        "C++ Compiler": check_compiler(),
        "CMake": check_cmake(),
        "Git": check_git(),
        "Project Structure": check_project_structure(),
        "Optional Tools": check_optional_tools(),
        "Python Packages": check_python_packages(),
    }
    
    return print_summary(all_results)


if __name__ == "__main__":
    sys.exit(main())
